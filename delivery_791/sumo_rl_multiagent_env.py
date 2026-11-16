"""
Entorno Gymnasium para controlar VARIOS semaforos de la red de Mendoza a la
vez con aprendizaje por refuerzo (accion conjunta / centralizado), via TraCI.

Esto extiende sumo_rl_env.py (que controlaba un unico semaforo con un
agente aislado) a las 12 intersecciones criticas de scope_tls_top12.json,
coordinadas entre si -- responde a la pregunta de "como hago para que los
semaforos de atras tambien se ajusten y no se forme congestion".

Como se logra la coordinacion (dos mecanismos, no uno solo):

1. OBSERVACION con informacion del vecino: la observacion de cada semaforo
   no es solo su propia cola. Incluye ademas la ocupacion de su calle de
   salida (aguas abajo, ver tls_topology.py) y la cola del/los semaforo(s)
   vecino(s) semaforizados directos dentro del scope (tls_adjacency.json).
   Asi el agente puede aprender relaciones del tipo "si el vecino de
   adelante ya esta lleno, no le mande mas autos ahora".

2. RECOMPENSA compartida a nivel RED: en vez de que cada semaforo maximice
   solo su propia cola local, la recompensa es la MISMA para todos los
   agentes: -(promedio de autos parados en TODAS las aproximaciones de los
   12 semaforos). Un agente que "resuelve" su cola empujandola al vecino no
   mejora la recompensa (la cola del vecino sigue contando), asi que no hay
   incentivo para trasladar el problema en vez de reducirlo.

Se entrena con UNA sola politica que controla los 12 semaforos a la vez
(accion conjunta / MultiDiscrete), no 12 politicas independientes -- es la
forma mas simple de implementar coordinacion real con las librerias que ya
usa el proyecto (Stable-Baselines3, que no trae multi-agente nativo). Es
"centralizado" en el sentido de que una unica red neuronal ve el estado de
toda la red y decide todas las fases juntas; en el informe (seccion 8) esto
se puede mencionar como una simplificacion practica de MARL (multi-agent
RL) "totalmente descentralizado" -- razonable para 12 intersecciones, mas
dificil de escalar a las 63 sin pasar a algo como PettingZoo/RLlib con
QMIX/VDN (mencionado como trabajo futuro).

Accion: MultiDiscrete([2] * N) -- un bit por semaforo:
    0 = mantener/extender la fase verde actual de ese semaforo
    1 = pedir avanzar a la siguiente fase verde del ciclo (si ya paso el
        verde minimo de ESE semaforo; si no, no hace nada)

Observacion: Box de 5*N valores, 5 por semaforo (en el orden de
scope_tls_top12.json):
    [cola_fase_actual/20, cola_maxima_otras_fases/20, tiempo_en_fase/60,
     ocupacion_aguas_abajo_fase_actual (0-1),
     cola_maxima_de_vecinos_semaforizados_en_el_scope/20]

Recompensa: -(promedio de autos parados en las aproximaciones de los 12
semaforos, sobre todos los pasos de simulacion del intervalo de decision).
Es la MISMA recompensa (escalar unico) para toda la accion conjunta.
"""
import os
import sys
import json
import numpy as np
import gymnasium as gym
from gymnasium import spaces

sys.path.insert(0, os.environ["SUMO_HOME"] + "/tools")
import traci
import ga_lib as gl
import adaptive_lib as al

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MIN_GREEN = 10
DECISION_DT = 5
SIM_END = 1800
N_FEATURES_PER_TLS = 5


def load_scope_ids():
    with open(os.path.join(PROJECT_DIR, "scope_tls_top12.json")) as f:
        return json.load(f)


