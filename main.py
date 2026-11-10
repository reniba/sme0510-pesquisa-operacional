import argparse
import os
import time

import numpy as np
import pandas as pd

from src.cenarios import carregar_lab, carregar_ru, carregar_salao
from src.mclp_solver import resolver_mclp, resolver_lscp, varrer_pareto, varrer_pareto_comparativo
from src.visualizer import (plot_planta, plot_pareto, plot_planta_ru, plot_pareto_grupos,
                            plotar_comparacao_planta, plotar_curva_pareto_comparativa,
                            plotar_comparacao_malhas, plotar_plantas_malhas, plotar_comparacao_manual)
from src.ru_environment import IMAGEM_PLANTA
from src.experimentos import comparar_malhas, comparar_manual

PADROES = {"lab": dict(p=6, p_max=12, tempo_limite=None),
           "ru": dict(p=10, p_max=15, tempo_limite=120),
           "salao": dict(p=10, p_max=20, tempo_limite=120)}


def tabela(resultados, env, extra=None):
    linhas = []
    for k, r in enumerate(resultados):
        lin = {"p": r["p"], "tempo_s": round(r["tempo_s"], 4), "status": r["status"],
               "otimo": r["otimo"], "n_vars": r["n_vars"], "n_restr": r["n_restr"],
               "cob_total_pct": round(r["cob_total_pct"], 2)}
        for g in env.grupos:
            lin[f"cob_{g}_pct"] = round(r[f"cob_{g}_pct"], 2)
        if extra:
            lin["cob_total_sem_restricao_pct"] = round(extra[k]["cob_total_pct"], 2)
            if "cob_camaras_pct" in extra[k]:
                lin["cob_camaras_sem_restricao_pct"] = round(extra[k]["cob_camaras_pct"], 2)
        lin["sensores"] = "; ".join(f"({x:.2f},{y:.2f})" for x, y in r["sensores"])
        linhas.append(lin)
    return pd.DataFrame(linhas)


def comparar_kmeans(env, pareto, saida, p_alvo, p_comp=15):
    """MCLP (PLI exata) x K-Means ponderado + snapping, para p = 1..p_comp."""
    comp = varrer_pareto_comparativo(env, p_max=p_comp, mclp={r["p"]: r for r in pareto})
    cols = [c for c in comp[0] if not c.startswith("res_")]
    df = pd.DataFrame([{c: r[c] for c in cols} for r in comp]).round(4)
    df.to_csv(f"{saida}/comparacao_mclp_vs_kmeans.csv", index=False)

    print("\nComparação MCLP (CBC) vs K-Means ponderado + snapping (melhor de 5 sementes)")
    print(f"{'p':>3} {'Cobertura MCLP %':>17} {'Cobertura K-Means %':>20} {'Ganho (p.p.)':>13} "
          f"{'Tempo MCLP (s)':>15} {'Tempo K-Means (s)':>18}")
    for r in comp:
        print(f"{r['p']:>3} {r['cob_mclp_pct']:>17.2f} {r['cob_kmeans_pct']:>20.2f} {r['ganho_pp']:>13.2f} "
              f"{r['tempo_mclp_s']:>15.3f} {r['tempo_kmeans_s']:>18.3f}")
    ganhos = [r["ganho_pp"] for r in comp]
    print(f"Ganho médio da PLI: {sum(ganhos)/len(ganhos):.2f} p.p. (máximo {max(ganhos):.2f} p.p. em "
          f"p={comp[ganhos.index(max(ganhos))]['p']}); K-Means chegou a empatar com o ótimo em "
          f"{sum(1 for g in ganhos if g < 1e-6)} de {len(ganhos)} valores de p")
    if min(ganhos) < -1e-6:
        print("AVISO: ganho negativo; algum MCLP não foi provado ótimo (ver coluna mclp_otimo).")

    p_graf = p_alvo if p_alvo <= p_comp else p_comp
    ref = next(r for r in comp if r["p"] == p_graf)
    plotar_comparacao_planta(env, ref["res_mclp"], ref["res_kmeans"], f"{saida}/comparacao_planta_mclp_vs_kmeans.png")
    plotar_curva_pareto_comparativa(comp, f"{saida}/curva_pareto_mclp_vs_kmeans.png", p_graf)
    print(f"Gerados em {saida}/: comparacao_mclp_vs_kmeans.csv, comparacao_planta_mclp_vs_kmeans.png, "
          "curva_pareto_mclp_vs_kmeans.png")


