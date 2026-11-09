import argparse
import os

import numpy as np
import pandas as pd

from src.cenarios import carregar_lab, carregar_ru, carregar_salao
from src.mclp_solver import resolver_mclp, resolver_lscp, varrer_pareto
from src.visualizer import plot_planta, plot_pareto, plot_planta_ru, plot_pareto_grupos
from src.ru_environment import IMAGEM_PLANTA

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

    saida = {"lab": "results", "ru": "results/ru",
             "salao": "results/salao_mesas" if args.mesas else "results/salao"}[args.cenario]
    os.makedirs(saida, exist_ok=True)
    env = {"lab": carregar_lab, "ru": lambda: carregar_ru(args.balcoes),
           "salao": lambda: carregar_salao(args.mesas)}[args.cenario]()
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
    else:
        plot_planta(env, res, "results/planta_cobertura_otima.png")
        plot_pareto(pareto, "results/curva_pareto_sensores.png", p_alvo)
        print("\nGerados: results/planta_cobertura_otima.png, curva_pareto_sensores.png, metricas_pareto.csv")


if __name__ == "__main__":
    main()