class RLPhaseAgent:
    """Maquina de estados de UN semaforo bajo control de RL: guarda fase
    actual/tiempos y ejecuta la transicion amarilla, igual que
    adaptive_lib.AdaptiveController, pero el "switch o no" lo decide una
    accion externa (del agente de RL) en vez de una heuristica de presion."""

    def __init__(self, tls_id, phases, lanes, downstream_lanes, neighbor_ids):
        self.id = tls_id
        self.phases = phases
        self.lanes = lanes
        self.neighbor_ids = neighbor_ids  # ids de vecinos DENTRO del scope
        self.green_indices = [i for i, p in enumerate(phases) if p["is_green"]]
        self.yellow_of = {}
        for k, gi in enumerate(self.green_indices):
            self.yellow_of[gi] = (gi + 1) % len(phases)
        self.green_lanes = {}
        for gi in self.green_indices:
            state = phases[gi]["state"]
            s = set()
            for ch, lane in zip(state, lanes):
                if ch in "Gg":
                    s.add(lane)
            self.green_lanes[gi] = list(s)
        self.downstream_of_phase = {}
        for gi in self.green_indices:
            dl = set()
            for lane in self.green_lanes[gi]:
                dl.update(downstream_lanes.get(lane, []))
            self.downstream_of_phase[gi] = list(dl)

        self.current_phase = self.green_indices[0]
        self.mode = "green"
        self.green_timer = 0
        self.yellow_timer = 0
        self.target_phase = None

    def halting(self, gi, get_halting):
        return sum(get_halting(l) for l in self.green_lanes[gi])

    def downstream_occupancy(self, gi, get_occupancy):
        lanes = self.downstream_of_phase.get(gi)
        if not lanes:
            return 0.0
        return max(get_occupancy(l) for l in lanes)

    def next_green_index(self):
        pos = self.green_indices.index(self.current_phase)
        return self.green_indices[(pos + 1) % len(self.green_indices)]

    def apply_action(self, want_switch, set_phase):
        """Se llama UNA vez por intervalo de decision (no cada segundo).
        Si corresponde, inicia la transicion a amarillo."""
        if self.mode != "green":
            return
        if want_switch and self.green_timer >= MIN_GREEN:
            target = self.next_green_index()
            yi = self.yellow_of[self.current_phase]
            set_phase(self.id, yi)
            self.target_phase = target
            self.mode = "yellow"
            self.yellow_timer = int(self.phases[yi]["duration"])

    def tick(self, set_phase):
        """Se llama UNA vez por segundo de simulacion (siempre, haya o no
        accion nueva ese segundo) para hacer avanzar amarillos/timers."""
        if self.mode == "yellow":
            self.yellow_timer -= 1
            if self.yellow_timer <= 0:
                set_phase(self.id, self.target_phase)
                self.current_phase = self.target_phase
                self.mode = "green"
                self.green_timer = 0
        else:
            self.green_timer += 1


class SumoMultiTLSEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, rou_path="osm.rou.xml", sim_end=SIM_END, use_gui=False, label="rlmulti",
                 tripinfo_path=None, stats_path=None, emissions=False):
        super().__init__()
        self.rou_path = os.path.join(PROJECT_DIR, rou_path)
        self.sim_end = sim_end
        self.use_gui = use_gui
        self.label = label
        # solo se usan para evaluacion final (eval_rl_multi.py): durante el
        # entrenamiento normal se dejan en None para no pagar el costo de
        # escribir tripinfo/emisiones en cada episodio
        self.tripinfo_path = tripinfo_path
        self.stats_path = stats_path
        self.emissions = emissions

        self.scope = load_scope_ids()
        n = len(self.scope)

        with open(gl.NET_PATH) as f:
            net_text = f.read()
        gene_map, _ = gl.build_gene_map(net_text, self.scope)
        gene_map_by_id = {e["id"]: e for e in gene_map}

        frozen_text = al.build_frozen_net(net_text, self.scope)
        self.net_path = os.path.join(PROJECT_DIR, f"net_rlmulti_{label}.xml")
        with open(self.net_path, "w") as f:
            f.write(frozen_text)

        lanes_info = json.load(open(os.path.join(PROJECT_DIR, "tls_controlled_lanes.json")))

        downstream_path = os.path.join(PROJECT_DIR, "tls_downstream_lanes.json")
        downstream_info = json.load(open(downstream_path)) if os.path.exists(downstream_path) else {}

        adjacency_path = os.path.join(PROJECT_DIR, "tls_adjacency.json")
        adjacency = json.load(open(adjacency_path)) if os.path.exists(adjacency_path) else {}
        scope_set = set(self.scope)

        self.agents = []
        for tid in self.scope:
            entry = gene_map_by_id[tid]
            phases = [{"state": s, "duration": d, "is_green": g} for d, s, g in entry["phases"]]
            lanes = lanes_info[tid]["lanes"]
            downstream_lanes = downstream_info.get(tid, {})
            adj = adjacency.get(tid, {"upstream": [], "downstream": []})
            neighbor_ids = [x for x in (adj["upstream"] + adj["downstream"]) if x in scope_set]
            self.agents.append(RLPhaseAgent(tid, phases, lanes, downstream_lanes, neighbor_ids))

        self._agent_by_id = {a.id: a for a in self.agents}
        n_direct_neighbors = sum(1 for a in self.agents if a.neighbor_ids)
        print(f"[SumoMultiTLSEnv] {n} semaforos controlados; "
              f"{n_direct_neighbors} tienen al menos un vecino directo tambien controlado.", flush=True)

        self.action_space = spaces.MultiDiscrete([2] * n)
        self.observation_space = spaces.Box(low=0.0, high=10.0, shape=(N_FEATURES_PER_TLS * n,), dtype=np.float32)

        self._conn_open = False
        self.sim_time = 0

    def _halting_lane(self, lane):
        return traci.lane.getLastStepHaltingNumber(lane)

    def _occupancy_lane(self, lane):
        return traci.lane.getLastStepOccupancy(lane)

    def _agent_obs(self, a):
        h_cur = a.halting(a.current_phase, self._halting_lane)
        others = [gi for gi in a.green_indices if gi != a.current_phase]
        h_other = max((a.halting(gi, self._halting_lane) for gi in others), default=0)
        occ = a.downstream_occupancy(a.current_phase, self._occupancy_lane)
        if a.neighbor_ids:
            neigh_h = max(self._agent_by_id[nid].halting(self._agent_by_id[nid].current_phase, self._halting_lane)
                          for nid in a.neighbor_ids)
        else:
            neigh_h = 0
        return [h_cur / 20.0, h_other / 20.0, a.green_timer / 60.0, occ, neigh_h / 20.0]

    def _obs(self):
        feats = []
        for a in self.agents:
            feats.extend(self._agent_obs(a))
        return np.array(feats, dtype=np.float32)

    def _network_halting(self):
        total, count = 0, 0
        for a in self.agents:
            total += a.halting(a.current_phase, self._halting_lane)
            count += 1
        return total

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        if self._conn_open:
            try:
                traci.close()
            except Exception:
                pass
            self._conn_open = False

        binary = "sumo-gui" if self.use_gui else "sumo"
        cmd = [
            binary, "-n", self.net_path, "-r", self.rou_path,
            "-b", "0", "-e", str(self.sim_end),
            "--ignore-route-errors", "true", "--time-to-teleport", "300",
            "--no-step-log", "true", "--no-warnings", "true",
        ]
        if self.tripinfo_path:
            cmd += ["--tripinfo-output", self.tripinfo_path]
        if self.stats_path:
            cmd += ["--statistic-output", self.stats_path]
        if self.emissions:
            cmd += ["--device.emissions.probability", "1.0"]
        traci.start(cmd, label=self.label)
        self._conn_open = True
        for a in self.agents:
            a.current_phase = a.green_indices[0]
            a.mode = "green"
            a.green_timer = 0
            traci.trafficlight.setPhase(a.id, a.current_phase)
        self.sim_time = 0
        return self._obs(), {}

    def step(self, action):
        def set_phase(tls_id, idx):
            traci.trafficlight.setPhase(tls_id, idx)

        for a, want_switch in zip(self.agents, action):
            a.apply_action(bool(want_switch), set_phase)

        halting_samples = []
        for _ in range(DECISION_DT):
            traci.simulationStep()
            self.sim_time += 1
            for a in self.agents:
                a.tick(set_phase)
            halting_samples.append(self._network_halting())

        reward = -float(np.mean(halting_samples)) if halting_samples else 0.0
        terminated = self.sim_time >= self.sim_end
        truncated = False
        return self._obs(), reward, terminated, truncated, {}

    def close(self):
        if self._conn_open:
            try:
                traci.close()
            except Exception:
                pass
            self._conn_open = False
