"""
Corre la simulacion con control ADAPTATIVO en tiempo real (max-pressure/gap-out,
coordinado con presion neta -- ver adaptive_lib.py) sobre las 12 intersecciones
criticas, via TraCI. Uso:

    python3 adaptive_run.py <rou_file> <tag> <loaded_vehicles> [--no-coord]

Ejemplo (version coordinada, la nueva -- por defecto):
    python3 adaptive_run.py osm.rou.xml moderado_coord 820

Ejemplo (version original, SIN coordinar entre semaforos vecinos -- para
comparar "antes vs despues" con exactamente el mismo motor):
    python3 adaptive_run.py osm.rou.xml moderado_nocoord 820 --no-coord

Requiere haber corrido antes `python3 tls_topology.py` una vez (genera
tls_downstream_lanes.json, usado para que cada semaforo del scope vigile la
ocupacion de su calle de salida y no la sature empujandole autos a un
semaforo vecino que ya esta saturado).
"""
import os
import sys
import json
import time

sys.path.insert(0, os.environ["SUMO_HOME"] + "/tools")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import traci
import ga_lib as gl
import adaptive_lib as al

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    rou_file = sys.argv[1]
    tag = sys.argv[2]
    loaded_vehicles = int(sys.argv[3])
    no_coord = "--no-coord" in sys.argv
    sim_end = 1800

    with open(gl.NET_PATH, encoding="utf-8") as f:
        net_text = f.read()
    scope = gl.load_scope()
    gene_map, n_genes = gl.build_gene_map(net_text, scope)

    frozen_text = al.build_frozen_net(net_text, scope)
    frozen_path = os.path.join(PROJECT_DIR, f"net_adaptive_{tag}.xml")
    with open(frozen_path, "w", encoding="utf-8") as f:
        f.write(frozen_text)

    lanes_info = json.load(open(os.path.join(PROJECT_DIR, "tls_controlled_lanes.json"), encoding="utf-8"))

    downstream_path = os.path.join(PROJECT_DIR, "tls_downstream_lanes.json")
    if no_coord:
        downstream_info = {}
        print("Coordinacion con vecinos: DESACTIVADA (--no-coord)", flush=True)
    elif os.path.exists(downstream_path):
        downstream_info = json.load(open(downstream_path, encoding="utf-8"))
        print("Coordinacion con vecinos: ACTIVADA (tls_downstream_lanes.json encontrado)", flush=True)
    else:
        downstream_info = {}
        print("Coordinacion con vecinos: DESACTIVADA (correr 'python3 tls_topology.py' primero)", flush=True)

    tripinfo_path = os.path.join(PROJECT_DIR, f"tripinfo_adaptive_{tag}.xml")
    stats_path = os.path.join(PROJECT_DIR, f"stats_adaptive_{tag}.xml")

    t0 = time.time()
    traci.start([
        "sumo", "-n", frozen_path, "-r", rou_file, "-b", "0", "-e", str(sim_end),
        "--ignore-route-errors", "true", "--time-to-teleport", "300",
        "--no-step-log", "true", "--no-warnings", "true",
        "--tripinfo-output", tripinfo_path,
        "--statistic-output", stats_path,
    ])

    controllers = []
    for entry in gene_map:
        tid = entry["id"]
        phases = [{"state": s, "duration": d, "is_green": g} for d, s, g in entry["phases"]]
        lanes = lanes_info[tid]["lanes"]
        downstream_lanes = downstream_info.get(tid)
        controllers.append(al.AdaptiveController(tid, phases, lanes, downstream_lanes=downstream_lanes))

    def get_halting(lane):
        return traci.lane.getLastStepHaltingNumber(lane)

    def get_occupancy(lane):
        return traci.lane.getLastStepOccupancy(lane)

    def set_phase(tls_id, phase_idx):
        traci.trafficlight.setPhase(tls_id, phase_idx)

    step = 0
    while step < sim_end:
        traci.simulationStep()
        for c in controllers:
            c.step(get_halting, set_phase, get_occupancy)
        step += 1
        if step % 300 == 0:
            print(f"  ... {step}/{sim_end}s simulados", flush=True)

    traci.close()
    print(f"Listo en {time.time()-t0:.1f}s reales", flush=True)

    fitness, metrics = gl.compute_fitness(tripinfo_path, stats_path, loaded_vehicles)
    print(f"ADAPTATIVO ({tag}): fitness={fitness:.2f}  {metrics}", flush=True)

    json.dump({"tag": tag, "fitness": fitness, **metrics},
              open(os.path.join(PROJECT_DIR, f"result_adaptive_{tag}.json"), "w", encoding="utf-8"))


if __name__ == "__main__":
    main()