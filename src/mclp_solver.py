"""MCLP (Church & ReVelle, 1974) e LSCP em PuLP/CBC, independentes do cenário.

O ambiente (`env`) precisa de: I_coords, a, J_coords, N. Opcionais:
  env.grupos       dict nome -> índices i; gera as colunas cob_<nome>_pct
  env.obrigatorios lista (id, nome, [j...]); com obrigatorios=True exige >= 1 sensor em cada
"""
import time

import numpy as np
import pulp


def _metricas(env, cobertos):
    total = sum(env.a)
    out = {"cob_total_pct": 100.0 * sum(env.a[i] for i in cobertos) / total}
    for nome, idx in (getattr(env, "grupos", None) or {}).items():
        tot = sum(env.a[i] for i in idx)
        cob = sum(env.a[i] for i in idx if i in cobertos)
        out[f"cob_{nome}_pct"] = 100.0 * cob / tot if tot else 0.0
    return out


def _resolver(prob, tempo_limite):
    t0 = time.perf_counter()
    prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=tempo_limite))
    dt = time.perf_counter() - t0
    status = pulp.LpStatus[prob.status]
    if status != "Optimal" and prob.sol_status != pulp.LpSolutionIntegerFeasible:
        raise RuntimeError(f"Solver sem solução ({prob.name}): {status}")
    otimo = prob.sol_status == pulp.LpSolutionOptimal
    return dt, status, otimo


def _cobertos(env, escolhidos):
    s = set(escolhidos)
    return {i for i in range(len(env.I_coords)) if any(j in s for j in env.N[i])}


def resolver_mclp(env, p, obrigatorios=False, tempo_limite=None):
    I, J = range(len(env.I_coords)), range(len(env.J_coords))
    cobertaveis = [i for i in I if env.N[i]]
    prob = pulp.LpProblem(f"MCLP_p{p}", pulp.LpMaximize)
    x = pulp.LpVariable.dicts("x", J, cat="Binary")
    y = pulp.LpVariable.dicts("y", cobertaveis, cat="Binary")
    prob += pulp.lpSum(env.a[i] * y[i] for i in cobertaveis)
    for i in cobertaveis:
        prob += pulp.lpSum(x[j] for j in env.N[i]) >= y[i]
    prob += pulp.lpSum(x[j] for j in J) <= p
    if obrigatorios:
        for _, _, js in getattr(env, "obrigatorios", []):
            prob += pulp.lpSum(x[j] for j in js) >= 1
    dt, status, otimo = _resolver(prob, tempo_limite)
    escolhidos = [j for j in J if x[j].value() > 0.5]
    cob = _cobertos(env, escolhidos)
    return {
        "p": p, "tempo_s": dt, "status": status, "otimo": otimo,
        "n_vars": len(prob.variables()), "n_restr": len(prob.constraints),
        "idx_sensores": escolhidos,
        "sensores": [env.J_coords[j] for j in escolhidos],
        "cobertos": cob, **_metricas(env, cob),
    }


def resolver_lscp(env, tempo_limite=None):
    """Mínimo de sensores para cobrir todas as células coberturáveis (N_i != vazio)."""
    I, J = range(len(env.I_coords)), range(len(env.J_coords))
    cobertaveis = [i for i in I if env.N[i]]
    nao_cob = [i for i in I if not env.N[i]]
    prob = pulp.LpProblem("LSCP", pulp.LpMinimize)
    x = pulp.LpVariable.dicts("x", J, cat="Binary")
    prob += pulp.lpSum(x[j] for j in J)
    for n in {tuple(env.N[i]) for i in cobertaveis}:  # restrições idênticas só uma vez
        prob += pulp.lpSum(x[j] for j in n) >= 1
    dt, status, otimo = _resolver(prob, tempo_limite)
    escolhidos = [j for j in J if x[j].value() > 0.5]
    cob = _cobertos(env, escolhidos)
    return {
        "p_min": len(escolhidos), "tempo_s": dt, "status": status, "otimo": otimo,
        "n_vars": len(prob.variables()), "n_restr": len(prob.constraints),
        "idx_sensores": escolhidos, "sensores": [env.J_coords[j] for j in escolhidos],
        "cobertos": cob, "nao_cobriveis": nao_cob,
        "peso_nao_cobrivel_pct": 100.0 * sum(env.a[i] for i in nao_cob) / sum(env.a),
        **_metricas(env, cob),
    }


def varrer_pareto(env, p_max=12, ps=None, **kw):
    """Resolve o MCLP para cada p em `ps` (padrão: 1..p_max)."""
    return [resolver_mclp(env, p, **kw) for p in (ps or range(1, p_max + 1))]


