"""
Control adaptativo en tiempo real de semaforos via TraCI (max-pressure /
gap-out): en vez de un plan de tiempos fijo, en cada paso de simulacion se
mide cuantos vehiculos estan esperando en cada fase, y se decide extender,
cortar o cambiar de fase segun esa demanda real -- "si no pasa nadie, no
se queda en verde; si hay cola, se le da mas tiempo".

Esto reemplaza al algoritmo genetico (que buscaba UN plan de tiempos fijo
offline) por un controlador que decide en cada instante, usando el estado
real del trafico -- el mismo principio que usan los sistemas de "adaptive
traffic signal control" citados en la seccion 2.2 del informe (aunque ahi
la politica es una red neuronal entrenada con RL; aca es una politica
programada a mano tipo "max-pressure", mas simple pero del mismo espiritu).

COORDINACION ENTRE SEMAFOROS VECINOS (spillback-aware max-pressure)
---------------------------------------------------------------------
La version original de este controlador decidia mirando SOLO la cola de
autos parados en las propias aproximaciones -- cada semaforo optimizaba su
propia esquina de forma totalmente aislada. El problema (parte 8.x del
informe, "trabajo futuro"): si un semaforo prioriza la fase con mas cola y
la vacia rapido, esos autos van a parar a la cuadra siguiente. Si esa
cuadra ya esta saturada, se forma una cola que termina "atascando" tambien
al semaforo de donde salieron (spillback) -- o al semaforo de atras de ese.

La solucion que se aplica aca es la variante "con presion neta" del propio
max-pressure (Varaiya, 2013): en vez de mirar solo cuantos autos estan
esperando para entrar a una fase (presion local), tambien se mide la
ocupacion de los carriles de SALIDA de esa fase (aguas abajo, hacia el
proximo semaforo -- ver tls_topology.py / tls_downstream_lanes.json) y se
resta como penalidad. Asi, una fase con mucha cola local pero cuya calle de
salida ya esta saturada deja de ser la mas atractiva, y el controlador le
da paso a otro movimiento -- evita "empujar" el problema al semaforo de
atras en lugar de resolverlo. Ademas, si la salida de la fase actual esta
realmente al borde del colapso (SPILLBACK_OCC), se fuerza el corte de
verde ni bien se cumple el minimo, en vez de esperar a MAX_GREEN.
"""
import os
import re
import json

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

MIN_GREEN = 10       # segundos minimos de verde antes de poder cortar
MAX_GREEN = 60       # segundos maximos de verde aunque siga habiendo cola
SWITCH_MARGIN = 2    # otra fase necesita al menos esta cantidad extra de autos en cola para "ganarle" a la actual
STARVE_LIMIT = 90    # si una fase no se sirve hace mas de esto (segundos), se la fuerza igual (evita inanicion)

# --- coordinacion con semaforos vecinos ---
DOWNSTREAM_WEIGHT = 6.0   # cuantos "autos de presion" vale 1.0 de ocupacion aguas abajo (0-1)
SPILLBACK_OCC = 0.80      # ocupacion aguas abajo a partir de la cual se considera "por saturarse"


def build_frozen_net(net_text, tls_ids, frozen_duration=9999):
    """Devuelve el net.xml (como texto) con los tls_ids dados congelados:
    type='static' y duracion enorme en cada fase, para que SUMO nunca los
    cambie solo -- el cambio de fase lo hace por completo nuestro script
    via TraCI (traci.trafficlight.setPhase)."""
    pieces = []
    cursor = 0
    blocks = []
    for tid in tls_ids:
        pattern = re.compile(r'<tlLogic id="%s"[^>]*>(.*?)</tlLogic>' % re.escape(tid), re.DOTALL)
        m = pattern.search(net_text)
        if m is None:
            raise ValueError(f"No se encontro tlLogic {tid}")
        blocks.append((m.start(), m.end(), tid, m.group(1)))
    blocks.sort(key=lambda b: b[0])

    phase_re = re.compile(r'<phase\s+duration="(\d+)"\s+state="([^"]+)"[^/]*/>')
    for start, end, tid, block in blocks:
        pieces.append(net_text[cursor:start])
        lines = [f'<tlLogic id="{tid}" type="static" programID="0" offset="0">']
        for dur, state in phase_re.findall(block):
            lines.append(f'    <phase duration="{frozen_duration}" state="{state}"/>')
        lines.append("</tlLogic>")
        pieces.append("\n".join(lines))
        cursor = end
    pieces.append(net_text[cursor:])
    return "".join(pieces)


