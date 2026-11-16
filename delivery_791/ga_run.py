"""
Algoritmo Genetico para optimizar los tiempos de las 12 intersecciones mas
congestionadas de la red SUMO (Mendoza, AR).

Escribe progreso a ga_log.jsonl (una linea JSON por evaluacion) y a
ga_progress.txt (resumen legible), y al final guarda el mejor genoma en
best_genome.json.
"""
import json
import random
import sys
import time
import os
import multiprocessing as mp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ga_lib as gl

RNG_SEED = 123
POP_SIZE = 8    # antes 24 -- reducido para que la corrida completa (POP_SIZE*N_GEN
                # evaluaciones) entre en ~horas en vez de ~3 dias, dado que cada
                # evaluacion individual tarda ~11-12 min en la red de 791 semaforos
N_GEN = 8       # antes 16 -- idem

# NUM_WORKERS: cuantas evaluaciones corren EN PARALELO (una por proceso de SUMO).
# Las evaluaciones de una misma generacion son independientes entre si, asi que
# se pueden repartir entre nucleos de CPU en vez de correr una detras de otra.
# Por defecto usa todos los nucleos disponibles, sin pasarse de POP_SIZE (no
# tiene sentido pedir mas workers que individuos a evaluar por generacion).
# OJO: cada worker de SUMO usa ~2.8 GB de RAM en esta red -- si tu PC tiene
# poca memoria, bajalo a mano (ej. NUM_WORKERS = 4) para no quedarte sin RAM.
NUM_WORKERS = min(POP_SIZE, os.cpu_count() or 1)
TOURNAMENT_K = 3
ELITISM = 2
CX_RATE = 0.8
MUT_RATE = 0.25
MUT_SIGMA = 8.0
SIM_END = 1800
LOADED_VEHICLES = 10286  # antes 820 -- corregido: es la cantidad real de vehiculos
                          # de osm.rou.xml (demanda moderada reescalada para 791
                          # semaforos). Si se deja en 820, la penalizacion por
                          # vehiculos no completados queda siempre en 0 porque
                          # completed siempre supera a 820 (bug silencioso).

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(PROJECT_DIR, "ga_log.jsonl")
PROGRESS_PATH = os.path.join(PROJECT_DIR, "ga_progress.txt")
BEST_PATH = os.path.join(PROJECT_DIR, "best_genome.json")

rng = random.Random(RNG_SEED)


def log(msg):
    with open(PROGRESS_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)


def evaluate(genome, net_text, gene_map, tag):
    new_text = gl.genome_to_net_text(net_text, gene_map, genome)
    net_path = os.path.join(PROJECT_DIR, f"net_eval_{tag}.xml")
    tripinfo_path = os.path.join(PROJECT_DIR, f"tripinfo_{tag}.xml")
    stats_path = os.path.join(PROJECT_DIR, f"stats_{tag}.xml")
    with open(net_path, "w", encoding="utf-8") as f:
        f.write(new_text)
    gl.run_sumo_eval(net_path, gl.ROU_PATH, SIM_END, tripinfo_path, stats_path)
    fitness, metrics = gl.compute_fitness(tripinfo_path, stats_path, LOADED_VEHICLES)
    # limpieza: con tags unicos por tarea paralela, sin esto se acumularian
    # ~750MB por evaluacion (net+tripinfo+stats) sin borrarse nunca
    for p in (net_path, tripinfo_path, stats_path):
        try:
            os.remove(p)
        except OSError:
            pass
    return fitness, metrics


# --- soporte para evaluar en paralelo (un proceso de SUMO por nucleo) ---
# Cada proceso worker carga net_text/gene_map UNA sola vez al arrancar
# (via _init_worker), no en cada evaluacion, para no perder tiempo
# releyendo/parseando el net.xml (250MB) en cada tarea.
_worker_net_text = None
_worker_gene_map = None


def _init_worker():
    global _worker_net_text, _worker_gene_map
    with open(gl.NET_PATH, encoding="utf-8") as f:
        _worker_net_text = f.read()
    scope = gl.load_scope()
    _worker_gene_map, _ = gl.build_gene_map(_worker_net_text, scope)


def _evaluate_task(args):
    genome, tag = args
    return evaluate(genome, _worker_net_text, _worker_gene_map, tag)


