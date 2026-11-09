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


# ---------------------------------------------------------------------------
# Cenário RU (genérico: usa polígonos/raios guardados no ambiente)
# ---------------------------------------------------------------------------
def _extent_planta(origem_px=(269.0, 388.5), px_por_m=8.2, shape=(410, 580)):
    h, w = shape
    return [-origem_px[0] / px_por_m, (w - origem_px[0]) / px_por_m,
            (origem_px[1] - h) / px_por_m, origem_px[1] / px_por_m]


def plot_planta_ru(env, res, caminho, fundo=None, titulo=None):
    """Planta do RU colorida pelo peso a_i. `res=None` omite os sensores; `fundo` é o
    caminho da planta original, desenhada por baixo para conferir a digitalização."""
    from matplotlib.collections import LineCollection
    fig, ax = plt.subplots(figsize=(11, 4 + 11.5 * env.comprimento / 43.3))
    if fundo:
        ax.imshow(plt.imread(fundo), extent=_extent_planta(), zorder=0, alpha=.55)
    st = env.step
    nx, ny = round(env.largura / st + .49), round(env.comprimento / st + .49)
    g = np.full((ny, nx), np.nan)
    for (x, y), w in zip(env.I_coords, env.a):
        g[int(y / st), int(x / st)] = w
    im = ax.imshow(np.ma.masked_invalid(g), extent=[0, nx * st, 0, ny * st], origin="lower",
                   cmap="YlOrRd", vmin=0, vmax=max(env.a), alpha=.45 if fundo else .75, zorder=1)
    plt.colorbar(im, ax=ax, fraction=.03, pad=.02, label="Peso de demanda $a_i$")
    ax.add_collection(LineCollection([((a, b), (c, d)) for a, b, c, d in env.paredes],
                                     colors="k", linewidths=1.6, zorder=3))
    if getattr(env, "divisorias", None):
        ax.add_collection(LineCollection([((a, b), (c, d)) for a, b, c, d in env.divisorias],
                                         colors="k", linewidths=3, zorder=3, label="Divisória interna"))
    for sid, s in env.salas.items():
        pts = np.array([c for c, r in zip(env.I_coords, env.sala_i) if r == sid])
        ax.text(*pts.mean(0), sid, ha="center", va="center", fontsize=10, fontweight="bold",
                color="navy", zorder=4)
    for k, p in enumerate(env.portas):
        ax.add_patch(patches.Circle((p["x"], p["y"]), env.raio_porta, fill=False, ec="crimson", ls=":", lw=1.2, zorder=3))
        ax.scatter(p["x"], p["y"], marker="^", c="crimson", s=70, ec="k", zorder=5,
                   label="Porta externa (raio 1,5 m)" if k == 0 else None)
    for k, q in enumerate(env.equipamentos):
        x0, y0, x1, y1 = q["retangulo"]
        m = q["margem"]
        ax.add_patch(patches.Rectangle((x0, y0), x1 - x0, y1 - y0, fc="dodgerblue", ec="k", zorder=4,
                                       label="Fonte de calor (exclusão)" if k == 0 else None))
        ax.add_patch(patches.Rectangle((x0 - m, y0 - m), x1 - x0 + 2 * m, y1 - y0 + 2 * m, fill=False,
                                       ec="dodgerblue", ls=":", zorder=3))
    tipos = getattr(env, "tipo_j", None) or ["parede"] * len(env.J_coords)
    estilo = {"parede": ("dimgray", "."), "divisória": ("dimgray", "."), "pilar": ("dimgray", "."),
              "borda de mesa": ("darkviolet", "."), "balcão": ("teal", "."), "malha": ("dimgray", ".")}
    for t in dict.fromkeys(tipos):
        pts = [c for c, tj in zip(env.J_coords, tipos) if tj == t]
        cor, mk = estilo.get(t, ("dimgray", "."))
        ax.scatter(*zip(*pts), c=cor, marker=mk, s=14, alpha=.8, zorder=4,
                   label=f"Candidatos: {t} ({len(pts)})")
    px = [p["x"] for p in env.pilares]; py = [p["y"] for p in env.pilares]
    ax.scatter(px, py, c="k", marker="s", s=60, zorder=5, label="Pilares do salão")
    if res is not None:
        for k, (sx, sy) in enumerate(res["sensores"], 1):
            r = env.raio_j[res["idx_sensores"][k - 1]]
            ax.add_patch(patches.Circle((sx, sy), r, fc="limegreen", ec="darkgreen", alpha=.22, ls="--", lw=1.2, zorder=3))
            ax.scatter(sx, sy, c="lime", marker="*", s=300, ec="k", zorder=6,
                       label=f"{getattr(env, 'sensor', 'DHT22')} escolhido (p={res['p']})" if k == 1 else None)
            ax.text(sx, sy + .5, f"S{k}", fontsize=8, ha="center", fontweight="bold", zorder=7,
                    bbox=dict(boxstyle="round,pad=.15", fc="white", alpha=.8))
    ax.set_xlim(-1, env.largura + 1); ax.set_ylim(-1, env.comprimento + 1); ax.set_aspect("equal")
    ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)")
    if titulo is None and res is not None:
        titulo = (f"{getattr(env, 'nome', 'RU UFSCar')} — {getattr(env, 'sensor', 'DHT22')} ótimos "
                  f"(p={res['p']}, cobertura ponderada {res['cob_total_pct']:.1f}%)")
    ax.set_title(titulo or f"{getattr(env, 'nome', 'RU UFSCar')} — conferência da geometria digitalizada")
    ax.legend(loc="upper right", fontsize=8, framealpha=.9)
    fig.tight_layout(); fig.savefig(caminho, dpi=300); plt.close(fig)


