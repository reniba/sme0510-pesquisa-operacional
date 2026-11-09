import argparse
import os
import pandas as pd
from src.lab_environment import construir_ambiente, subambiente, S_XY
from src.mclp_solver import resolver_mclp, varrer_pareto
from src.visualizer import plot_planta, plot_pareto


def main():
    ap = argparse.ArgumentParser(description="MCLP: posicionamento ótimo de DHT22")
    ap.add_argument("--p", type=int, default=6, help="número de sensores (default 6)")
    ap.add_argument("--p-max", type=int, default=12, help="limite da curva de Pareto")
    args = ap.parse_args()

    os.makedirs("results", exist_ok=True)
    env = construir_ambiente()
    print(f"|I|={len(env.I_coords)} pontos de demanda, |J|={len(env.J_coords)} candidatos, S_xy={S_XY} m")

    pareto = varrer_pareto(env, max(args.p_max, args.p))
    df = pd.DataFrame([{
        "p": r["p"], "tempo_s": round(r["tempo_s"], 4),
        "cob_total_pct": round(r["cob_total_pct"], 2),
        "cob_racks_pct": round(r["cob_racks_pct"], 2),
        "cob_lab_pct": round(r["cob_lab_pct"], 2),
        "cob_bancadas_pct": round(r["cob_bancadas_pct"], 2),
        "sensores": "; ".join(f"({x:.2f},{y:.2f})" for x, y in r["sensores"]),
    } for r in pareto])
    df.to_csv("results/metricas_pareto.csv", index=False)
    print(df.drop(columns="sensores").to_string(index=False))

    res = next(r for r in pareto if r["p"] == args.p) if args.p <= len(pareto) else resolver_mclp(env, args.p)
    print(f"\nSensores DHT22 para p={args.p} (cobertura {res['cob_total_pct']:.2f}%):")
    for k, (x, y) in enumerate(res["sensores"], 1):
        print(f"  S{k}: (x={x:.2f}, y={y:.2f})  subambiente: {subambiente(x, y)}")

    plot_planta(env, res, "results/planta_cobertura_otima.png")
    plot_pareto(pareto, "results/curva_pareto_sensores.png", args.p)
    print("\nGerados: results/planta_cobertura_otima.png, curva_pareto_sensores.png, metricas_pareto.csv")


if __name__ == "__main__":
    main()
