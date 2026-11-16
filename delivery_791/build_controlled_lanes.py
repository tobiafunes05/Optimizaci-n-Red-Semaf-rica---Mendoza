"""
Genera (o regenera) tls_controlled_lanes.json para un scope de semaforos
dado, usando TraCI. Esto es lo que faltaba en el proyecto original: los
scripts (adaptive_run.py, sumo_rl_env.py, sumo_rl_multiagent_env.py)
necesitan este archivo, pero no habia ningun script incluido que lo
generara para una red o un scope nuevo -- se habia armado a mano para los
12 semaforos originales.

Para cada semaforo del scope guarda:
  - "lanes": los carriles controlados, EN EL MISMO ORDEN que los caracteres
    del string de estado de sus fases (position i del string <-> lanes[i]).
    Se obtiene con traci.trafficlight.getControlledLanes(), que ya devuelve
    la lista en orden de indice de link (con carriles repetidos si un mismo
    carril tiene mas de un movimiento).
  - "phases": lista de fases con su "state", "duration", "minDur", "maxDur"
    (los dos ultimos igual a "duration" si el semaforo es de tipo estatico).

Uso:
    python3 build_controlled_lanes.py <net.xml> <scope.json> <salida.json>

Ejemplo (regenerar para el scope de 791 semaforos, en la carpeta del
proyecto reescalado):
    python3 build_controlled_lanes.py osm.net.xml scope_tls_791.json tls_controlled_lanes.json
"""
import os
import sys
import json

sys.path.insert(0, os.environ["SUMO_HOME"] + "/tools")
import traci


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)

    net_path, scope_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

    with open(scope_path) as f:
        scope = json.load(f)

    print(f"Arrancando SUMO (sin rutas) para leer la topologia de {len(scope)} semaforos...")
    traci.start(["sumo", "-n", net_path, "--no-step-log", "true", "--no-warnings", "true"])

    result = {}
    missing = []
    for i, tid in enumerate(scope, 1):
        try:
            lanes = list(traci.trafficlight.getControlledLanes(tid))
            logics = traci.trafficlight.getAllProgramLogics(tid)
        except traci.exceptions.TraCIException:
            missing.append(tid)
            continue

        # Si el semaforo tiene varios programas (ej. original + uno propio
        # ya cargado), nos quedamos con el primero -- es el que trae la red
        # tal cual la exporto osmWebWizard.
        logic = logics[0]
        phases = []
        for p in logic.phases:
            phases.append({
                "state": p.state,
                "duration": float(p.duration),
                "minDur": float(getattr(p, "minDur", p.duration)),
                "maxDur": float(getattr(p, "maxDur", p.duration)),
            })
        result[tid] = {"lanes": lanes, "phases": phases}

        if i % 100 == 0 or i == len(scope):
            print(f"  ... {i}/{len(scope)} procesados", flush=True)

    traci.close()

    with open(out_path, "w") as f:
        json.dump(result, f)

    print(f"\nGuardado: {out_path} ({len(result)} semaforos)")
    if missing:
        print(f"AVISO: {len(missing)} ids del scope no se encontraron en la red "
              f"(revisa que scope.json corresponda a este net.xml): {missing[:10]}"
              f"{' ...' if len(missing) > 10 else ''}")


if __name__ == "__main__":
    main()
