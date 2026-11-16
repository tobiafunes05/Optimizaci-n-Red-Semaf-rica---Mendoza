"""
Utilidades para optimizar tiempos de semaforos en una red SUMO
mediante un Algoritmo Genetico (metaheuristica).

Autor: generado para el proyecto de investigacion de Fran (Mendoza, Argentina)
"""
import os
import re
import subprocess
import xml.etree.ElementTree as ET
import random
import json

SUMO_HOME = os.environ["SUMO_HOME"]
SUMO_BIN = os.path.join(SUMO_HOME, "bin", "sumo")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
NET_PATH = os.path.join(PROJECT_DIR, "osm.net.xml")
ROU_PATH = os.path.join(PROJECT_DIR, "osm.rou.xml")

if not os.path.exists(NET_PATH) and os.path.exists(NET_PATH + ".gz"):
    import gzip
    import shutil
    print("Descomprimiendo osm.net.xml.gz -> osm.net.xml ...", flush=True)
    with gzip.open(NET_PATH + ".gz", "rb") as _f_in, open(NET_PATH, "wb") as _f_out:
        shutil.copyfileobj(_f_in, _f_out)

GENE_MIN = 8    # segundos, minimo de verde por fase (seguridad peatonal)
GENE_MAX = 70   # segundos, maximo de verde por fase (evita ciclos excesivos)

# Penalizaciones para la funcion de fitness (en "segundos equivalentes")
PENALTY_NOT_COMPLETED = 600.0   # vehiculo que no llego a destino en la ventana simulada
PENALTY_TELEPORT = 30.0         # vehiculo que tuvo que ser "teletransportado" por atasco


def load_scope(scope_path=os.path.join(PROJECT_DIR, "scope_tls_791.json")):
    # OJO: scope_tls.json quedo sobreescrito en algun momento con el ranking
    # completo de las 63 intersecciones (en vez del subconjunto de 12 que se
    # uso para el GA/adaptativo/RL, que coincide con tls_controlled_lanes.json
    # y con best_genome.json). scope_tls_top12.json tiene esos 12 ids
    # originales, asi que es lo que hay que usar por defecto en todo el
    # proyecto (ga_run.py, adaptive_run.py, etc.) -- si se corre con
    # scope_tls.json revienta con KeyError en tls_controlled_lanes.json.
    with open(scope_path, encoding="utf-8") as f:
        return json.load(f)


def build_gene_map(net_text, tls_ids):
    """
    Para cada semaforo en tls_ids, ubica su bloque <tlLogic> en el texto del
    net.xml y devuelve la estructura necesaria para reconstruirlo con nuevas
    duraciones de fase verde.

    Devuelve:
      gene_map: lista de dicts, uno por tls, con:
        - id, start, end (posicion del bloque completo <tlLogic...>...</tlLogic> en el texto)
        - phases: lista de (duration, state, is_green) en orden
        - n_green: cantidad de fases verdes (== genes que le corresponden)
      total_genes: cantidad total de genes (suma de n_green de todos los tls)
    """
    phase_re = re.compile(r'<phase\s+duration="(\d+)"\s+state="([^"]+)"[^/]*/>')
    gene_map = []
    total_genes = 0
    for tid in tls_ids:
        pattern = re.compile(
            r'<tlLogic id="%s"[^>]*>(.*?)</tlLogic>' % re.escape(tid), re.DOTALL
        )
        m = pattern.search(net_text)
        if m is None:
            raise ValueError(f"No se encontro tlLogic para id={tid}")
        block = m.group(1)
        phases = []
        for pm in phase_re.finditer(block):
            dur, state = pm.group(1), pm.group(2)
            is_green = ("y" not in state) and ("Y" not in state)
            phases.append([int(dur), state, is_green])
        n_green = sum(1 for p in phases if p[2])
        gene_map.append({
            "id": tid,
            "start": m.start(),
            "end": m.end(),
            "phases": phases,
            "n_green": n_green,
        })
        total_genes += n_green
    return gene_map, total_genes


