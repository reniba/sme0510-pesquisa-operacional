"""MCLP (Church & ReVelle, 1974) em PuLP/CBC."""
import time
import pulp
from .lab_environment import na_sala_racks, subambiente


def _pct(env, cobertos, filtro):
    idx = [i for i in range(len(env.I_coords)) if filtro(i)]
    tot = sum(env.a[i] for i in idx)
    cob = sum(env.a[i] for i in idx if i in cobertos)
    return 100.0 * cob / tot if tot else 0.0


def resolver_mclp(env, p):
    I, J = range(len(env.I_coords)), range(len(env.J_coords))
    prob = pulp.LpProblem(f"MCLP_p{p}", pulp.LpMaximize)
    x = pulp.LpVariable.dicts("x", J, cat="Binary")
    y = pulp.LpVariable.dicts("y", I, cat="Binary")
    prob += pulp.lpSum(env.a[i] * y[i] for i in I)
    for i in I:
        prob += pulp.lpSum(x[j] for j in env.N[i]) >= y[i]
    prob += pulp.lpSum(x[j] for j in J) <= p
    t0 = time.perf_counter()
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    dt = time.perf_counter() - t0
    if pulp.LpStatus[prob.status] != "Optimal":
        raise RuntimeError(f"Solver não ótimo para p={p}: {pulp.LpStatus[prob.status]}")
    sensores = [j for j in J if x[j].value() > 0.5]
    cobertos = {i for i in I if y[i].value() > 0.5}
    total = sum(env.a)
    is_rack = lambda i: na_sala_racks(*env.I_coords[i])
    return {
        "p": p,
        "tempo_s": dt,
        "sensores": [env.J_coords[j] for j in sensores],
        "cobertos": cobertos,
        "cob_total_pct": 100.0 * sum(env.a[i] for i in cobertos) / total,
        "cob_racks_pct": _pct(env, cobertos, is_rack),
        "cob_bancadas_pct": _pct(env, cobertos, lambda i: env.cat[i] in ("ilha", "bancada_sul", "bancada_leste")),
        "cob_lab_pct": _pct(env, cobertos, lambda i: not is_rack(i)),
    }


def varrer_pareto(env, p_max=12):
    return [resolver_mclp(env, p) for p in range(1, p_max + 1)]
