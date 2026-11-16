"""
Entorno Gymnasium para controlar UN semaforo de la red de Mendoza con
aprendizaje por refuerzo, via TraCI.

Semaforo elegido: 1135888071 (2 fases verdes, bastante congestionado,
rank #5 en el ranking de congestion del escenario moderado).

Accion (Discrete(2)):
    0 = mantener/extender la fase actual
    1 = pedir cambio de fase (si ya paso el verde minimo; si no, no hace nada)

Observacion (Box, 5 valores):
    [autos_parados_fase0/20, autos_parados_fase1/20, fase_actual (0 o 1),
     tiempo_en_fase/60, ocupacion_aguas_abajo_de_la_fase_actual (0-1)]

    El 5to valor es NUEVO: mide que tan llena esta la calle de salida de la
    fase que esta en verde ahora mismo, camino al proximo semaforo (ver
    tls_topology.py). Sin esto, el agente solo veia su propia cola y podia
    aprender a "resolverla" mandando un pelotón de autos justo a una calle
    ya saturada -- lo cual solo mueve el problema al semaforo de atras, no
    lo soluciona. Con esta señal en la observacion, el agente puede aprender
    a frenar el flujo hacia una calle llena en vez de forzarlo.

Recompensa: -(promedio de autos parados en las 2 aproximaciones) MENOS una
penalidad si la calle de salida de la fase activa esta cerca de saturarse
(ocupacion aguas abajo). Esto es lo que efectivamente "castiga" al agente
por empujar congestion al semaforo vecino, no solo por tener cola propia.
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
TARGET_TLS = "1135888071"
MIN_GREEN = 10
DECISION_DT = 5
SIM_END = 1800
DOWNSTREAM_PENALTY_WEIGHT = 6.0  # mismo orden de magnitud que adaptive_lib.DOWNSTREAM_WEIGHT


class SumoTLSEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, rou_path="osm.rou.xml", sim_end=SIM_END, use_gui=False, label="rlenv"):
        super().__init__()
        self.rou_path = os.path.join(PROJECT_DIR, rou_path)
        self.sim_end = sim_end
        self.use_gui = use_gui
        self.label = label

        with open(gl.NET_PATH) as f:
            net_text = f.read()
        gene_map, _ = gl.build_gene_map(net_text, [TARGET_TLS])
        entry = gene_map[0]
        self.phases = [{"state": s, "duration": d, "is_green": g} for d, s, g in entry["phases"]]
        self.green_indices = [i for i, p in enumerate(self.phases) if p["is_green"]]
        assert len(self.green_indices) == 2, "este entorno asume 2 fases verdes"
        self.yellow_of = {gi: (gi + 1) % len(self.phases) for gi in self.green_indices}

        frozen_text = al.build_frozen_net(net_text, [TARGET_TLS])
        self.net_path = os.path.join(PROJECT_DIR, f"net_rl_{label}.xml")
        with open(self.net_path, "w") as f:
            f.write(frozen_text)

        lanes_info = json.load(open(os.path.join(PROJECT_DIR, "tls_controlled_lanes.json")))
        lanes = lanes_info[TARGET_TLS]["lanes"]
        self.green_lanes = {}
        for gi in self.green_indices:
            state = self.phases[gi]["state"]
            s = set()
            for ch, lane in zip(state, lanes):
                if ch in "Gg":
                    s.add(lane)
            self.green_lanes[gi] = list(s)

        # carriles aguas abajo (hacia el proximo semaforo) por cada fase,
        # para medir si le estamos mandando autos a una calle saturada
        downstream_path = os.path.join(PROJECT_DIR, "tls_downstream_lanes.json")
        downstream_lanes = {}
        if os.path.exists(downstream_path):
            all_downstream = json.load(open(downstream_path))
            downstream_lanes = all_downstream.get(TARGET_TLS, {})
        self.downstream_of_phase = {}
        for gi in self.green_indices:
            dl = set()
            for lane in self.green_lanes[gi]:
                dl.update(downstream_lanes.get(lane, []))
            self.downstream_of_phase[gi] = list(dl)

        self.action_space = spaces.Discrete(2)
        self.observation_space = spaces.Box(low=0.0, high=10.0, shape=(5,), dtype=np.float32)

        self._conn_open = False
        self.current_phase = self.green_indices[0]
        self.time_in_phase = 0
        self.sim_time = 0

    def _halting(self, gi):
        return sum(traci.lane.getLastStepHaltingNumber(l) for l in self.green_lanes[gi])

    def _downstream_occupancy(self, gi):
        lanes = self.downstream_of_phase.get(gi)
        if not lanes:
            return 0.0
        return max(traci.lane.getLastStepOccupancy(l) for l in lanes)

    def _obs(self):
        h0 = self._halting(self.green_indices[0])
        h1 = self._halting(self.green_indices[1])
        phase_ind = 0.0 if self.current_phase == self.green_indices[0] else 1.0
        occ = self._downstream_occupancy(self.current_phase)
        return np.array([h0 / 20.0, h1 / 20.0, phase_ind, self.time_in_phase / 60.0, occ],
                         dtype=np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        if self._conn_open:
            try:
                traci.close()
            except Exception:
                pass
            self._conn_open = False

        binary = "sumo-gui" if self.use_gui else "sumo"
        traci.start([
            binary, "-n", self.net_path, "-r", self.rou_path,
            "-b", "0", "-e", str(self.sim_end),
            "--ignore-route-errors", "true", "--time-to-teleport", "300",
            "--no-step-log", "true", "--no-warnings", "true",
        ], label=self.label)
        self._conn_open = True
        self.current_phase = self.green_indices[0]
        traci.trafficlight.setPhase(TARGET_TLS, self.current_phase)
        self.time_in_phase = 0
        self.sim_time = 0
        return self._obs(), {}

    def step(self, action):
        halting_samples = []
        occ_samples = []
        elapsed = 0

        if action == 1 and self.time_in_phase >= MIN_GREEN:
            target = [gi for gi in self.green_indices if gi != self.current_phase][0]
            yi = self.yellow_of[self.current_phase]
            traci.trafficlight.setPhase(TARGET_TLS, yi)
            y_dur = int(self.phases[yi]["duration"])
            for _ in range(y_dur):
                traci.simulationStep()
                self.sim_time += 1
                elapsed += 1
                halting_samples.append(self._halting(self.green_indices[0]) + self._halting(self.green_indices[1]))
            traci.trafficlight.setPhase(TARGET_TLS, target)
            self.current_phase = target
            self.time_in_phase = 0

        for _ in range(DECISION_DT):
            traci.simulationStep()
            self.sim_time += 1
            self.time_in_phase += 1
            elapsed += 1
            halting_samples.append(self._halting(self.green_indices[0]) + self._halting(self.green_indices[1]))
            occ_samples.append(self._downstream_occupancy(self.current_phase))

        local_reward = -float(np.mean(halting_samples)) if halting_samples else 0.0
        downstream_penalty = DOWNSTREAM_PENALTY_WEIGHT * (float(np.mean(occ_samples)) if occ_samples else 0.0)
        reward = local_reward - downstream_penalty
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
