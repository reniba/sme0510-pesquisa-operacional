# Posicionamento ótimo de sensores de temperatura

Projeto da disciplina **SME0510 – Pesquisa Operacional** (ICMC/USP São Carlos).

O projeto decide onde instalar um número limitado de sensores de temperatura para monitorar, da melhor forma possível, o **salão de refeições do Restaurante Universitário (RU) da UFSCar São Carlos**. O problema é modelado como um **Problema de Localização de Cobertura Máxima** (*Maximal Covering Location Problem*, MCLP; Church & ReVelle, 1974) em programação linear inteira binária e resolvido em Python com PuLP e o solver CBC.

As regras completas do modelo, com conjuntos, parâmetros, variáveis e restrições numeradas, estão em **[docs/regras_modelagem_salao.md](docs/regras_modelagem_salao.md)**.

## O problema

Com no máximo `p` sensores, onde instalá-los para cobrir a maior "exposição térmica" possível dos alunos?

- **Domínio:** o salão de refeições, de cerca de 29 × 26 m com os dois pátios laterais descontados. A geometria foi digitalizada da planta baixa ([img/2_planta14.webp](img/2_planta14.webp)) e está em [data/salao_geometria.json](data/salao_geometria.json).
- **Malha:** pontos a cada 1 m, num total de 626 pontos de demanda.
- **Pesos:** representam a exposição dos ocupantes, isto é, a densidade de pessoas multiplicada pelo tempo de permanência.

  | Zona | Peso |
  |---|---|
  | mesas | 20 |
  | fila diante dos balcões | 16 |
  | corredor principal (entradas, eixo central e hall) | 10 |
  | corredores entre mesas | 6 |
  | balcões térmicos | 4 |

- **Sensor:** SHT31, com ±0,2 °C. O raio de cobertura vem de `S = (ΔT_max − e)/g`: 4,0 m nas mesas e corredores e 2,29 m perto dos balcões, onde o gradiente é maior.
- **Candidatos:** qualquer ponto da malha, com o sensor suspenso do teto. Ficam excluídos os pontos a menos de 1,5 m das portas externas e a menos de 1,0 m dos balcões térmicos.
- **Linha de visada:** um sensor não cobre pontos atrás de paredes ou das divisórias que separam as alas de mesas do corredor de entrada.

## Modelo

```
max  Σ_{i∈I'} a_i · y_i

s.a. (1)  Σ_{j∈N_i} x_j ≥ y_i     ∀ i ∈ I'     i só é coberto se houver sensor em N_i
     (2)  Σ_{j∈J}  x_j ≤ p                     limite de sensores
     (3)  x_j ∈ {0,1}             ∀ j ∈ J
     (4)  y_i ∈ {0,1}             ∀ i ∈ I'
```

- `N_i` é o conjunto de candidatos a até `S_i` metros do ponto `i`, com linha de visada livre.
- `I'` são os pontos com pelo menos um candidato ao alcance.
- O LSCP (mínimo de sensores para cobrir tudo o que é alcançável) define até onde vai a varredura de `p`.

## Resultados

| p | Cobertura total | Mesas | Corredor principal | Fila/serviço |
|---|---|---|---|---|
| 5 | 46,2% | 66,3% | 1,7% | 0% |
| 8 | 66,4% | 90,3% | 13,6% | 6,0% |
| **10** | **75,1%** | **90,3%** | **49,2%** | **24,0%** |
| 16 | 90,5% | 94,0% | 97,2% | 54,0% |
| 23 (LSCP) | 98,4% | 100% | 100% | 84,0% |

- **Prioridade das mesas:** os primeiros 8 sensores vão quase todos para as mesas, que já ficam 90% cobertas com p = 8.
- **Cobertura máxima:** 23 sensores cobrem tudo o que é alcançável. Isso dá 98,4% do peso total; os 12 pontos restantes ficam perto dos balcões e não têm nenhum candidato ao alcance.
- **Tempo:** todos os 23 modelos foram resolvidos com ótimo provado, em cerca de 42 s no total.

| Solução para p = 10 | Curva de trade-off |
|---|---|
| ![Planta](results/salao/planta_salao_p10.png) | ![Pareto](results/salao/curva_pareto_salao.png) |

