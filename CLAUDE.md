# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Course project for SME0510 (Pesquisa Operacional, USP São Carlos). It finds optimal placements for temperature sensors, modeled as a **Maximal Covering Location Problem** (MCLP, Church & ReVelle 1974) and solved as a binary integer program. Code comments, identifiers, terminal output and figure labels are in Portuguese; keep new ones in Portuguese.

**The current main scenario is `salao`:** the dining hall of the UFSCar São Carlos university restaurant (RU), with SHT31 sensors that can be hung from the ceiling anywhere on a 1 m grid. Its full modeling rules (sets, parameters, numbered constraints, assumptions, results) are in `docs/regras_modelagem_salao.md`; keep that file in sync when the salão model changes. `results/` holds only salão outputs: `results/salao/` (SHT31, main), `results/salao_raio050/` (half radius) and `results/salao_raio062/` (DHT22, `--fator-raio 0.625`). The `lab` and `ru` scenarios still run, but their outputs were deliberately removed.

The final report is `docs/relatorio_sme0510_sensores_ru.docx`. It was generated once with a docx-js script that is not kept in the repo, so edit the .docx directly. Its numbers come from the CSVs in `results/`; if the model changes, rerun the experiments and update the report, the README and `docs/regras_modelagem_salao.md` together. Author names are still placeholders (`[Nome 1]`…).

The final deliverable is a written report (5–30 pages: abstract, introduction, literature review, mathematical model with numbered constraints, computational experiments, conclusions). Reference papers live in `articles/`; the RU floor plan, sections and elevations (Graco Projetos) are in `img/`.

## Commands

All commands use the local virtualenv at `.venv` (Python 3.14).

```bash
.venv/bin/python main.py --cenario salao                    # main scenario: LSCP + sweep p=1..23 (~1 min) -> results/salao/
.venv/bin/python main.py --cenario salao --p 10 --apenas-p  # one MCLP only, no sweep/LSCP/K-Means (~5 s)
.venv/bin/python main.py --cenario salao --comparar-malhas --tempo-limite 600  # 1.0 m x 0.5 m grid, MCLP x K-Means (~4 min)
.venv/bin/python main.py --cenario salao --comparar-malhas --fator-raio 0.5  # half radius (scales every S; = doubling g_xy) -> results/salao_raio050/
.venv/bin/python main.py              # lab scenario: solve for p=6, sweep p=1..12, write results/
.venv/bin/python main.py --p 8        # chosen sensor count for the floor-plan figure
.venv/bin/python main.py --p-max 15   # extend the Pareto sweep
.venv/bin/python main.py --cenario ru # RU UFSCar scenario (default p=10), outputs in results/ru/
.venv/bin/python main.py --lscp       # also solve the set-cover variant (always on for ru and salao)
.venv/bin/python -m pip install -r requirements.txt          # pins numpy/pandas/matplotlib/pillow, PuLP>=3.3,<4
.venv/bin/python main.py --cenario salao --fator-raio 0.625  # DHT22 sensor instead of SHT31 -> results/salao_raio062/
```

There are no tests, linter or build step.

**PuLP must stay below 4.0.** PuLP 4.x no longer bundles CBC and removed `PULP_CBC_CMD` and `LpVariable.dicts`. With 4.x, `pulp.listSolvers(onlyAvailable=True)` returns `[]` and the solver fails. The code relies on the 3.x API.

## Architecture

Three scenarios share one solver: `salao` (main; `data/salao_geometria.json`), `ru` (whole UFSCar canteen; `data/ru_geometria.json`) and `lab` (USP lab, hard-coded in `lab_environment.py`). `salao` and `ru` are both built by `construir_ambiente_ru` from their JSON. `src/cenarios.py` loads either one into an object with the same interface (`I_coords`, `a`, `J_coords`, `N`, plus `grupos` for per-group coverage metrics, `obrigatorios` and `rotulo_j`). `lab_environment.py` must not change the lab results (p=6 → 96.85%); the lab-only grouping lives in `cenarios.py`.

The notes below describe the lab pipeline; the RU differs as listed after them.

The pipeline is `main.py` → `src/lab_environment.py` → `src/mclp_solver.py` → `src/visualizer.py`. Import modules as `src.<module>` and run from the repo root (the `src` modules use relative imports).

