import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation

SURFACE = "#fcfcfb"
ROAD = "#c3c2b7"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
BLUE = "#2a78d6"
AQUA = "#1baf7a"

CX, CY = 1397.195, 2576.78
R = 220  # medio-ancho del recuadro en metros

scene = json.load(open("scene_edges.json"))
fb = json.load(open("frames_baseline.json"))["frames"]
fo = json.load(open("frames_optimized.json"))["frames"]
n_frames = min(len(fb), len(fo))

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial"],
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
})

fig, axes = plt.subplots(1, 2, figsize=(10.5, 5.9), dpi=110)
fig.subplots_adjust(top=0.82, bottom=0.06, left=0.05, right=0.97, wspace=0.12)

titles = ["Baseline (semaforos originales, actuados)", "GA-optimizado (12 intersecciones criticas)"]
colors = [BLUE, AQUA]
scatters = []

for ax, title, color in zip(axes, titles, colors):
    for e in scene["edges"]:
        xs = [p[0] for p in e["shape"]]
        ys = [p[1] for p in e["shape"]]
        ax.plot(xs, ys, color=ROAD, linewidth=2.2, solid_capstyle="round", zorder=1)
    ax.set_xlim(CX - R, CX + R)
    ax.set_ylim(CY - R, CY + R)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title(title, fontsize=10.5, color=TEXT_PRIMARY, pad=8)
    sc = ax.scatter([], [], s=20, color=color, zorder=3, edgecolors="white", linewidths=0.4)
    scatters.append(sc)

count_texts = [
    axes[0].text(0.02, 0.02, "", transform=axes[0].transAxes, fontsize=9, color=TEXT_SECONDARY),
    axes[1].text(0.02, 0.02, "", transform=axes[1].transAxes, fontsize=9, color=TEXT_SECONDARY),
]
suptitle = fig.suptitle("", fontsize=13, color=TEXT_PRIMARY, y=0.985)
fig.text(0.5, 0.905, "Misma demanda de trafico, mismo instante — interseccion mas congestionada de la red",
          ha="center", fontsize=9, color=TEXT_SECONDARY)


def init():
    for sc in scatters:
        sc.set_offsets(np.empty((0, 2)))
    return scatters + count_texts + [suptitle]


def update(i):
    frame_b = fb[i]
    frame_o = fo[i]
    t = frame_b["time"]
    mm, ss = divmod(int(t), 60)
    suptitle.set_text(f"Comparativa en SUMO — minuto {mm:02d}:{ss:02d} de simulacion")

    xb = [[v["x"], v["y"]] for v in frame_b["vehicles"]]
    xo = [[v["x"], v["y"]] for v in frame_o["vehicles"]]
    scatters[0].set_offsets(np.array(xb) if xb else np.empty((0, 2)))
    scatters[1].set_offsets(np.array(xo) if xo else np.empty((0, 2)))
    count_texts[0].set_text(f"{len(xb)} vehiculos en el recuadro")
    count_texts[1].set_text(f"{len(xo)} vehiculos en el recuadro")
    return scatters + count_texts + [suptitle]


ani = animation.FuncAnimation(fig, update, frames=n_frames, init_func=init,
                               interval=90, blit=False)
writer = animation.PillowWriter(fps=11)
ani.save("comparativa_sumo.gif", writer=writer)
print("GIF guardado: comparativa_sumo.gif, frames:", n_frames)