def tournament_select(pop, fitnesses, k):
    idxs = rng.sample(range(len(pop)), k)
    best = min(idxs, key=lambda i: fitnesses[i])
    return pop[best][:]


def crossover(p1, p2):
    if rng.random() > CX_RATE:
        return p1[:], p2[:]
    c1, c2 = [], []
    for a, b in zip(p1, p2):
        alpha = rng.random()
        c1.append(gl.clip(alpha * a + (1 - alpha) * b))
        c2.append(gl.clip(alpha * b + (1 - alpha) * a))
    return c1, c2


def mutate(ind):
    for i in range(len(ind)):
        if rng.random() < MUT_RATE:
            ind[i] = gl.clip(ind[i] + rng.gauss(0, MUT_SIGMA))
    return ind


def main():
    with open(gl.NET_PATH, encoding="utf-8") as f:
        net_text = f.read()
    scope = gl.load_scope()
    gene_map, n_genes = gl.build_gene_map(net_text, scope)

    orig_genome = []
    for entry in gene_map:
        for dur, state, is_green in entry["phases"]:
            if is_green:
                orig_genome.append(float(dur))

    log(f"=== INICIO GA === genes={n_genes} pop={POP_SIZE} gen={N_GEN} "
        f"workers={NUM_WORKERS} seed={RNG_SEED} start_time={time.strftime('%H:%M:%S')}")

    # Poblacion inicial: 1 = original (static), resto aleatorio dentro de bounds
    population = [orig_genome[:]]
    for _ in range(POP_SIZE - 1):
        population.append(gl.random_genome(n_genes, rng))

    best_ever = None
    best_ever_fit = float("inf")
    history = []

    eval_counter = 0
    t_start = time.time()

    pool = mp.Pool(processes=NUM_WORKERS, initializer=_init_worker)

    for gen in range(N_GEN):
        tasks = [(ind, f"g{gen}_i{i}") for i, ind in enumerate(population)]
        # reparte los POP_SIZE individuos de esta generacion entre los
        # NUM_WORKERS procesos disponibles -- esto es lo que da la mejora
        # de velocidad real (antes: uno por uno, ahora: varios a la vez)
        results = pool.map(_evaluate_task, tasks)

        fitnesses = []
        for i, (fit, metrics) in enumerate(results):
            eval_counter += 1
            fitnesses.append(fit)
            with open(LOG_PATH, "a", encoding="utf-8") as lf:
                lf.write(json.dumps({
                    "gen": gen, "ind": i, "eval": eval_counter,
                    "fitness": fit, **metrics
                }) + "\n")
            if fit < best_ever_fit:
                best_ever_fit = fit
                best_ever = population[i][:]

        gen_best = min(fitnesses)
        gen_avg = sum(fitnesses) / len(fitnesses)
        elapsed = time.time() - t_start
        history.append({"gen": gen, "best": gen_best, "avg": gen_avg, "elapsed_s": elapsed})
        log(f"[gen {gen:02d}] best={gen_best:.2f} avg={gen_avg:.2f} "
            f"best_ever={best_ever_fit:.2f} elapsed={elapsed:.0f}s evals={eval_counter}")

        # --- nueva generacion ---
        ranked = sorted(range(len(population)), key=lambda i: fitnesses[i])
        new_pop = [population[ranked[0]][:], population[ranked[1]][:]][:ELITISM]
        while len(new_pop) < POP_SIZE:
            p1 = tournament_select(population, fitnesses, TOURNAMENT_K)
            p2 = tournament_select(population, fitnesses, TOURNAMENT_K)
            c1, c2 = crossover(p1, p2)
            mutate(c1)
            mutate(c2)
            new_pop.append(c1)
            if len(new_pop) < POP_SIZE:
                new_pop.append(c2)
        population = new_pop

    pool.close()
    pool.join()

    with open(BEST_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "genome": best_ever,
            "fitness": best_ever_fit,
            "gene_map_ids": [e["id"] for e in gene_map],
            "gene_map_n_green": [e["n_green"] for e in gene_map],
            "history": history,
        }, f, indent=2)

    log(f"=== FIN GA === best_fitness={best_ever_fit:.2f} "
        f"total_time={time.time()-t_start:.0f}s total_evals={eval_counter}")


if __name__ == "__main__":
    main()