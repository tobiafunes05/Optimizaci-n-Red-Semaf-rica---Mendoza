"""
Identifica las intersecciones semaforizadas mas congestionadas para una
demanda de trafico dada, y guarda un archivo de "scope" (lista de ids de
semaforo) para usar con ga_run.py.

Uso:
    python3 find_critical_tls.py <archivo_rutas.rou.xml> <nombre_escenario> [top_n]

Ejemplo (para el trafico denso que generaste con randomTrips.py):
    python3 find_critical_tls.py osm_denso.rou.xml denso 12

Esto corre una simulacion base (semaforos originales, actuados) con esa
demanda, mide la cola en cada semaforo, y guarda:
    - top_tls_<escenario>_full.json  (ranking completo, todas las intersecciones)
    - scope_tls_<escenario>.json     (las top_n mas congestionadas -> usar en el GA)
"""
import sys
import os
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ga_lib as gl

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    rou_path = sys.argv[1]
    scenario = sys.argv[2]
    top_n = int(sys.argv[3]) if len(sys.argv) > 3 else 12

    queue_path = f"queue_baseline_{scenario}.xml"
    tripinfo_path = f"tripinfo_baseline_{scenario}.xml"
    stats_path = f"stats_baseline_{scenario}.xml"

    print(f"1) Corriendo simulacion base (semaforos originales) con {rou_path} ...")
    cmd = [
        gl.SUMO_BIN, "-n", gl.NET_PATH, "-r", rou_path,
        "-b", "0", "-e", "1800",
        "--ignore-route-errors", "true", "--time-to-teleport", "300",
        "--no-step-log", "true", "--no-warnings", "true",
        "--tripinfo-output", tripinfo_path,
        "--statistic-output", stats_path,
        "--queue-output", queue_path,
    ]
    subprocess.run(cmd, check=True)

    print("2) Analizando colas por semaforo ...")
    import sumolib
    net = sumolib.net.readNet(gl.NET_PATH)
    lane_to_tls = {}
    for tls in net.getTrafficLights():
        for conn in tls.getConnections():
            lane_to_tls[conn[0].getID()] = tls.getID()

    tree = ET.parse(queue_path)
    agg = defaultdict(float)
    for step in tree.getroot().findall("data"):
        lanes = step.find("lanes")
        if lanes is None:
            continue
        for lane in lanes.findall("lane"):
            tlsid = lane_to_tls.get(lane.get("id"))
            if tlsid:
                agg[tlsid] += float(lane.get("queueing_time", 0))

    ranked = sorted(agg.items(), key=lambda x: -x[1])
    total = sum(agg.values()) or 1
    cum = 0
    print(f"\nTop {top_n} intersecciones mas congestionadas ({scenario}):")
    for i, (tid, val) in enumerate(ranked[:top_n]):
        cum += val
        print(f"  {i+1:2d}. {tid}  (acumulado {cum/total*100:.1f}% de la congestion total)")

    scope = [t for t, _ in ranked[:top_n]]
    json.dump(scope, open(f"scope_tls_{scenario}.json", "w"))
    json.dump(ranked, open(f"top_tls_{scenario}_full.json", "w"))
    print(f"\nGuardado: scope_tls_{scenario}.json  (usar este archivo en ga_run.py)")

if __name__ == "__main__":
    main()