def experimento_malhas(p_alvo, p_max, tempo_limite, saida="results/salao", fator_raio=1.0):
    """4 cenários: {malha 1,0 m, 0,5 m} x {MCLP, K-Means}, p = 1..p_max."""
    os.makedirs(saida, exist_ok=True)
    t0 = time.perf_counter()
    envs, linhas, sols, ref = comparar_malhas(p_max=p_max, tempo_limite=tempo_limite, fator_raio=fator_raio)
    df = pd.DataFrame(linhas)
    df.round(4).to_csv(f"{saida}/comparacao_malhas.csv", index=False)

    tab = df.pivot_table(index="p", columns="cenario", values=["cob_ref_pct", "tempo_solucao_s"])
    ordem = ["MCLP 1,0 m", "MCLP 0,5 m", "K-Means 1,0 m", "K-Means 0,5 m"]
    print(f"\nCobertura ponderada (%) avaliada na malha de referência ({ref:.1f} m)")
    print(tab["cob_ref_pct"][ordem].round(2).to_string())
    print("\nTempo de solução (s)")
    print(tab["tempo_solucao_s"][ordem].round(3).to_string())
    tot = df.groupby("cenario")["tempo_solucao_s"].sum()[ordem]
    print("\nTempo total de solução por cenário (s):", ", ".join(f"{c}: {v:.1f}" for c, v in tot.items()))
    nao = df[(df.metodo == "MCLP") & (~df.otimo.astype(bool))]
    if len(nao):
        print(f"AVISO: {len(nao)} MCLP não provados ótimos no limite de {tempo_limite:.0f} s: "
              + ", ".join(f"{r.cenario} p={r.p}" for r in nao.itertuples()))

    p_graf = min(p_alvo, p_max)
    plotar_comparacao_malhas(linhas, f"{saida}/comparacao_malhas_curvas.png", ref, p_graf)
    plotar_plantas_malhas(envs, sols, linhas, p_graf, f"{saida}/comparacao_malhas_plantas_p{p_graf}.png")
    print(f"\nGerados em {saida}/: comparacao_malhas.csv, comparacao_malhas_curvas.png, "
          f"comparacao_malhas_plantas_p{p_graf}.png  (tempo total {time.perf_counter() - t0:.0f} s)")


def experimento_manual(caminho_json, saida, tempo_limite, fator_raio=1.0):
    """Posições escolhidas pelo grupo x K-Means x MCLP, para o mesmo p."""
    os.makedirs(saida, exist_ok=True)
    env, sols, linhas, avisos = comparar_manual(caminho_json, tempo_limite=tempo_limite, fator_raio=fator_raio)
    for a in avisos:
        print("AVISO (posição manual fora das regras):", a)
    df = pd.DataFrame(linhas)
    df.round(4).to_csv(f"{saida}/comparacao_manual.csv", index=False)
    p = linhas[0]["p"]
    cols = ["metodo", "cob_total_pct", "cob_ref_pct"] + [f"cob_{g}_pct" for g in env.grupos if g != "circulacao"] + ["tempo_s"]
    print(f"\nComparação para p = {p} (malha de 1,0 m; cob_ref_pct = avaliada na malha de 0,5 m)")
    print(df[cols].round(2).to_string(index=False))
    man, ot = linhas[0]["cob_total_pct"], linhas[-1]["cob_total_pct"]
    print(f"\nO ótimo cobre {ot - man:.2f} p.p. a mais que a escolha manual ({100 * (ot - man) / man:.1f}% a mais).")
    plotar_comparacao_manual(env, sols, linhas, f"{saida}/comparacao_manual_plantas.png")
    print(f"Gerados em {saida}/: comparacao_manual.csv, comparacao_manual_plantas.png")


