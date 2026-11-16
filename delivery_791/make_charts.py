import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# --- paleta (dataviz skill, modo claro) ---
SURFACE = "#fcfcfb"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
TEXT_MUTED = "#898781"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial"],
    "text.color": TEXT_PRIMARY,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": TEXT_SECONDARY,
    "xtick.color": TEXT_MUTED,
    "ytick.color": TEXT_MUTED,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
})

# =========== Chart 1: Convergencia del GA ===========
best = json.load(open("best_genome.json"))
hist = best["history"]
gens = [h["gen"] for h in hist]
bests = [h["best"] for h in hist]
avgs = [h["avg"] for h in hist]

fig, ax = plt.subplots(figsize=(7.6, 4.6), dpi=200)
ax.grid(True, axis="y", color=GRID, linewidth=0.8, zorder=0)
ax.set_axisbelow(True)
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)
for spine in ["left", "bottom"]:
    ax.spines[spine].set_color(AXIS)
    ax.spines[spine].set_linewidth(0.8)

ax.plot(gens, avgs, color=ORANGE, linewidth=2, label="Promedio de la poblacion", marker="o", markersize=4)
ax.plot(gens, bests, color=BLUE, linewidth=2, label="Mejor individuo", marker="o", markersize=4)

ax.set_xlabel("Generacion")
ax.set_ylabel("Fitness (seg-equiv./vehiculo)\nmenor es mejor")
ax.set_title("Convergencia del algoritmo genetico", color=TEXT_PRIMARY, fontsize=13, loc="left", pad=12)
leg = ax.legend(frameon=False, loc="upper right", fontsize=9, labelcolor=TEXT_SECONDARY)
plt.tight_layout(pad=1.2)
plt.savefig("chart_convergence.png")
plt.close()

# =========== Chart 2: Comparacion de escenarios ===========
comp = json.load(open("comparison.json"))
labels = [c["label"] for c in comp]
metrics = [
    ("meanWait", "Espera media (s)"),
    ("meanDur", "Duracion media (s)"),
    ("meanTimeLoss", "Perdida de tiempo media (s)"),
]
colors = [BLUE, ORANGE, AQUA]

fig, ax = plt.subplots(figsize=(7.5, 4.5), dpi=200)
ax.grid(True, axis="y", color=GRID, linewidth=0.8, zorder=0)
ax.set_axisbelow(True)
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)
for spine in ["left", "bottom"]:
    ax.spines[spine].set_color(AXIS)
    ax.spines[spine].set_linewidth(0.8)

n_metrics = len(metrics)
n_series = len(comp)
bar_w = 0.24
x = range(n_metrics)

for i, c in enumerate(comp):
    vals = [c[m[0]] for m in metrics]
    offs = [xi + (i - (n_series - 1) / 2) * bar_w for xi in x]
    bars = ax.bar(offs, vals, width=bar_w, color=colors[i], label=c["label"], zorder=3)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 3, f"{v:.0f}", ha="center",
                fontsize=8, color=TEXT_SECONDARY)

ax.set_xticks(list(x))
ax.set_xticklabels([m[1] for m in metrics], fontsize=9)
ax.set_ylabel("Segundos")
ax.set_title("Metricas de trafico por escenario (misma demanda, 30 min simulados)",
              color=TEXT_PRIMARY, fontsize=12, loc="left", pad=12)
ax.legend(frameon=False, loc="upper right", fontsize=8, labelcolor=TEXT_SECONDARY)
plt.tight_layout()
plt.savefig("chart_comparison.png")
plt.close()

print("Charts generados: chart_convergence.png, chart_comparison.png")
