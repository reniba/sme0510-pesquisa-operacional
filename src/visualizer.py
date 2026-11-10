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


def _desenhar_planta_ru(ax, env, res, fundo=None, titulo=None, rotulo="escolhido",
                        cor_sensor="lime", cor_circulo="limegreen", cor_borda="darkgreen"):
    """Desenha a planta num eixo `ax`. `res=None` omite os sensores; `fundo` é o caminho
    da planta original, desenhada por baixo para conferir a digitalização."""
    from matplotlib.collections import LineCollection
    if fundo:
        ax.imshow(plt.imread(fundo), extent=_extent_planta(), zorder=0, alpha=.55)
    st = env.step
    nx, ny = round(env.largura / st + .49), round(env.comprimento / st + .49)
    g = np.full((ny, nx), np.nan)
    for (x, y), w in zip(env.I_coords, env.a):
        g[int(y / st), int(x / st)] = w
    im = ax.imshow(np.ma.masked_invalid(g), extent=[0, nx * st, 0, ny * st], origin="lower",
                   cmap="YlOrRd", vmin=0, vmax=max(env.a), alpha=.45 if fundo else .75, zorder=1)
    ax.figure.colorbar(im, ax=ax, fraction=.03, pad=.02, label="Peso de demanda $a_i$")
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
            ax.add_patch(patches.Circle((sx, sy), r, fc=cor_circulo, ec=cor_borda, alpha=.22, ls="--", lw=1.2, zorder=3))
            ax.scatter(sx, sy, c=cor_sensor, marker="*", s=300, ec="k", zorder=6,
                       label=f"{getattr(env, 'sensor', 'DHT22')} {rotulo} (p={res['p']})" if k == 1 else None)
            ax.text(sx, sy + .5, f"S{k}", fontsize=8, ha="center", fontweight="bold", zorder=7,
                    bbox=dict(boxstyle="round,pad=.15", fc="white", alpha=.8))
    ax.set_xlim(-1, env.largura + 1); ax.set_ylim(-1, env.comprimento + 1); ax.set_aspect("equal")
    ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)")
    if titulo is None and res is not None:
        titulo = (f"{getattr(env, 'nome', 'RU UFSCar')} — {getattr(env, 'sensor', 'DHT22')} ótimos "
                  f"(p={res['p']}, cobertura ponderada {res['cob_total_pct']:.1f}%)")
    ax.set_title(titulo or f"{getattr(env, 'nome', 'RU UFSCar')} — conferência da geometria digitalizada")
    ax.legend(loc="upper right", fontsize=8, framealpha=.9)


def plot_planta_ru(env, res, caminho, fundo=None, titulo=None):
    """Planta do RU/salão colorida pelo peso a_i, com os sensores de `res` (se houver)."""
    fig, ax = plt.subplots(figsize=(11, 4 + 11.5 * env.comprimento / 43.3))
    _desenhar_planta_ru(ax, env, res, fundo, titulo)
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