## Como executar

Requer Python 3 e PuLP **3.x**. A versão 4.x do PuLP não traz mais o CBC embutido.

```bash
python -m venv .venv
.venv/bin/python -m pip install numpy matplotlib pandas "pulp>=3,<4"

.venv/bin/python main.py --cenario salao                  # varredura p = 1..23 e LSCP (~1 min)
.venv/bin/python main.py --cenario salao --p 10 --apenas-p  # resolve só p = 10 (~5 s)
```

Saídas em `results/salao/`:

| Arquivo | Conteúdo |
|---|---|
| `planta_salao_p10.png` / `planta_salao_cobertura.png` | planta com os pesos, as divisórias, as exclusões, os candidatos e os sensores escolhidos com seus raios |
| `curva_pareto_salao.png` | cobertura total e por zona em função de `p` |
| `metricas_salao_pareto.csv` / `metricas_salao_p10.csv` | tempo, status, cobertura por zona e posições dos sensores |
| `sobreposicao_planta.png` | geometria digitalizada sobre a planta original, para conferência |

## Cenários anteriores

O código também tem dois cenários desenvolvidos antes. Os resultados deles não estão no repositório, mas podem ser gerados de novo.

- **Laboratório de computadores (USP), `--cenario lab`:** planta de 10 × 7 m com sala de racks separada por divisória de vidro e sensores DHT22 nas paredes. Com p = 6, cobre 96,85%. Saídas em `results/`.
- **RU completo, `--cenario ru`:** 20 cômodos (salão, cozinha, câmaras, despensa e apoio) com DHT22 nas paredes e ao menos 1 sensor obrigatório na câmara frigorífica. A geometria está em [data/ru_geometria.json](data/ru_geometria.json) e as saídas vão para `results/ru/`. Opções: `--balcoes` e `--sem-obrigatorios`.

## Estrutura

```
main.py                    linha de comando: otimiza, salva o CSV e gera os gráficos
src/ru_environment.py      constrói I, J e N_i a partir de um JSON de geometria
src/cenarios.py            carrega os cenários (salao, ru, lab) com a mesma interface
src/mclp_solver.py         MCLP e LSCP em PuLP/CBC, varredura de p
src/visualizer.py          figuras em matplotlib (300 dpi)
src/lab_environment.py     cenário do laboratório (geometria no código)
data/salao_geometria.json  geometria, pesos, sensor e raios do salão
data/ru_geometria.json     geometria do RU completo
docs/                      regras de modelagem do salão e prompts do projeto
articles/                  artigos de referência
img/                       planta, cortes e elevações do RU (Graco Projetos)
results/salao/             saídas do cenário do salão
```

## Limitações

- **2D e estático:** o modelo considera um plano a 1,1 m (ISO 7726) e não representa a variação vertical de temperatura nem a variação ao longo do dia. Um sensor suspenso do teto fica, na prática, a 2–2,5 m de altura.
- **Cobertura simplificada:** a cobertura é binária (coberto ou não) e igual em todas as direções.
- **Premissas não medidas:** os gradientes, a tolerância e os pesos são premissas.
- **Geometria a confirmar:** portas, divisórias, mesas e balcões estão marcados `confirmar` no JSON e precisam ser conferidos numa visita ao RU.

## Referências

- CHURCH, R.; REVELLE, C. The maximal covering location problem. *Papers of the Regional Science Association*, v. 32, p. 101–118, 1974.
- *Sensor Optimization in Large Spaces Based on RBF Neural Networks and K-means Cluster Analysis*. IEEE Xplore, doc. 10473322.
- *Study on Classroom Temperature Distribution in Hybrid Cooling System at Different Air Conditioner Setpoints*. IEEE Xplore, doc. 11533711.
- *Gaussian processes for multi-sensor environmental monitoring*. IEEE Xplore, doc. 7295810.
- ISO 7726:1998. *Ergonomics of the thermal environment — Instruments for measuring physical quantities*.
- ANSI/ASHRAE Standard 55. *Thermal Environmental Conditions for Human Occupancy*.
