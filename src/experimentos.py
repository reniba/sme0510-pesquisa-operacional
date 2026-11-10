"""Experimento: efeito da resolução da malha (1,0 m x 0,5 m) e do método de solução
(MCLP exato x K-Means + snapping) no salão de refeições.

Os 4 cenários são {malha 1,0 m, malha 0,5 m} x {MCLP (CBC), K-Means}. Como cada malha
tem seus próprios pontos de demanda, a cobertura de toda solução é avaliada também
numa malha de referência comum (a mais fina), com as mesmas regras de cobertura.
"""
import time

import numpy as np

from .cenarios import carregar_salao
from .mclp_solver import resolver_kmeans, resolver_mclp
from .ru_environment import cobertos_por_coordenadas


def comparar_malhas(passos=(1.0, 0.5), p_max=15, seed=42, n_sementes=5, tempo_limite=600, log=print,
                    fator_raio=1.0):
    """Retorna (envs, linhas, solucoes):
    - envs: {passo: ambiente}
    - linhas: uma por (malha, método, p), com cobertura nativa, cobertura na malha de
      referência, tempo de solução e de construção da malha, status e tamanho do modelo
    - solucoes: {(passo, método, p): resultado completo}"""
    envs, t_constr = {}, {}
    for passo in passos:
        t0 = time.perf_counter()
        envs[passo] = carregar_salao(passo=passo, fator_raio=fator_raio)
        t_constr[passo] = time.perf_counter() - t0
        e = envs[passo]
        log(f"malha {passo:.1f} m: |I|={len(e.I_coords)} |J|={len(e.J_coords)} "
            f"ligações={sum(len(n) for n in e.N)} construção {t_constr[passo]:.1f} s")
    passo_ref = min(passos)
    ref = envs[passo_ref]
    peso_ref = sum(ref.a)

    def cob_ref(res):
        cob = cobertos_por_coordenadas(ref, res["sensores"])
        return 100.0 * sum(ref.a[i] for i in cob) / peso_ref

    linhas, solucoes = [], {}
    for passo, env in envs.items():
        for p in range(1, p_max + 1):
            m = resolver_mclp(env, p, tempo_limite=tempo_limite)
            ks = [resolver_kmeans(env, p, seed=seed + k) for k in range(n_sementes)]
            kb = max(ks, key=lambda r: r["cob_total_pct"])
            t_k = float(sum(r["tempo_s"] for r in ks))
            for metodo, res, t in (("MCLP", m, m["tempo_s"]), ("K-Means", kb, t_k)):
                solucoes[(passo, metodo, p)] = res
                linhas.append({
                    "cenario": f"{metodo} {passo:.1f} m".replace(".", ","),
                    "malha_m": passo, "metodo": metodo, "p": p,
                    "cob_nativa_pct": res["cob_total_pct"],
                    "cob_ref_pct": cob_ref(res),
                    "cob_kmeans_media_pct": (float(np.mean([r["cob_total_pct"] for r in ks]))
                                             if metodo == "K-Means" else None),
                    "tempo_solucao_s": t,
                    "tempo_construcao_malha_s": t_constr[passo],
                    "status": res["status"], "otimo": res["otimo"],
                    "n_vars": res.get("n_vars"), "n_restr": res.get("n_restr"),
                    "n_I": len(env.I_coords), "n_J": len(env.J_coords),
                    "sensores": "; ".join(f"({x:.2f},{y:.2f})" for x, y in res["sensores"]),
                })
            log(f"  malha {passo:.1f} m, p={p:2d}: MCLP {m['cob_total_pct']:6.2f}% em {m['tempo_s']:7.1f} s"
                f"{'' if m['otimo'] else ' (NÃO provado ótimo)'} | K-Means {kb['cob_total_pct']:6.2f}% em {t_k:5.2f} s")
    return envs, linhas, solucoes, passo_ref


def comparar_manual(caminho_json, passo=1.0, passo_ref=0.5, seed=42, n_sementes=5, tempo_limite=600,
                    fator_raio=1.0):
    """Compara sensores em posições escolhidas à mão (JSON com a lista "sensores" de
    [x, y] em metros) com o MCLP e o K-Means para o MESMO p = número de posições.
    As posições manuais são avaliadas exatamente onde estão (sem ajuste à malha), com
    as mesmas regras de cobertura, na malha do modelo e na malha de referência."""
    import json
    import math
    from .mclp_solver import _metricas
    with open(caminho_json, encoding="utf-8") as f:
        coords = [tuple(c) for c in json.load(f)["sensores"]]
    p = len(coords)
    env = carregar_salao(passo=passo, fator_raio=fator_raio)
    ref = carregar_salao(passo=passo_ref, fator_raio=fator_raio)
    peso_ref = sum(ref.a)

    def cob_ref(cs):
        cob = cobertos_por_coordenadas(ref, cs)
        return 100.0 * sum(ref.a[i] for i in cob) / peso_ref

    # posições manuais: regras de exclusão e cobertura exata
    avisos = []
    for x, y in coords:
        for porta in env.portas:
            if math.hypot(x - porta["x"], y - porta["y"]) < env.raio_porta:
                avisos.append(f"({x}, {y}) a menos de {env.raio_porta} m da porta {porta['id']}")
        for q in env.equipamentos:
            x0, y0, x1, y1 = q["retangulo"]
            if math.hypot(max(x0 - x, 0, x - x1), max(y0 - y, 0, y - y1)) < q["margem"]:
                avisos.append(f"({x}, {y}) a menos de {q['margem']} m de {q['id']}")
    t0 = time.perf_counter()
    cob = cobertos_por_coordenadas(env, coords)
    t_man = time.perf_counter() - t0
    Jc = np.asarray(env.J_coords, float)
    idx_prox = [int(np.argmin(np.hypot(Jc[:, 0] - x, Jc[:, 1] - y))) for x, y in coords]  # só p/ o raio no desenho
    manual = {"p": p, "tempo_s": t_man, "status": "Manual", "otimo": False, "idx_sensores": idx_prox,
              "sensores": coords, "cobertos": cob, **_metricas(env, cob)}

    m = resolver_mclp(env, p, tempo_limite=tempo_limite)
    ks = [resolver_kmeans(env, p, seed=seed + k) for k in range(n_sementes)]
    kb = max(ks, key=lambda r: r["cob_total_pct"])
    kb = dict(kb, tempo_s=float(sum(r["tempo_s"] for r in ks)))

    linhas = []
    for metodo, res in (("Manual (grupo)", manual), ("K-Means", kb), ("MCLP (ótimo)", m)):
        lin = {"metodo": metodo, "p": p, "malha_m": passo,
               "cob_total_pct": res["cob_total_pct"], "cob_ref_pct": cob_ref(res["sensores"]),
               "tempo_s": res["tempo_s"], "otimo": res["otimo"]}
        for g in env.grupos:
            lin[f"cob_{g}_pct"] = res[f"cob_{g}_pct"]
        lin["sensores"] = "; ".join(f"({x:.2f},{y:.2f})" for x, y in res["sensores"])
        linhas.append(lin)
    return env, {"Manual (grupo)": manual, "K-Means": kb, "MCLP (ótimo)": m}, linhas, avisos