# ---------------------------------------------------------------------------
# Comparação MCLP (PLI exata) x K-Means + snapping
# ---------------------------------------------------------------------------
def plotar_comparacao_planta(env, res_mclp, res_kmeans, caminho_saida):
    """Duas plantas lado a lado, para o mesmo p: MCLP (esquerda) e K-Means (direita).
    No painel do K-Means, `X` vermelho = centroide bruto; a linha tracejada leva até o
    candidato físico escolhido no snapping (estrela)."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(22, 4 + 5.2 * env.comprimento / 26))
    p = res_mclp["p"]
    _desenhar_planta_ru(a1, env, res_mclp, titulo=(f"MCLP (PLI, CBC) — p = {p}\n"
                        f"cobertura ponderada {res_mclp['cob_total_pct']:.1f}%"))
    _desenhar_planta_ru(a2, env, res_kmeans, rotulo="K-Means + snapping", cor_sensor="orange",
                        cor_circulo="orange", cor_borda="darkorange",
                        titulo=(f"K-Means ponderado + snapping (Qin et al., 2023) — p = {p}\n"
                                f"cobertura ponderada {res_kmeans['cob_total_pct']:.1f}%"))
    for k, ((cx, cy), (sx, sy)) in enumerate(zip(res_kmeans["centroides_brutos"], res_kmeans["sensores"])):
        a2.plot([cx, sx], [cy, sy], color="red", ls="--", lw=1.3, zorder=7)
        a2.scatter(cx, cy, marker="X", c="red", s=110, ec="k", zorder=8,
                   label="Centroide bruto (K-Means)" if k == 0 else None)
    a2.legend(loc="upper right", fontsize=8, framealpha=.9)
    ganho = res_mclp["cob_total_pct"] - res_kmeans["cob_total_pct"]
    fig.suptitle(f"Programação inteira vs. K-Means: ganho de {ganho:.1f} p.p. de cobertura ponderada com p = {p}",
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, .97)); fig.savefig(caminho_saida, dpi=300, bbox_inches="tight"); plt.close(fig)


def plotar_curva_pareto_comparativa(resultados_comp, caminho_saida, p_destaque=10):
    """Cobertura ponderada total x p: MCLP (linha sólida) contra K-Means + snapping
    (tracejada), com a área entre as curvas sombreada (ganho da otimização inteira)."""
    ps = [r["p"] for r in resultados_comp]
    m = np.array([r["cob_mclp_pct"] for r in resultados_comp])
    k = np.array([r["cob_kmeans_pct"] for r in resultados_comp])
    km = np.array([r["cob_kmeans_media_pct"] for r in resultados_comp])
    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.fill_between(ps, k, m, color="tab:green", alpha=.18, label="Ganho da PLI ($\\Delta$%)")
    ax.plot(ps, m, "-o", color="tab:green", lw=2.6, label="MCLP (PLI exata, CBC)")
    ax.plot(ps, k, "--s", color="tab:blue", lw=2, label="K-Means + snapping (melhor de 5 sementes)")
    ax.plot(ps, km, ":", color="tab:blue", lw=1.3, label="K-Means + snapping (média das 5 sementes)")
    if p_destaque in ps:
        i = ps.index(p_destaque)
        ax.axvline(p_destaque, color="gray", ls="--", lw=1)
        ax.annotate(f"+{m[i] - k[i]:.1f} p.p.", ((p_destaque), (m[i] + k[i]) / 2), xytext=(8, 0),
                    textcoords="offset points", fontsize=11, fontweight="bold", color="darkgreen")
    ax.set_xticks(ps); ax.set_ylim(0, 105)
    ax.set_xlabel("Número máximo de sensores $p$"); ax.set_ylabel("Cobertura ponderada total (%)")
    ax.set_title("MCLP (programação inteira) vs. K-Means com snapping")
    ax.grid(ls="--", alpha=.5); ax.legend(loc="lower right")
    fig.tight_layout(); fig.savefig(caminho_saida, dpi=300); plt.close(fig)


# ---------------------------------------------------------------------------
# Comparação entre malhas (1,0 m x 0,5 m) e métodos (MCLP x K-Means)
# ---------------------------------------------------------------------------
_ESTILO_CENARIO = {
    ("MCLP", 1.0): dict(color="tab:green", ls="-", marker="o"),
    ("MCLP", 0.5): dict(color="darkgreen", ls="-", marker="D"),
    ("K-Means", 1.0): dict(color="tab:blue", ls="--", marker="s"),
    ("K-Means", 0.5): dict(color="navy", ls="--", marker="^"),
}


def plotar_comparacao_malhas(linhas, caminho_saida, passo_ref=0.5, p_destaque=10):
    """Painel 1: cobertura ponderada avaliada na malha de referência x p, para os 4
    cenários. Painel 2: tempo de solução x p (escala log)."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(17, 6.5))
    for (metodo, passo), est in _ESTILO_CENARIO.items():
        rs = sorted([r for r in linhas if r["metodo"] == metodo and r["malha_m"] == passo], key=lambda r: r["p"])
        if not rs:
            continue
        rot = f"{metodo} — malha {passo:.1f} m".replace(".", ",")
        ps = [r["p"] for r in rs]
        a1.plot(ps, [r["cob_ref_pct"] for r in rs], lw=2, ms=5, label=rot, **est)
        a2.plot(ps, [max(r["tempo_solucao_s"], 1e-3) for r in rs], lw=2, ms=5, label=rot, **est)
        nao = [r for r in rs if metodo == "MCLP" and not r["otimo"]]
        if nao:
            a2.scatter([r["p"] for r in nao], [r["tempo_solucao_s"] for r in nao], s=160, facecolors="none",
                       edgecolors="red", lw=2, zorder=6, label="limite de tempo (ótimo não provado)")
    for ax in (a1, a2):
        ax.axvline(p_destaque, color="gray", ls=":", lw=1)
        ax.set_xlabel("Número máximo de sensores $p$"); ax.grid(ls="--", alpha=.5)
        ax.set_xticks(sorted({r["p"] for r in linhas}))
    a1.set_ylim(0, 105)
    a1.set_ylabel(f"Cobertura ponderada (%) — avaliada na malha de {passo_ref:.1f} m".replace(".", ","))
    a1.set_title("Qualidade da solução"); a1.legend(loc="lower right")
    a2.set_yscale("log"); a2.set_ylabel("Tempo de solução (s, escala log)")
    a2.set_title("Custo computacional (K-Means: soma de 5 sementes)"); a2.legend(loc="upper left", fontsize=9)
    fig.suptitle("Salão do RU: malha 1,0 m x 0,5 m e MCLP (ótimo) x K-Means (heurística)",
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, .95)); fig.savefig(caminho_saida, dpi=300, bbox_inches="tight"); plt.close(fig)


