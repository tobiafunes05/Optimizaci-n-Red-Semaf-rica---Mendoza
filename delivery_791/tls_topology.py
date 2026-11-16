"""
Calcula la topologia de vecindad entre semaforos de la red, a partir de
osm.net.xml (con sumolib). Esto es lo que le falta al proyecto original
para poder coordinar semaforos vecinos: adaptive_lib.py y sumo_rl_env.py
controlaban cada interseccion de forma totalmente aislada, sin saber que
pasaba en la calle de salida ni en el semaforo de al lado.

Genera dos archivos:

  tls_downstream_lanes.json
      Para cada semaforo y cada uno de sus carriles de entrada (controlados
      por una fase verde), la lista de carriles "aguas abajo" (por donde
      sigue ese movimiento) hasta llegar al proximo semaforo o hasta un
      limite de saltos. Sirve para medir, en tiempo real via TraCI, si la
      calle de salida de un semaforo ya esta saturada -- y si lo esta, no
      conviene seguir mandandole mas autos (eso es lo que causa que la
      congestion se "corra" al semaforo de atras).

  tls_adjacency.json
      Para cada semaforo, sus vecinos semaforizados directos (upstream =
      le mandan autos, downstream = les manda autos) y, cuando no hay uno
      directo, el semaforo mas cercano en cada sentido siguiendo la red
      (salteando esquinas sin semaforo). Es mas que nada para entender/
      documentar la red, no lo usan los controladores en tiempo real.

Uso:
    python3 tls_topology.py
"""
import os
import json
import sys

sys.path.insert(0, os.environ["SUMO_HOME"] + "/tools")
import sumolib

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
NET_PATH = os.path.join(PROJECT_DIR, "osm.net.xml")
MAX_HOPS = 6  # cuantos carriles seguir aguas abajo antes de rendirse


def build_downstream_lanes(net, tls_ids, max_hops=MAX_HOPS):
    tls_objs = {t.getID(): t for t in net.getTrafficLights()}
    result = {}
    for tid in tls_ids:
        t = tls_objs[tid]
        # carriles de entrada controlados por este semaforo (los que
        # aparecen en el string de estado de sus fases)
        in_lanes = sorted({fl.getID() for fl, tl, link in t.getConnections()})
        per_lane = {}
        for lane_id in in_lanes:
            lane = net.getLane(lane_id)
            chain = []
            frontier = [lane]
            seen = {lane_id}
            for _ in range(max_hops):
                nxt_frontier = []
                stop = False
                for lseg in frontier:
                    for conn in lseg.getOutgoing():
                        tolane = conn.getToLane()
                        tid_ = tolane.getID()
                        if tid_ in seen:
                            continue
                        seen.add(tid_)
                        chain.append(tid_)
                        to_node = tolane.getEdge().getToNode().getID()
                        if to_node in tls_objs:
                            # llegamos al proximo semaforo: no hace falta
                            # seguir por esta rama
                            stop = True
                        else:
                            nxt_frontier.append(tolane)
                if stop:
                    break
                frontier = nxt_frontier
                if not frontier:
                    break
            per_lane[lane_id] = chain
        result[tid] = per_lane
    return result


def build_adjacency(net, tls_ids):
    tls_objs = {t.getID(): t for t in net.getTrafficLights()}
    adjacency = {}
    for tid in tls_ids:
        t = tls_objs[tid]
        upstream_direct = set()
        downstream_direct = set()
        for fl, tl, link in t.getConnections():
            fromnode = fl.getEdge().getFromNode().getID()
            if fromnode in tls_objs and fromnode != tid:
                upstream_direct.add(fromnode)
            tonode = tl.getEdge().getToNode().getID()
            if tonode in tls_objs and tonode != tid:
                downstream_direct.add(tonode)
        adjacency[tid] = {
            "upstream": sorted(upstream_direct),
            "downstream": sorted(downstream_direct),
        }
    return adjacency


def main():
    net = sumolib.net.readNet(NET_PATH)
    tls_ids = [t.getID() for t in net.getTrafficLights()]

    downstream_lanes = build_downstream_lanes(net, tls_ids)
    json.dump(downstream_lanes, open(os.path.join(PROJECT_DIR, "tls_downstream_lanes.json"), "w"))

    adjacency = build_adjacency(net, tls_ids)
    json.dump(adjacency, open(os.path.join(PROJECT_DIR, "tls_adjacency.json"), "w"), indent=1)

    n_direct = sum(1 for v in adjacency.values() if v["upstream"] or v["downstream"])
    print(f"{len(tls_ids)} semaforos en la red.")
    print(f"{n_direct} tienen al menos un vecino semaforizado directo (sin esquinas sin semaforo en el medio).")
    print("Guardado: tls_downstream_lanes.json, tls_adjacency.json")


if __name__ == "__main__":
    main()
