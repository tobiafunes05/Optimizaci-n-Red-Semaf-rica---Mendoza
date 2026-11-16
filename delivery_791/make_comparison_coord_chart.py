"""
Genera un grafico comparando las 5 estrategias de control de semaforos
probadas en el escenario moderado (820 vehiculos), incluyendo la novedad de
esta sesion: adaptativo CON coordinacion entre semaforos vecinos vs SIN
ella. A diferencia de make_adaptive_chart.py (valores harcodeados), este
script lee los JSON reales, asi que si volves a correr adaptive_run.py se
puede regenerar sin editar nada.

Requiere: comparison.json (Baseline/Static/GA, ya en el proyecto),
result_adaptive_moderado_nocoord.json y result_adaptive_moderado_coord.json
(generados con adaptive_run.py, con y sin --no-coord).

Uso:
    python3 make_comparison_coord_chart.py
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

SURFACE = "#fcfcfb"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
YELLOW = "#eda100"
RED = "#d63b3b"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial"],
    "text.color": TEXT_PRIMARY,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": TEXT_SECONDARY,
    "xtick.color": TEXT_SECONDARY,
    "ytick.color": TEXT_SECONDARY,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
})


def load(name):
    with open(os.path.join(PROJECT_DIR, name)) as f:
        return json.load(f)


def main():
    comparison = load("comparison.json")
    nocoord = load("result_adaptive_moderado_nocoord.json")
    coord = load("result_adaptive_moderado_coord.json")

    labels = [c["label"] for c in comparison] + [
        "Adaptativo\n(sin coordinar)", "Adaptativo\n(coordinado, nuevo)"
    ]
    fitness = [c["fitness"] for c in comparison] + [nocoord["fitness"], coord["fitness"]]
    completed = [c["completed"] for c in comparison] + [nocoord["completed"], coord["completed"]]
    teleports = [c["teleports"] for c in comparison] + [nocoord["teleports"], coord["teleports"]]
    colors = [BLUE, ORANGE, AQUA, YELLOW, RED]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.5, 5.8), dpi=110)

    # --- panel 1: fitness (menor es mejor) ---
    ax1.grid(True, axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax1.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax1.spines[spine].set_visible(False)
    bars = ax1.bar(range(len(labels)), fitness, color=colors, zorder=3)
    for b, v in zip(bars, fitness):
        ax1.text(b.get_x() + b.get_width() / 2, v + 3, f"{v:.0f}", ha="center",
                  fontsize=9, color=TEXT_SECONDARY)
    ax1.set_xticks(range(len(labels)))
    ax1.set_xticklabels(labels, fontsize=8.5, rotation=12, ha="right")
    ax1.set_ylabel("Fitness (costo, seg-equiv./vehiculo) — menor es mejor")
    ax1.set_title("Costo total", fontsize=11, loc="left")

    # --- panel 2: completados vs teleports ---
    ax2.grid(True, axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax2.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax2.spines[spine].set_visible(False)
    x = range(len(labels))
    w = 0.35
    b1 = ax2.bar([xi - w / 2 for xi in x], completed, width=w, color="#3a8fd6",
                 label="Vehiculos completados (mas es mejor)", zorder=3)
    b2 = ax2.bar([xi + w / 2 for xi in x], teleports, width=w, color="#d67a3a",
                 label="Teleports / atascos (menos es mejor)", zorder=3)
    for b, v in zip(b1, completed):
        ax2.text(b.get_x() + b.get_width() / 2, v + 3, f"{v}", ha="center", fontsize=8, color=TEXT_SECONDARY)
    for b, v in zip(b2, teleports):
        ax2.text(b.get_x() + b.get_width() / 2, v + 3, f"{v}", ha="center", fontsize=8, color=TEXT_SECONDARY)
    ax2.set_xticks(range(len(labels)))
    ax2.set_xticklabels(labels, fontsize=8.5, rotation=12, ha="right")
    ax2.set_title("Vehiculos completados vs. atascos", fontsize=11, loc="left")
    ax2.legend(frameon=False, loc="upper left", fontsize=8, labelcolor=TEXT_SECONDARY)

    fig.suptitle("Trafico moderado (820 vehiculos) — 5 estrategias de control de semaforos",
                  fontsize=13, x=0.02, ha="left")
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    out_path = os.path.join(PROJECT_DIR, "chart_comparativa_coordinacion.png")
    plt.savefig(out_path)
    print(f"Guardado: {out_path}")


if __name__ == "__main__":
    main()
