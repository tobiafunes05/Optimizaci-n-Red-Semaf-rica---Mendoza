"""
Corre el escenario "tiempo fijo como linea base" (scenario 1 de la
comparacion final: fijo vs. RL adaptativo): los 12 semaforos criticos de
scope_tls_top12.json, forzados a tiempo fijo (type="static") con sus
duraciones ORIGINALES (las que trae el mapa descargado, antes de cualquier
optimizacion) -- exactamente la misma definicion de "Static" que ya se uso
en el informe original del algoritmo genetico (seccion 5.2). Corre con
emisiones activadas para poder despues comparar CO2 contra el escenario RL.

Uso:
    python3 baseline_fixed_run.py <rou_file> <tag> <loaded_vehicles>

Ejemplo:
    python3 baseline_fixed_run.py osm.rou.xml moderado 820
"""
import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ga_lib as gl

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    rou_file = sys.argv[1]
    tag = sys.argv[2]
    loaded_vehicles = int(sys.argv[3])
    sim_end = 1800

    with open(gl.NET_PATH) as f:
        net_text = f.read()
    scope = gl.load_scope()
    gene_map, n_genes = gl.build_gene_map(net_text, scope)

    orig_genome = []
    for entry in gene_map:
        for dur, state, is_green in entry["phases"]:
            if is_green:
                orig_genome.append(float(dur))

    static_text = gl.genome_to_net_text(net_text, gene_map, orig_genome)
    net_path = os.path.join(PROJECT_DIR, f"net_baseline_fixed_{tag}.xml")
    with open(net_path, "w") as f:
        f.write(static_text)

    tripinfo_path = os.path.join(PROJECT_DIR, f"tripinfo_baseline_fixed_{tag}.xml")
    stats_path = os.path.join(PROJECT_DIR, f"stats_baseline_fixed_{tag}.xml")

    t0 = time.time()
    gl.run_sumo_eval(
        net_path, os.path.join(PROJECT_DIR, rou_file), sim_end, tripinfo_path, stats_path,
        extra_args=["--device.emissions.probability", "1.0"],
    )
    print(f"Listo en {time.time()-t0:.1f}s reales", flush=True)

    fitness, metrics = gl.compute_full_metrics(tripinfo_path, stats_path, loaded_vehicles, sim_end)
    print(f"BASELINE FIJO ({tag}): fitness={fitness:.2f}  {metrics}", flush=True)

    json.dump({"tag": tag, "scenario": "tiempo_fijo_baseline", "fitness": fitness, **metrics},
              open(os.path.join(PROJECT_DIR, f"result_baseline_fixed_{tag}.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