def plotar_plantas_malhas(envs, solucoes, linhas, p, caminho_saida):
    """Grade 2 x 2 de plantas para um p: linhas = malha, colunas = método. O título de
    cada painel traz a cobertura na própria malha e na malha de referência."""
    passos = sorted(envs, reverse=True)
    env0 = envs[passos[0]]
    fig, axs = plt.subplots(len(passos), 2, figsize=(22, len(passos) * (4 + 5.2 * env0.comprimento / 26)))
    axs = np.atleast_2d(axs)
    for li, passo in enumerate(passos):
        for ci, metodo in enumerate(("MCLP", "K-Means")):
            ax, res = axs[li, ci], solucoes[(passo, metodo, p)]
            lin = next(r for r in linhas if r["malha_m"] == passo and r["metodo"] == metodo and r["p"] == p)
            km = metodo == "K-Means"
            titulo = (f"{'K-Means + snapping' if km else 'MCLP (PLI, CBC)'} — malha {passo:.1f} m — p = {p}\n"
                      f"cobertura {lin['cob_nativa_pct']:.1f}% (própria malha) | {lin['cob_ref_pct']:.1f}% (referência) | "
                      f"{lin['tempo_solucao_s']:.2f} s").replace(".", ",")
            _desenhar_planta_ru(ax, envs[passo], res, titulo=titulo,
                                rotulo="K-Means" if km else "ótimo",
                                cor_sensor="orange" if km else "lime",
                                cor_circulo="orange" if km else "limegreen",
                                cor_borda="darkorange" if km else "darkgreen")
            if km:
                for (cx, cy), (sx, sy) in zip(res["centroides_brutos"], res["sensores"]):
                    ax.plot([cx, sx], [cy, sy], color="red", ls="--", lw=1.2, zorder=7)
                    ax.scatter(cx, cy, marker="X", c="red", s=90, ec="k", zorder=8)
    fig.tight_layout(); fig.savefig(caminho_saida, dpi=300, bbox_inches="tight"); plt.close(fig)


def plotar_comparacao_manual(env, solucoes, linhas, caminho_saida):
    """Três plantas lado a lado, mesmo p: posições escolhidas pelo grupo, K-Means e MCLP."""
    estilos = {"Manual (grupo)": ("gold", "gold", "darkgoldenrod", "escolhido pelo grupo"),
               "K-Means": ("orange", "orange", "darkorange", "K-Means"),
               "MCLP (ótimo)": ("lime", "limegreen", "darkgreen", "ótimo")}
    fig, axs = plt.subplots(1, 3, figsize=(31, 4 + 5.2 * env.comprimento / 26))
    for ax, (metodo, res) in zip(axs, solucoes.items()):
        lin = next(r for r in linhas if r["metodo"] == metodo)
        cs, cc, cb, rot = estilos[metodo]
        titulo = (f"{metodo} — p = {res['p']}\n"
                  f"cobertura {lin['cob_total_pct']:.1f}% | mesas {lin.get('cob_mesas_pct', 0):.1f}%").replace(".", ",")
        _desenhar_planta_ru(ax, env, res, titulo=titulo, rotulo=rot, cor_sensor=cs, cor_circulo=cc, cor_borda=cb)
    p = linhas[0]["p"]
    tot = {r["metodo"]: r["cob_total_pct"] for r in linhas}
    fig.suptitle((f"Escolha do grupo x heurística x ótimo (p = {p}): "
                  f"{tot['Manual (grupo)']:.1f}% · {tot['K-Means']:.1f}% · {tot['MCLP (ótimo)']:.1f}%").replace(".", ","),
                 fontsize=16, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, .96)); fig.savefig(caminho_saida, dpi=300, bbox_inches="tight"); plt.close(fig)