class AdaptiveController:
    """Un controlador max-pressure/gap-out para un semaforo, con presion neta
    (local - ocupacion aguas abajo) para coordinarse con el semaforo siguiente."""

    def __init__(self, tls_id, phases, lanes, downstream_lanes=None):
        # phases: lista de dicts {"state":..., "duration":..., "is_green": bool}
        # en el MISMO orden que en el net.xml (green, yellow, green, yellow, ...)
        # downstream_lanes: dict {lane_id de entrada -> [lane_ids aguas abajo]}
        #   (salida de tls_topology.py). Si es None, el controlador se
        #   comporta exactamente como la version original (sin coordinar).
        self.id = tls_id
        self.phases = phases
        self.lanes = lanes  # lista de lane-ids, en el mismo orden que los caracteres de "state"
        self.downstream_lanes = downstream_lanes or {}
        self.green_indices = [i for i, p in enumerate(phases) if p["is_green"]]
        self.yellow_of = {}  # green_index -> yellow_index que le sigue
        for gi in self.green_indices:
            yi = (gi + 1) % len(phases)
            self.yellow_of[gi] = yi
        # precomputar, para cada fase verde, el set de carriles con luz verde
        self.green_lanes = {}
        for gi in self.green_indices:
            state = phases[gi]["state"]
            s = set()
            for ch, lane in zip(state, lanes):
                if ch in "Gg":
                    s.add(lane)
            self.green_lanes[gi] = list(s)

        # precomputar, para cada fase verde, el set de carriles aguas abajo
        # (hacia el proximo semaforo) que hay que vigilar antes de mandarle
        # mas autos con esta fase
        self.downstream_of_phase = {}
        for gi in self.green_indices:
            dl = set()
            for lane in self.green_lanes[gi]:
                dl.update(self.downstream_lanes.get(lane, []))
            self.downstream_of_phase[gi] = list(dl)

        self.current_phase = self.green_indices[0]
        self.mode = "green"       # "green" o "yellow"
        self.green_timer = 0
        self.yellow_timer = 0
        self.target_phase = None
        # anti-inanicion: hace cuanto no se sirve cada fase verde
        self.since_served = {gi: 0 for gi in self.green_indices}
        self.since_served[self.current_phase] = 0

    def local_pressure(self, gi, get_halting):
        return sum(get_halting(lane) for lane in self.green_lanes[gi])

    def downstream_occupancy(self, gi, get_occupancy):
        """Ocupacion (0-1) de la calle de salida de la fase gi. 0 si no hay
        info de topologia (comportamiento original) o si no hay calle de
        salida vigilable (p. ej. la fase sale de la red)."""
        lanes = self.downstream_of_phase.get(gi)
        if not lanes or get_occupancy is None:
            return 0.0
        return max(get_occupancy(lane) for lane in lanes)

    def pressure(self, gi, get_halting, get_occupancy=None):
        """Presion neta: cola local menos una penalidad si la calle de
        salida de esta fase ya esta saturada (para no empujarle mas autos
        a un semaforo vecino que ya esta al limite)."""
        local = self.local_pressure(gi, get_halting)
        occ = self.downstream_occupancy(gi, get_occupancy)
        return local - DOWNSTREAM_WEIGHT * occ

    def step(self, get_halting, set_phase, get_occupancy=None):
        if self.mode == "yellow":
            self.yellow_timer -= 1
            if self.yellow_timer <= 0:
                set_phase(self.id, self.target_phase)
                self.current_phase = self.target_phase
                self.since_served[self.current_phase] = 0
                self.mode = "green"
                self.green_timer = 0
            return

        # mode == "green"
        self.green_timer += 1
        for gi in self.green_indices:
            if gi != self.current_phase:
                self.since_served[gi] += 1

        cur_p = self.pressure(self.current_phase, get_halting, get_occupancy)
        others = [(gi, self.pressure(gi, get_halting, get_occupancy))
                  for gi in self.green_indices if gi != self.current_phase]
        best_gi, best_p = max(others, key=lambda x: x[1]) if others else (None, -1)

        # anti-inanicion: si alguna fase lleva mucho tiempo sin servirse, tiene prioridad
        starved = [gi for gi, t in self.since_served.items() if gi != self.current_phase and t >= STARVE_LIMIT]
        # anti-spillback: si la calle de salida de la fase actual ya esta
        # casi saturada, cortamos apenas se cumpla el verde minimo, aunque
        # todavia tenga cola local -- seguir sirviendola solo la empeora.
        cur_downstream_occ = self.downstream_occupancy(self.current_phase, get_occupancy)
        spilling_back = cur_downstream_occ >= SPILLBACK_OCC

        if starved and self.green_timer >= MIN_GREEN:
            best_gi = max(starved, key=lambda gi: self.since_served[gi])
            best_p = self.pressure(best_gi, get_halting, get_occupancy)
            should_switch = True
        else:
            should_switch = False
            if self.green_timer >= MAX_GREEN:
                should_switch = True
            elif self.green_timer >= MIN_GREEN:
                if spilling_back and best_gi is not None:
                    should_switch = True
                elif cur_p <= 0 and best_p > 0:
                    should_switch = True
                elif best_p >= cur_p + SWITCH_MARGIN:
                    should_switch = True

        if should_switch and best_gi is not None:
            yi = self.yellow_of[self.current_phase]
            set_phase(self.id, yi)
            self.target_phase = best_gi
            self.mode = "yellow"
            self.yellow_timer = int(self.phases[yi]["duration"])