def genome_to_net_text(net_text, gene_map, genome):
    """Reconstruye el net.xml (como string) aplicando el genoma (duraciones
    de fase verde) a los semaforos del scope. Las fases amarillas quedan
    igual que en la red original. Los tlLogic optimizados se marcan type="static".

    IMPORTANTE: el orden de los genes en `genome` sigue el orden de
    `gene_map` (que a su vez sigue tls_ids, ordenado por congestion), NO el
    orden en que los bloques aparecen dentro del archivo. Por eso primero
    asignamos a cada entry su porcion de genoma, y recien despues procesamos
    los bloques ordenados por posicion en el texto (start) para poder
    reconstruir el archivo sin solapamientos ni saltos hacia atras.
    """
    # 1) asignar a cada entry su slice del genoma (en el orden de gene_map)
    idx = 0
    for entry in gene_map:
        entry["_gene_slice"] = genome[idx: idx + entry["n_green"]]
        idx += entry["n_green"]
    assert idx == len(genome), f"genoma mal dimensionado: uso {idx} de {len(genome)}"

    # 2) reconstruir el texto procesando los bloques en orden de posicion
    ordered = sorted(gene_map, key=lambda e: e["start"])
    pieces = []
    cursor = 0
    for entry in ordered:
        pieces.append(net_text[cursor:entry["start"]])
        gvals = iter(entry["_gene_slice"])
        lines = [f'<tlLogic id="{entry["id"]}" type="static" programID="0" offset="0">']
        for dur, state, is_green in entry["phases"]:
            if is_green:
                new_dur = int(round(next(gvals)))
            else:
                new_dur = dur
            lines.append(f'    <phase duration="{new_dur}" state="{state}"/>')
        lines.append("</tlLogic>")
        pieces.append("\n".join(lines))
        cursor = entry["end"]
    pieces.append(net_text[cursor:])
    return "".join(pieces)


def run_sumo_eval(net_text_path, rou_path, end_time, tripinfo_path, stats_path,
                   extra_args=None):
    cmd = [
        SUMO_BIN,
        "-n", net_text_path,
        "-r", rou_path,
        "-b", "0", "-e", str(end_time),
        "--ignore-route-errors", "true",
        "--time-to-teleport", "300",
        "--no-step-log", "true",
        "--no-warnings", "true",
        "--tripinfo-output", tripinfo_path,
        "--statistic-output", stats_path,
    ]
    if extra_args:
        cmd += extra_args
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def compute_fitness(tripinfo_path, stats_path, loaded_vehicles):
    tree = ET.parse(tripinfo_path)
    trips = tree.getroot().findall("tripinfo")
    completed = len(trips)
    total_time_loss = sum(float(t.get("timeLoss")) for t in trips)

    stree = ET.parse(stats_path)
    teleports = int(stree.getroot().find("teleports").get("total"))

    not_completed = max(loaded_vehicles - completed, 0)
    penalty = not_completed * PENALTY_NOT_COMPLETED + teleports * PENALTY_TELEPORT
    fitness = (total_time_loss + penalty) / max(loaded_vehicles, 1)

    metrics = {
        "completed": completed,
        "not_completed": not_completed,
        "teleports": teleports,
        "mean_time_loss_completed": total_time_loss / completed if completed else None,
        "fitness": fitness,
    }
    return fitness, metrics


def compute_full_metrics(tripinfo_path, stats_path, loaded_vehicles, sim_duration_s):
    """Igual que compute_fitness, mas las 3 metricas que pide la comparacion
    final (tiempo fijo vs. RL adaptativo): tiempo promedio de espera, flujo
    de vehiculos por hora, y emisiones de CO2 (si la corrida se hizo con
    --device.emissions.probability 1.0 -- si no, quedan en None).

    tiempo promedio de espera: waitingTime de SUMO es el tiempo total que el
    vehiculo paso completamente detenido (velocidad < 0.1 m/s), no cuenta
    circular lento -- es la definicion estandar de "tiempo de espera" en la
    literatura de semaforos.

    flujo de vehiculos por hora: vehiculos completados / duracion simulada
    en horas. Con 12 semaforos compartiendo la demanda de toda la red, esto
    mide throughput real de la red, no de un semaforo puntual.

    CO2: SUMO estima emisiones por vehiculo con el modelo HBEFA a partir de
    la velocidad/aceleracion instantanea (device "emissions"). CO2_abs en el
    tripinfo es el total en miligramos acumulado durante todo el viaje de
    ese vehiculo. Solo esta disponible si se corrio SUMO con
    --device.emissions.probability 1.0 (ver adaptive_run.py / eval_rl_multi.py).
    """
    fitness, metrics = compute_fitness(tripinfo_path, stats_path, loaded_vehicles)

    tree = ET.parse(tripinfo_path)
    trips = tree.getroot().findall("tripinfo")
    completed = len(trips)

    total_waiting = sum(float(t.get("waitingTime")) for t in trips)
    metrics["mean_waiting_time"] = total_waiting / completed if completed else None
    metrics["vehicles_per_hour"] = completed / (sim_duration_s / 3600.0)

    co2_mg = []
    for t in trips:
        em = t.find("emissions")
        if em is not None and em.get("CO2_abs") is not None:
            co2_mg.append(float(em.get("CO2_abs")))
    if co2_mg:
        metrics["total_co2_kg"] = sum(co2_mg) / 1e6
        metrics["mean_co2_g_per_vehicle"] = (sum(co2_mg) / len(co2_mg)) / 1000.0
    else:
        metrics["total_co2_kg"] = None
        metrics["mean_co2_g_per_vehicle"] = None

    return fitness, metrics


def random_genome(n, rng):
    return [rng.uniform(GENE_MIN, GENE_MAX) for _ in range(n)]


def clip(v):
    return max(GENE_MIN, min(GENE_MAX, v))