- **`lab_environment.py`** holds every modeling assumption as module-level constants and builds an `Ambiente` dataclass:
  - `I_coords`: 280 demand cells (10 × 7 m plan, 0.5 m step, centers 0.25…9.75 × 0.25…6.75).
  - `a`: weights per cell. `cat`: region label per cell (`rack`, `corredor_racks`, `ilha`, `bancada_sul`, `bancada_leste`, `corredor`).
  - `J_coords`: candidate sites (currently 81), a subset of the grid filtered by `candidato_valido`.
  - `N[i]`: indices into `J_coords` (not into the grid) of the candidates that cover demand cell `i`.
- **Coverage radius:** `S_XY = (DT_MAX - E_DHT22) / G_XY = 2.5 m`. Change the physical inputs, not `S_XY` directly.
- **Glass-partition barrier:** a candidate covers a cell only if both lie in the same sub-environment (`na_sala_racks`: `x <= 7.5 and y >= 5.0`), regardless of distance. Any new coverage rule must keep this check.
- **Exact float comparisons are intentional.** Grid coordinates are built from integer indices (`0.25 + 0.5*k`) and are exact in binary, so `y == 2.75` and `x in (0.25, 9.75)` are safe. Keep that construction if you change the grid; with a different step those equality tests (walls, corners, island axis) must be revisited.
- **`mclp_solver.py`:** `resolver_mclp(env, p)` builds and solves one model with CBC and raises if the status is not `Optimal`. It returns a dict with:
  - `sensores` (coordinates)
  - `cobertos` (a set of demand indices)
  - timing
  - weighted coverage percentages: total, `cob_racks_pct`, `cob_lab_pct`, and `cob_bancadas_pct` (island plus south and east benches)

  `varrer_pareto` loops `p = 1..p_max`, building an independent model for each `p`.
- **`visualizer.py`:** uses the `Agg` backend (it does not call `plt.show()`) and saves PNGs at `dpi=300`. It rebuilds the heat-map grid from the coordinates, so it assumes the regular grid from `lab_environment`.
- **`main.py`:**
  - writes `results/metricas_pareto.csv`, `results/planta_cobertura_otima.png` and `results/curva_pareto_sensores.png`
  - prints each chosen sensor's `(x, y)` and sub-environment
  - reuses the sweep result for `--p` when `p <= p_max`

### RU scenario

- `ru_environment.py` builds `AmbienteRU` (a subclass of `Ambiente`) from the JSON. It adds per-cell room, sub-region and coverage radius (`raio_i`), per-sensor radius (`raio_j`), wall segments and exclusion data.
- **Barrier rule:** `N[i]` holds candidates in the *same room* within the radius of cell `i`'s zone. Non-contiguous circulation areas are separate rooms (`C1`, `C2`, `C3`).
- **Geometry is data:** edit rooms, weights, radii, doors, equipment and pillars in the JSON, not in code. Room rectangles are half-open (`x0 <= x < x1`) and overlapping rooms raise an error.
- **Calibration:** `meta` in the JSON records the plan's scale (8.2 px/m) and origin; `plot_planta_ru(..., fundo=IMAGEM_PLANTA)` overlays the original plan for checking, and the image is only ~580×410 px, so positions are good to about ±0.5 m.
- `mclp_solver.py` also has `resolver_lscp`; `resolver_mclp(..., obrigatorios=True)` forces at least one sensor in each room marked `exige_sensor` (currently the cold rooms, `7`). In the `ru` scenario this restricted model is the main one; the unrestricted MCLP is solved as a comparison (CSV columns `*_sem_restricao_pct`). `--sem-obrigatorios` turns the restriction off.
- **Known result, not a bug:** about 27% of the RU cells (interior of the dining hall and kitchen) have no candidate within reach, since candidates are wall-adjacent. The LSCP therefore needs ~260 sensors for the coverable 66% of the weight. Revisit the candidate rules before drawing conclusions.
- PuLP's CBC wrapper does not expose the MIP gap, so results record `status` and `otimo` (solution proven optimal) instead.

### Salão scenario

- `--cenario salao` reuses `construir_ambiente_ru` with `data/salao_geometria.json` (`carregar_salao` in `cenarios.py`); outputs go to `results/salao/`.
- **Current configuration** (all in the JSON):
  - `malha.step = 1.0`, giving 626 demand cells;
  - `sensor` = SHT31 with `erro` 0.2 °C, replacing `e_dht22`; the radius is 4.0 m, or 2.29 m near the counters;
  - `candidatos.modo = "malha"`, which makes every grid cell a candidate (`tipo_j = "malha"`) before door and heat-source exclusions; this makes `--mesas` and the wall or pillar rules irrelevant here.