def main():
    ap = argparse.ArgumentParser(description="MCLP: posicionamento ótimo de sensores de temperatura")
    ap.add_argument("--cenario", choices=["lab", "ru", "salao"], default="lab")
    ap.add_argument("--p", type=int, help="número de sensores (lab: 6, ru e salao: 10)")
    ap.add_argument("--p-max", type=int, help="limite da curva de Pareto (lab: 12, ru: 15, salao: 20)")
    ap.add_argument("--lscp", action="store_true", help="resolve também o LSCP (sempre ligado no ru e no salao)")
    ap.add_argument("--mesas", action="store_true",
                    help="salao: permite sensores nas bordas dos blocos de mesas")
    ap.add_argument("--tempo-limite", type=float, help="limite do CBC por modelo, em s (ru: 120)")
    ap.add_argument("--balcoes", action="store_true", help="ru: inclui as faces dos balcões como candidatos")
    ap.add_argument("--comparar-kmeans", action=argparse.BooleanOptionalAction, default=None,
                    help="compara o MCLP com o K-Means + snapping para p = 1..15 (padrão: ligado no salao)")
    ap.add_argument("--fator-raio", type=float, default=1.0,
                    help="salao: multiplica os raios de cobertura (0.5 = metade); saídas em "
                         "results/salao_raio<fator x 100>/")
    ap.add_argument("--manual", nargs="?", const="data/salao_sensores_manuais.json",
                    help="salao: compara posições escolhidas à mão (JSON) com K-Means e MCLP para o mesmo p")
    ap.add_argument("--comparar-malhas", action="store_true",
                    help="salao: compara malha 1,0 m x 0,5 m e MCLP x K-Means para p = 1..15")
    ap.add_argument("--apenas-p", action="store_true",
                    help="resolve só o p escolhido (sem varredura de Pareto nem LSCP)")
    ap.add_argument("--sem-obrigatorios", action="store_true",
                    help="ru: desliga a restrição de ao menos 1 sensor em cada câmara")
    args = ap.parse_args()
    ru = args.cenario != "lab"  # cenários construídos a partir de JSON (ru, salao)
    pad = PADROES[args.cenario]
    p_alvo = args.p or pad["p"]
    p_max = max(args.p_max or pad["p_max"], p_alvo)
    tl = args.tempo_limite or pad["tempo_limite"]
    pasta_salao = "results/salao" + ("_mesas" if args.mesas else "") + \
        (f"_raio{round(args.fator_raio * 100):03d}" if args.fator_raio != 1.0 else "")
    if args.manual:
        experimento_manual(args.manual, pasta_salao, args.tempo_limite or 600, args.fator_raio)
        return
    if args.comparar_malhas:
        experimento_malhas(p_alvo, args.p_max or 15, args.tempo_limite or 600, pasta_salao, args.fator_raio)
        return

    saida = {"lab": "results", "ru": "results/ru", "salao": pasta_salao}[args.cenario]
    os.makedirs(saida, exist_ok=True)
    env = {"lab": carregar_lab, "ru": lambda: carregar_ru(args.balcoes),
           "salao": lambda: carregar_salao(args.mesas, fator_raio=args.fator_raio)}[args.cenario]()
    print(f"[{args.cenario}] |I|={len(env.I_coords)} demanda, |J|={len(env.J_coords)} candidatos, "
          f"{len(env.nao_cobriveis) if ru else 0} células sem nenhum candidato ao alcance")

    if args.apenas_p:
        obrig = bool(getattr(env, "obrigatorios", None)) and not args.sem_obrigatorios
        res = resolver_mclp(env, p_alvo, obrigatorios=obrig, tempo_limite=tl)
        nome = {"lab": "", "ru": "_ru", "salao": "_salao"}[args.cenario]
        tabela([res], env).to_csv(f"{saida}/metricas{nome}_p{p_alvo}.csv", index=False)
        print(f"p={p_alvo}: {res['tempo_s']:.1f} s, status {res['status']}, ótimo provado: {res['otimo']}, "
              f"{res['n_vars']} variáveis, {res['n_restr']} restrições")
        print(f"Cobertura ponderada total: {res['cob_total_pct']:.2f}%")
        for g in env.grupos:
            print(f"  {g:20s} {res[f'cob_{g}_pct']:6.2f}%")
        print(f"\nSensores {getattr(env, 'sensor', 'DHT22')} (p={p_alvo}):")
        for k, (j, (x, y)) in enumerate(zip(res["idx_sensores"], res["sensores"]), 1):
            extra = f"  S={env.raio_j[j]:.2f} m" if ru else ""
            print(f"  S{k}: (x={x:.2f}, y={y:.2f})  {env.rotulo_j[j]}{extra}")
        if ru:
            plot_planta_ru(env, res, f"{saida}/planta{nome}_p{p_alvo}.png")
        else:
            plot_planta(env, res, f"{saida}/planta_p{p_alvo}.png")
        print(f"\nGerados em {saida}/: planta{nome}_p{p_alvo}.png, metricas{nome}_p{p_alvo}.csv")
        return

    ps = list(range(1, p_max + 1))
    lscp = None
    if ru or args.lscp:
        lscp = resolver_lscp(env, tl)
        print(f"LSCP: {lscp['p_min']} sensores cobrem 100% do que é coberturável "
              f"({100 - lscp['peso_nao_cobrivel_pct']:.1f}% do peso total; status {lscp['status']}, "
              f"{lscp['tempo_s']:.1f} s)")
        if lscp["p_min"] > p_max:  # alguns pontos espaçados entre p_max e o p do LSCP
            ps += sorted({int(v) for v in np.linspace(p_max, lscp["p_min"], 9)[1:]} - set(ps))

    # Cenário principal do RU: ao menos 1 sensor em cada câmara (salas com "exige_sensor").
    # O MCLP sem a restrição é resolvido também, como comparação.
    obrig = bool(getattr(env, "obrigatorios", None)) and not args.sem_obrigatorios
    if obrig:
        print("Restrição ativa: ao menos 1 sensor em " +
              ", ".join(f"{nome} (cômodo {sid})" for sid, nome, _ in env.obrigatorios))
    pareto = varrer_pareto(env, ps=ps, obrigatorios=obrig, tempo_limite=tl)
    alt = varrer_pareto(env, ps=ps, tempo_limite=tl) if obrig else None
    df = tabela(pareto, env, alt)
    nome = {"lab": "", "ru": "_ru", "salao": "_salao"}[args.cenario]
    csv = os.path.join(saida, f"metricas{nome}_pareto.csv")
    df.to_csv(csv, index=False)
    print(df.drop(columns=["sensores", "n_vars", "n_restr"]).to_string(index=False))

    res = next((r for r in pareto if r["p"] == p_alvo), None) or resolver_mclp(env, p_alvo, obrigatorios=obrig, tempo_limite=tl)
    print(f"\nSensores {getattr(env, 'sensor', 'DHT22')} para p={p_alvo} (cobertura {res['cob_total_pct']:.2f}%):")
    for k, (j, (x, y)) in enumerate(zip(res["idx_sensores"], res["sensores"]), 1):
        extra = f"  S={env.raio_j[j]:.2f} m" if ru else ""
        print(f"  S{k}: (x={x:.2f}, y={y:.2f})  {env.rotulo_j[j]}{extra}")

    if ru:
        plot_planta_ru(env, res, f"{saida}/planta{nome}_cobertura.png")
        plot_planta_ru(env, None, f"{saida}/sobreposicao_planta.png", fundo=IMAGEM_PLANTA)
        plot_pareto_grupos(pareto, f"{saida}/curva_pareto{nome}.png", list(env.grupos), p_alvo,
                           lscp["p_min"] if lscp else None, alt, f"{env.nome}: sensores × cobertura", p_fim=p_max)
        print(f"\nGerados em {saida}/: planta{nome}_cobertura.png, sobreposicao_planta.png, "
              f"curva_pareto{nome}.png, metricas{nome}_pareto.csv")
        if args.comparar_kmeans is None or args.comparar_kmeans:
            if args.comparar_kmeans or args.cenario == "salao":
                comparar_kmeans(env, pareto, saida, p_alvo)
    else:
        plot_planta(env, res, "results/planta_cobertura_otima.png")
        plot_pareto(pareto, "results/curva_pareto_sensores.png", p_alvo)
        print("\nGerados: results/planta_cobertura_otima.png, curva_pareto_sensores.png, metricas_pareto.csv")


if __name__ == "__main__":
    main()