# ---------------------------------------------------------------------------
# Baseline geométrico: K-Means ponderado + snapping (Qin et al., 2023)
# ---------------------------------------------------------------------------
def _kmeans_ponderado(X, w, p, rng, max_iter, atol=1e-4):
    """K-Means (Lloyd) ponderado por `w`, com inicialização K-Means++ ponderada."""
    n = len(X)
    C = [X[rng.choice(n, p=w / w.sum())]]                      # 1º centroide ~ a_i
    d2 = ((X - C[0]) ** 2).sum(1)
    for _ in range(1, p):                                      # demais ~ a_i * min_dist^2
        pr = w * d2
        pr = pr / pr.sum() if pr.sum() > 0 else w / w.sum()    # tudo coincide: cai em a_i
        k = rng.choice(n, p=pr)
        C.append(X[k])
        d2 = np.minimum(d2, ((X - X[k]) ** 2).sum(1))
    C = np.array(C, dtype=float)
    n_iter = 0
    for n_iter in range(1, max_iter + 1):
        D = ((X[:, None, :] - C[None, :, :]) ** 2).sum(2)      # n x p
        rot = D.argmin(1)                                      # ponto -> centroide mais próximo
        Cn = C.copy()
        for k in range(p):
            m = rot == k
            if m.any():
                Cn[k] = np.average(X[m], axis=0, weights=w[m])  # média ponderada do cluster
            else:                                              # cluster vazio: reposiciona
                Cn[k] = X[np.argmax(w * D.min(1))]
        if np.allclose(Cn, C, rtol=0, atol=atol):
            C = Cn
            break
        C = Cn
    D = ((X[:, None, :] - C[None, :, :]) ** 2).sum(2)
    return C, D.argmin(1), n_iter


def resolver_kmeans(env, p, seed=42, max_iter=100):
    """K-Means ponderado pelos pesos a_i sobre env.I_coords, seguido de snapping: cada
    centroide contínuo vai para o candidato j em J mais próximo ainda não escolhido.
    A solução é avaliada com a mesma cobertura (env.N) e os mesmos pesos do MCLP.
    Retorna o mesmo formato de resolver_mclp, mais `centroides_brutos`, alinhados a
    `sensores` (mesma ordem)."""
    t0 = time.perf_counter()
    rng = np.random.default_rng(seed)
    X, w = np.asarray(env.I_coords, float), np.asarray(env.a, float)
    Jc = np.asarray(env.J_coords, float)
    if p > len(Jc):
        raise ValueError(f"p={p} maior que o número de candidatos ({len(Jc)})")
    C, rot, n_iter = _kmeans_ponderado(X, w, p, rng, max_iter)

    # snapping sem repetição; clusters de maior peso escolhem primeiro
    peso_cluster = np.array([w[rot == k].sum() for k in range(p)])
    escolhido = np.full(p, -1)
    usados = np.zeros(len(Jc), dtype=bool)
    for k in np.argsort(-peso_cluster, kind="stable"):
        d = np.hypot(Jc[:, 0] - C[k, 0], Jc[:, 1] - C[k, 1])
        d[usados] = np.inf
        j = int(np.argmin(d))
        escolhido[k] = j
        usados[j] = True
    desloc = [float(np.hypot(*(Jc[escolhido[k]] - C[k]))) for k in range(p)]

    idx = [int(j) for j in escolhido]
    cob = _cobertos(env, idx)
    return {
        "p": p, "tempo_s": time.perf_counter() - t0, "status": "Heuristic (K-Means)", "otimo": False,
        "seed": seed, "n_iter": n_iter, "desloc_snap_medio_m": float(np.mean(desloc)),
        "idx_sensores": idx, "sensores": [env.J_coords[j] for j in idx],
        "centroides_brutos": [(float(cx), float(cy)) for cx, cy in C],
        "cobertos": cob, **_metricas(env, cob),
    }


def varrer_pareto_comparativo(env, p_max=15, seed=42, n_sementes=5, mclp=None, **kw):
    """Para p = 1..p_max, resolve o MCLP e o K-Means (melhor e média de `n_sementes`
    sementes seed..seed+n_sementes-1). `mclp` pode trazer resultados já calculados
    ({p: resultado}) para não resolver de novo. Retorna uma lista de dicionários
    consolidados; `res_mclp` e `res_kmeans` guardam as soluções completas (a melhor
    semente do K-Means)."""
    grupos = list((getattr(env, "grupos", None) or {}))
    saida = []
    for p in range(1, p_max + 1):
        rm = (mclp or {}).get(p) or resolver_mclp(env, p, **kw)
        ks = [resolver_kmeans(env, p, seed=seed + k) for k in range(n_sementes)]
        rk = max(ks, key=lambda r: r["cob_total_pct"])
        lin = {
            "p": p,
            "cob_mclp_pct": rm["cob_total_pct"],
            "cob_kmeans_pct": rk["cob_total_pct"],
            "cob_kmeans_media_pct": float(np.mean([r["cob_total_pct"] for r in ks])),
            "ganho_pp": rm["cob_total_pct"] - rk["cob_total_pct"],
            "tempo_mclp_s": rm["tempo_s"],
            "tempo_kmeans_s": float(sum(r["tempo_s"] for r in ks)),
            "mclp_otimo": rm["otimo"], "semente_melhor": rk["seed"],
            "desloc_snap_medio_m": rk["desloc_snap_medio_m"],
        }
        lin["ganho_vs_media_pp"] = lin["cob_mclp_pct"] - lin["cob_kmeans_media_pct"]
        for g in grupos:
            lin[f"cob_{g}_mclp_pct"] = rm[f"cob_{g}_pct"]
            lin[f"cob_{g}_kmeans_pct"] = rk[f"cob_{g}_pct"]
        lin["res_mclp"], lin["res_kmeans"] = rm, rk
        saida.append(lin)
    return saida
