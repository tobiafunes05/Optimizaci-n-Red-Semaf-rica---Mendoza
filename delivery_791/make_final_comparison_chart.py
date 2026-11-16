"""
Grafico final: tiempo fijo (linea base) vs. RL adaptativo, en las 3
metricas pedidas -- tiempo promedio de espera, flujo de vehiculos por hora,
y CO2 (con el % de reduccion del RL respecto al fijo marcado en el titulo
del panel de CO2).

Requiere: result_baseline_fixed_<tag>.json y result_rl_multi_<tag>.json
(generados con baseline_fixed_run.py y eval_rl_multi.py).

Uso:
    python3 make_final_comparison_chart.py [tag]   (default tag=moderado)
"""
import json
import os
import sys

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
AQUA = "#1baf7a"

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


def bar_panel(ax, title, ylabel, values, fmt="{:.1f}"):
    ax.grid(True, axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    bars = ax.bar(["Tiempo fijo\n(linea base)", "RL adaptativo"], values, color=[BLUE, AQUA], zorder=3, width=0.55)
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, v + max(values) * 0.02, fmt.format(v),
                 ha="center", fontsize=10, color=TEXT_SECONDARY)
    ax.set_title(title, fontsize=11, loc="left")
    ax.set_ylabel(ylabel)


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "moderado"
    fixed = load(f"result_baseline_fixed_{tag}.json")
    rl = load(f"result_rl_multi_{tag}.json")

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.2), dpi=110)

    bar_panel(axes[0], "Tiempo promedio de espera (menor es mejor)", "Segundos",
              [fixed["mean_waiting_time"], rl["mean_waiting_time"]])
    bar_panel(axes[1], "Flujo de vehiculos por hora (mayor es mejor)", "Vehiculos/hora",
              [fixed["vehicles_per_hour"], rl["vehicles_per_hour"]], fmt="{:.0f}")

    co2_fixed = fixed["total_co2_kg"]
    co2_rl = rl["total_co2_kg"]
    pct_reduction_total = (co2_fixed - co2_rl) / co2_fixed * 100 if co2_fixed else 0.0
    co2_pv_fixed = fixed["mean_co2_g_per_vehicle"]
    co2_pv_rl = rl["mean_co2_g_per_vehicle"]
    pct_reduction_pv = (co2_pv_fixed - co2_pv_rl) / co2_pv_fixed * 100 if co2_pv_fixed else 0.0
    bar_panel(axes[2], f"CO2 total emitido (bruto: {pct_reduction_total:+.1f}%)", "kg de CO2",
              [co2_fixed, co2_rl])
    completed_fixed, completed_rl = fixed["completed"], rl["completed"]
    if completed_rl < completed_fixed:
        note = (f"OJO: el RL completo menos viajes ({completed_rl} vs {completed_fixed}), asi que el CO2\n"
                 f"total bruto baja por menos autos circulando, no por eficiencia. Por vehiculo que\n"
                 f"completo el viaje, la variacion de CO2 promedio es {pct_reduction_pv:+.1f}% (negativo = el RL emite MAS por vehiculo).")
        axes[2].text(0.5, -0.30, note, transform=axes[2].transAxes, ha="center", va="top",
                      fontsize=8, color="#b23b3b" if pct_reduction_pv < 0 else TEXT_SECONDARY)

    fig.suptitle(f"Semaforos de Mendoza — tiempo fijo vs. RL adaptativo (escenario {tag}, misma demanda)\n"
                 f"Modelo RL con entrenamiento PARCIAL/preliminar -- ver nota abajo", fontsize=13, x=0.02, ha="left")
    plt.tight_layout(rect=[0, 0.06, 1, 0.88])
    out_path = os.path.join(PROJECT_DIR, f"chart_final_fijo_vs_rl_{tag}.png")
    plt.savefig(out_path)
    print(f"Guardado: {out_path}")
    print(f"CO2 total bruto: {pct_reduction_total:+.1f}% | CO2 promedio por vehiculo completado: {pct_reduction_pv:+.1f}%")


if __name__ == "__main__":
    main()
