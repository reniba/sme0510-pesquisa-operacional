"""Figuras (dpi=300)."""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from .lab_environment import ACS, AC_EXCL, STEP, LX, LY, S_XY


def plot_planta(env, res, caminho):
    fig, ax = plt.subplots(figsize=(11, 8))
    nx, ny = round(LX / STEP), round(LY / STEP)
    g = np.zeros((ny, nx))
    for (x, y), w in zip(env.I_coords, env.a):
        g[int((y - .25) / STEP), int((x - .25) / STEP)] = w
    im = ax.imshow(g, extent=[0, LX, 0, LY], origin="lower", cmap="YlOrRd", alpha=.6)
    plt.colorbar(im, ax=ax, fraction=.035, pad=.02, label="Peso de demanda $a_i$")
    ax.plot([0, 7.5], [5, 5], "k-", lw=5, label="Divisória de vidro")
    ax.plot([7.5, 7.5], [5, 7], "k-", lw=5)
    for k, (ax_, ay_) in enumerate(ACS):
        ax.add_patch(patches.Circle((ax_, ay_), AC_EXCL, fill=False, ec="dodgerblue", ls=":", lw=1.2))
        ax.scatter(ax_, ay_, c="dodgerblue", marker="s", s=140, ec="k", zorder=5,
                   label="Ar-condicionado (raio 1 m)" if k == 0 else None)
    jx, jy = zip(*env.J_coords)
    ax.scatter(jx, jy, c="gray", marker=".", s=28, alpha=.7, label="Candidatos $J$")
    for k, (sx, sy) in enumerate(res["sensores"]):
        ax.scatter(sx, sy, c="lime", marker="*", s=380, ec="k", zorder=6,
                   label=f"DHT22 escolhido (p={res['p']})" if k == 0 else None)
        ax.add_patch(patches.Circle((sx, sy), S_XY, fc="limegreen", ec="darkgreen", alpha=.15, ls="--", lw=1.4))
        ax.text(sx, sy + .25, f"S{k+1} ({sx:.2f}, {sy:.2f})", fontsize=8, ha="center", fontweight="bold",
                bbox=dict(boxstyle="round,pad=.2", fc="white", alpha=.8))
    ax.set_xlim(0, LX); ax.set_ylim(0, LY); ax.set_aspect("equal")
    ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)")
    ax.set_title(f"Posicionamento ótimo de DHT22 — p={res['p']}, cobertura ponderada {res['cob_total_pct']:.1f}%")
    ax.legend(loc="lower right", fontsize=8, framealpha=.9)
    ax.grid(ls=":", alpha=.4)
    fig.tight_layout(); fig.savefig(caminho, dpi=300); plt.close(fig)


def plot_pareto(resultados, caminho, p_dest=None):
    ps = [r["p"] for r in resultados]
    fig, ax = plt.subplots(figsize=(9, 6))
    for chave, rot, cor, m in [("cob_total_pct", "Total ponderada", "firebrick", "o"),
                               ("cob_racks_pct", "Sala de Racks", "navy", "s"),
                               ("cob_bancadas_pct", "Bancadas", "darkgreen", "^")]:
        ax.plot(ps, [r[chave] for r in resultados], marker=m, color=cor, lw=2, label=rot)
    if p_dest:
        ax.axvline(p_dest, color="gray", ls="--", label=f"p = {p_dest}")
    ax.set_xticks(ps); ax.set_ylim(0, 105)
    ax.set_xlabel("Número máximo de sensores $p$"); ax.set_ylabel("Cobertura (%)")
    ax.set_title("Curva de trade-off: sensores × cobertura")
    ax.grid(ls="--", alpha=.5); ax.legend(loc="lower right")
    fig.tight_layout(); fig.savefig(caminho, dpi=300); plt.close(fig)
