"""
Entrena un agente DQN (aprendizaje por refuerzo) para controlar UN semaforo
de la red (1135888071) usando el entorno sumo_rl_env.SumoTLSEnv.

Uso:
    python3 train_rl.py <total_timesteps> [--resume]

Guarda checkpoints cada 5000 pasos en rl_checkpoints/, el modelo final en
rl_model_final.zip, y un log de recompensa por episodio en rl_train_log.csv
(para graficar la curva de aprendizaje).
"""
import sys
import os
import csv
import time

from stable_baselines3 import DQN
from stable_baselines3.common.callbacks import BaseCallback, CheckpointCallback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sumo_rl_env import SumoTLSEnv

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(PROJECT_DIR, "rl_train_log.csv")
CKPT_DIR = os.path.join(PROJECT_DIR, "rl_checkpoints")
FINAL_PATH = os.path.join(PROJECT_DIR, "rl_model_final.zip")


class EpisodeLogger(BaseCallback):
    """Escribe a rl_train_log.csv: episodio, pasos totales, recompensa promedio del episodio."""
    def __init__(self):
        super().__init__()
        self.ep_rewards = []
        self.ep_count = 0
        self.t0 = time.time()
        if not os.path.exists(LOG_PATH):
            with open(LOG_PATH, "w", newline="") as f:
                csv.writer(f).writerow(["episode", "total_timesteps", "mean_reward", "elapsed_s"])

    def _on_step(self):
        infos = self.locals.get("infos", [{}])
        rewards = self.locals.get("rewards", [0])
        self.ep_rewards.append(rewards[0])
        dones = self.locals.get("dones", [False])
        if dones[0]:
            self.ep_count += 1
            mean_r = sum(self.ep_rewards) / len(self.ep_rewards)
            with open(LOG_PATH, "a", newline="") as f:
                csv.writer(f).writerow([self.ep_count, self.num_timesteps, mean_r, time.time() - self.t0])
            print(f"[episodio {self.ep_count}] pasos={self.num_timesteps} "
                  f"recompensa_media={mean_r:.3f} elapsed={time.time()-self.t0:.0f}s", flush=True)
            self.ep_rewards = []
        return True


def main():
    total_timesteps = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    resume = "--resume" in sys.argv

    env = SumoTLSEnv(rou_path="osm.rou.xml", label="train")

    if resume and os.path.exists(FINAL_PATH):
        print("Retomando modelo existente...", flush=True)
        model = DQN.load(FINAL_PATH, env=env)
        reset_num_timesteps = False
    else:
        model = DQN(
            "MlpPolicy", env,
            learning_rate=1e-3,
            buffer_size=50000,
            learning_starts=500,
            batch_size=64,
            train_freq=1,
            target_update_interval=500,
            exploration_fraction=0.3,
            exploration_final_eps=0.05,
            policy_kwargs=dict(net_arch=[64, 64]),
            verbose=0,
        )
        reset_num_timesteps = True

    ckpt_cb = CheckpointCallback(save_freq=5000, save_path=CKPT_DIR, name_prefix="dqn_tls")
    log_cb = EpisodeLogger()

    model.learn(total_timesteps=total_timesteps, callback=[ckpt_cb, log_cb],
                reset_num_timesteps=reset_num_timesteps, progress_bar=False)
    model.save(FINAL_PATH)
    env.close()
    print("Entrenamiento terminado. Modelo guardado en", FINAL_PATH, flush=True)


if __name__ == "__main__":
    main()
