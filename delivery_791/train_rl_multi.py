"""
Entrena UNA politica (PPO) que controla los 12 semaforos de
scope_tls_top12.json a la vez, usando sumo_rl_multiagent_env.SumoMultiTLSEnv
(observacion con info de vecinos + ocupacion aguas abajo, recompensa
compartida a nivel red -- ver el docstring de ese archivo).

Se usa PPO (no DQN, como en train_rl.py) porque el espacio de accion ahora
es MultiDiscrete (un bit de "cambiar fase o no" por cada uno de los 12
semaforos), y Stable-Baselines3 DQN solo soporta acciones Discrete simples.

Uso:
    python3 train_rl_multi.py <total_timesteps> [--resume]

Guarda checkpoints cada 5000 pasos en rl_multi_checkpoints/, el modelo
final en rl_multi_model_final.zip, y un log de recompensa por episodio en
rl_multi_train_log.csv.

ATENCION -- tiempos esperados: cada paso de entorno son 5s simulados de una
red con 12 semaforos vivos (mucho mas trabajo por paso que el entorno de
train_rl.py, que controlaba uno solo). Contá con que entrenar algo que
converja razonablemente (>= 100k-200k timesteps) tarde bastante mas que
los 20-25 min del algoritmo genetico -- lo mas practico es arrancar con
pocos miles de pasos para validar que aprende (la recompensa media por
episodio deberia ir mejorando, ver rl_multi_train_log.csv) y despues
dejarlo corriendo mas tiempo en tu maquina.
"""
import sys
import os
import csv
import time

from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback, CheckpointCallback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sumo_rl_multiagent_env import SumoMultiTLSEnv

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(PROJECT_DIR, "rl_multi_train_log.csv")
CKPT_DIR = os.path.join(PROJECT_DIR, "rl_multi_checkpoints")
FINAL_PATH = os.path.join(PROJECT_DIR, "rl_multi_model_final.zip")


class EpisodeLogger(BaseCallback):
    def __init__(self):
        super().__init__()
        self.ep_rewards = []
        self.ep_count = 0
        self.t0 = time.time()
        if not os.path.exists(LOG_PATH):
            with open(LOG_PATH, "w", newline="") as f:
                csv.writer(f).writerow(["episode", "total_timesteps", "mean_reward", "elapsed_s"])

    def _on_step(self):
        rewards = self.locals.get("rewards", [0])
        self.ep_rewards.append(rewards[0])
        dones = self.locals.get("dones", [False])
        if dones[0]:
            self.ep_count += 1
            mean_r = sum(self.ep_rewards) / len(self.ep_rewards)
            with open(LOG_PATH, "a", newline="") as f:
                csv.writer(f).writerow([self.ep_count, self.num_timesteps, mean_r, time.time() - self.t0])
            print(f"[episodio {self.ep_count}] pasos={self.num_timesteps} "
                  f"recompensa_media_red={mean_r:.3f} elapsed={time.time()-self.t0:.0f}s", flush=True)
            self.ep_rewards = []
        return True


def latest_checkpoint():
    """Encuentra el checkpoint mas avanzado en CKPT_DIR (por numero de pasos
    en el nombre de archivo), para poder retomar aunque el proceso se haya
    cortado antes de llegar a guardar el modelo final (por ejemplo si el
    entorno de ejecucion se reciclo por inactividad a mitad de entrenamiento)."""
    if not os.path.isdir(CKPT_DIR):
        return None, 0
    best_path, best_steps = None, 0
    for fn in os.listdir(CKPT_DIR):
        m = fn.replace("ppo_multi_tls_", "").replace("_steps.zip", "")
        if m.isdigit() and fn.endswith("_steps.zip"):
            steps = int(m)
            if steps > best_steps:
                best_steps = steps
                best_path = os.path.join(CKPT_DIR, fn)
    return best_path, best_steps


def main():
    total_timesteps = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    resume = "--resume" in sys.argv

    env = SumoMultiTLSEnv(rou_path="osm.rou.xml", label="train_multi")

    ckpt_path, ckpt_steps = latest_checkpoint()
    if resume and os.path.exists(FINAL_PATH):
        print("Retomando desde el modelo final existente...", flush=True)
        model = PPO.load(FINAL_PATH, env=env)
        reset_num_timesteps = False
    elif resume and ckpt_path:
        print(f"No hay modelo final (se debe haber cortado antes de terminar) -- "
              f"retomando desde el ultimo checkpoint: {ckpt_path} ({ckpt_steps} pasos ya entrenados)", flush=True)
        model = PPO.load(ckpt_path, env=env)
        model.num_timesteps = ckpt_steps
        reset_num_timesteps = False
    else:
        model = PPO(
            "MlpPolicy", env,
            learning_rate=3e-4,
            n_steps=256,          # pasos de entorno por actualizacion (episodio ~360 pasos de 5s en 1800s)
            batch_size=64,
            n_epochs=10,
            gamma=0.99,
            policy_kwargs=dict(net_arch=[128, 128]),
            verbose=0,
        )
        reset_num_timesteps = True

    ckpt_cb = CheckpointCallback(save_freq=5000, save_path=CKPT_DIR, name_prefix="ppo_multi_tls")
    log_cb = EpisodeLogger()

    model.learn(total_timesteps=total_timesteps, callback=[ckpt_cb, log_cb],
                reset_num_timesteps=reset_num_timesteps, progress_bar=False)
    model.save(FINAL_PATH)
    env.close()
    print("Entrenamiento terminado. Modelo guardado en", FINAL_PATH, flush=True)


if __name__ == "__main__":
    main()
