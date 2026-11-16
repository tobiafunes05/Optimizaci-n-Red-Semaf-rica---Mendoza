import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SURFACE = "#fcfcfb"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
YELLOW = "#eda100"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial"],
    "text.color": TEXT_PRIMARY,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": TEXT_SECONDARY,
    "xtick.color": TEXT_MUTED if (TEXT_MUTED := "#898781") else None,
    "ytick.color": TEXT_MUTED,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
})

scenarios = ["Trafico moderado\n(820 veh.)", "Trafico denso\n(1800 veh.)"]
series = [
    ("Baseline (actuado)", BLUE, [402.4, 491.1]),
    ("Static (sin optimizar)", ORANGE, [384.4, 482.7]),
    ("GA-optimizado (offline)", AQUA, [370.7, 475.0]),
    ("Adaptativo tiempo real (max-pressure)", YELLOW, [397.4, 483.1]),
]

fig, ax = plt.subplots(figsize=(8.2, 5.2), dpi=110)
ax.grid(True, axis="y", color=GRID, linewidth=0.8, zorder=0)
ax.set_axisbelow(True)
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)
for spine in ["left", "bottom"]:
    ax.spines[spine].set_color(AXIS)

n_series = len(series)
bar_w = 0.19
x = range(len(scenarios))
for i, (label, color, vals) in enumerate(series):
    offs = [xi + (i - (n_series - 1) / 2) * bar_w for xi in x]
    bars = ax.bar(offs, vals, width=bar_w, color=color, label=label, zorder=3)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 3, f"{v:.0f}", ha="center",
                fontsize=8, color=TEXT_SECONDARY)

ax.set_xticks(list(x))
ax.set_xticklabels(scenarios, fontsize=10)
ax.set_ylabel("Fitness (costo, seg-equiv./vehiculo) — menor es mejor")
ax.set_title("Cuatro estrategias de control de semaforos, dos niveles de trafico",
              fontsize=12, loc="left", pad=12)
ax.legend(frameon=False, loc="upper left", fontsize=8, labelcolor=TEXT_SECONDARY, ncol=1)
plt.tight_layout()
plt.savefig("chart_four_way.png")
print("chart_four_way.png guardado")
