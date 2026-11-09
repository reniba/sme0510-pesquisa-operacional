"""MCLP (Church & ReVelle, 1974) e LSCP em PuLP/CBC, independentes do cenário.

O ambiente (`env`) precisa de: I_coords, a, J_coords, N. Opcionais:
  env.grupos       dict nome -> índices i; gera as colunas cob_<nome>_pct
  env.obrigatorios lista (id, nome, [j...]); com obrigatorios=True exige >= 1 sensor em cada
"""
import time
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