def plot_pareto_grupos(resultados, caminho, grupos, p_dest=None, p_lscp=None, alt=None, titulo=None, p_fim=None):
    """Curva de trade-off: cobertura total e por grupo. `alt` = resultados do modelo de comparação
    de câmaras (curva tracejada da cobertura total)."""
    ps = [r["p"] for r in resultados]
    p_fim = p_fim or max(ps)
    fig, ax = plt.subplots(figsize=(11, 6.5))

    def serie(rs, chave, **kw):  # linha até p_fim; acima disso só marcadores (sem interpolar)
        a = [r for r in rs if r["p"] <= p_fim]
        b = [r for r in rs if r["p"] >= p_fim]
        (linha,) = ax.plot([r["p"] for r in a], [r[chave] for r in a], **kw)
        if len(b) > 1:
            kw2 = {k: v for k, v in kw.items() if k != "label"}
            ax.plot([r["p"] for r in b], [r[chave] for r in b], ls="none", color=linha.get_color(),
                    **{k: v for k, v in kw2.items() if k in ("marker", "ms")})
    serie(resultados, "cob_total_pct", color="k", marker="o", lw=3, label="Total ponderada", zorder=5)
    if alt:
        serie(alt, "cob_total_pct", color="k", ls="--", lw=1.5, label="Total (sem restrição de câmara)")
    cores = plt.get_cmap("tab10")
    for k, gr in enumerate(grupos):
        serie(resultados, f"cob_{gr}_pct", marker="os^vDpP"[k % 7], ms=4, lw=1.4, color=cores(k), label=gr)
    if p_dest:
        ax.axvline(p_dest, color="gray", ls="--", lw=1, label=f"p = {p_dest}")
    if p_lscp:
        ax.axvline(p_lscp, color="purple", ls=":", lw=1.5, label=f"LSCP: p = {p_lscp}")
    if max(ps) > 40:  # p do LSCP muito acima da varredura inicial: eixo logarítmico
        ax.set_xscale("log")
        marcas = sorted({1, 2, 5, 10, 20, 50, 100, 200, max(ps)} & set(range(1, max(ps) + 1)) | {max(ps)})
        ax.set_xticks(marcas); ax.set_xticklabels([str(m) for m in marcas])
    ax.set_ylim(0, 105); ax.set_xlabel("Número máximo de sensores $p$"); ax.set_ylabel("Cobertura (%)")
    ax.set_title(titulo or "Curva de trade-off: sensores × cobertura")
    ax.grid(ls="--", alpha=.5); ax.legend(loc="lower right", ncol=2, fontsize=8)
    fig.tight_layout(); fig.savefig(caminho, dpi=300); plt.close(fig)
