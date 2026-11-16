"""
Corre UNA simulacion completa (1800s) con la politica de RL ya entrenada
(train_rl_multi.py) controlando los 12 semaforos, en modo determinista (sin
exploracion), con salida de tripinfo/estadisticas/emisiones activada, y
calcula las mismas metricas que baseline_fixed_run.py -- para poder
comparar de forma pareja "tiempo fijo" vs. "RL adaptativo" (tiempo de
espera, flujo vehiculos/hora, CO2).

Uso:
    python3 eval_rl_multi.py <rou_file> <tag> <loaded_vehicles> [modelo.zip]

Ejemplo:
    python3 eval_rl_multi.py osm.rou.xml moderado 820
    python3 eval_rl_multi.py osm.rou.xml moderado 820 rl_multi_checkpoints/ppo_multi_tls_40000_steps.zip
"""
import sys
import os
import json
import time

from stable_baselines3 import PPO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sumo_rl_multiagent_env import SumoMultiTLSEnv
import ga_lib as gl

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    rou_file = sys.argv[1]
    tag = sys.argv[2]
    loaded_vehicles = int(sys.argv[3])
    model_path = sys.argv[4] if len(sys.argv) > 4 else os.path.join(PROJECT_DIR, "rl_multi_model_final.zip")
    sim_end = 1800

    tripinfo_path = os.path.join(PROJECT_DIR, f"tripinfo_rl_multi_{tag}.xml")
    stats_path = os.path.join(PROJECT_DIR, f"stats_rl_multi_{tag}.xml")

    env = SumoMultiTLSEnv(
        rou_path=rou_file, sim_end=sim_end, label=f"eval_{tag}",
        tripinfo_path=tripinfo_path, stats_path=stats_path, emissions=True,
    )
    model = PPO.load(model_path)
    print(f"Modelo cargado: {model_path}", flush=True)

    t0 = time.time()
    obs, _ = env.reset()
    terminated = False
    n_steps = 0
    while not terminated:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        n_steps += 1
        if n_steps % 60 == 0:
            print(f"  ... {env.sim_time}/{sim_end}s simulados", flush=True)
    env.close()
    print(f"Listo en {time.time()-t0:.1f}s reales ({n_steps} decisiones)", flush=True)

    fitness, metrics = gl.compute_full_metrics(tripinfo_path, stats_path, loaded_vehicles, sim_end)
    print(f"RL MULTI-AGENTE ({tag}): fitness={fitness:.2f}  {metrics}", flush=True)

    json.dump({"tag": tag, "scenario": "rl_adaptativo", "model": model_path,
               "fitness": fitness, **metrics},
              open(os.path.join(PROJECT_DIR, f"result_rl_multi_{tag}.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