- Grid coordinates are `step * (k + 0.5)`, so with `step = 1.0` walls snap by up to 0.5 m. The `circulacao` zone (a 0.3 m wall strip) has no cells at this step.
- **Optional JSON keys** (absent in the RU file, so the RU is unchanged):
  - `linha_de_visada`: coverage also requires that the segment sensor–cell does not properly cross any wall edge or `divisorias` segment;
  - `divisorias`: internal partitions, which also count as walls for candidates;
  - `fontes_calor`: exclusion rectangles, merged with `equipamentos_vapor`;
  - a sub-region's `"suporte": "<tipo>"`, which turns the edges of that sub-region into candidates when the type is passed in `suportes`.
- Subregions are matched in order and the **last** match wins, so list broad zones (corridors) before specific ones (tables, counters).
- **K-Means baseline** (`resolver_kmeans`, `varrer_pareto_comparativo` in `mclp_solver.py`, numpy only): weighted K-Means (K-Means++ init, Lloyd) on `I_coords` with weights `a_i`, then snapping to the nearest unused candidate in `J`; scored with the same `env.N` and `env.a`, so it can never beat the proven-optimal MCLP. Runs by default for `salao` over `p = 1..15` (`--no-comparar-kmeans` turns it off), best of 5 seeds, reusing the MCLP results already in the sweep. Its result dict has the same keys as `resolver_mclp` (`cob_total_pct`, `cob_<grupo>_pct`, `idx_sensores`, `sensores`, `cobertos`, `status = "Heuristic (K-Means)"`) plus `centroides_brutos`, aligned with `sensores`. Outputs: `comparacao_*.csv/png`, `curva_pareto_mclp_vs_kmeans.png`.
- **Grid comparison** (`src/experimentos.py`, `--comparar-malhas`):
  - `construir_ambiente_ru(..., passo=0.5)` / `carregar_salao(passo=0.5)` overrides the JSON grid step.
  - Every solution is re-scored on the 0.5 m reference grid with `cobertos_por_coordenadas(env, coords)`, which applies the same room/radius/line-of-sight rules to arbitrary sensor coordinates.
  - At 0.5 m the MCLP has about 298k coverage links; each model takes 1–63 s and the full run about 4 min.
  - Expected oddity, not a bug: for p ≤ 11 the 1 m optimum scores higher on the 0.5 m grid than the 0.5 m optimum. 1 m candidates (x.5) are not in the 0.5 m candidate set (x.25/x.75), and a sensor on a fine-grid vertex reaches 208 fine points within 4 m vs 197 when it sits on a fine-grid point.
- **Manual placement** (`--manual [json]`, `comparar_manual` in `experimentos.py`): scores hand-picked coordinates from `data/salao_sensores_manuais.json` (12 positions read off `img/estimativa_sensores.png`) at their exact positions with `cobertos_por_coordenadas`, against MCLP and K-Means for the same p. Outputs `comparacao_manual.csv` and `comparacao_manual_plantas.png`.
- Line-of-sight checks are vectorized (`_bloqueados`); `_cruza` is kept for single segments.
- `tipo_j` records the support type of each candidate (parede, divisória, pilar, borda de mesa, balcão).
- Solve times: each MCLP takes 0.2–8 s with the current configuration. The older wall-only variant with `--mesas` (0.5 m grid, DHT22) was much harder, with up to 120 s per model.
- `main.py --apenas-p` solves only the chosen `p` and writes `planta<nome>_p<p>.png` and `metricas<nome>_p<p>.csv`. Extra sweep points between `p_max` and the LSCP value skip values already in the sweep.

## Modeling caveats to keep in mind

These come up when writing the report or extending the model:
- All scenarios are 2D. In `lab`, `Z_LAB = 1.1` and `Z_RACK = 1.5` are documentation-only constants. In `salao`, the plane is z = 1.1 m, but a ceiling-hung sensor would sit at about 2–2.5 m; this limitation is not modeled.
- The weights `a_i`, the gradients (0.20 and 0.35 °C/m) and the tolerance `ΔT_max = 1.0 °C` are assumptions, as is the SHT31's ±0.2 °C (a typical value). Their sources (ISO 7726, the classroom-temperature paper) still need to be checked before the report cites them.
