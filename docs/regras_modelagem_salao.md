# Regras de modelagem: salão de refeições do RU UFSCar

Este documento lista todas as regras e restrições do modelo de posicionamento de sensores de temperatura no salão de refeições do Restaurante Universitário (RU) da UFSCar, campus São Carlos. É a configuração cujos resultados estão em `results/salao/`.

Cada regra indica a sua origem:

- **[planta]**: medido na planta baixa (`img/2_planta14.webp`).
- **[norma]**: vem de norma técnica ou de datasheet.
- **[premissa]**: escolha do grupo, a justificar ou validar.
- **`confirmar`**: item marcado assim em `data/salao_geometria.json`, a conferir numa visita ao RU.

Todos os parâmetros ficam em [`data/salao_geometria.json`](../data/salao_geometria.json). O código que aplica as regras está em `src/ru_environment.py` (construção de `I`, `J` e `N_i`) e em `src/mclp_solver.py` (modelos).

---

## 1. Formulação matemática

### 1.1 Conjuntos e índices

| Símbolo | Descrição | Tamanho |
|---|---|---|
| `I` | pontos de demanda: centros das células de 1 m × 1 m dentro do salão | 626 |
| `J` | locais candidatos a receber um sensor | 526 |
| `N_i ⊆ J` | candidatos que cobrem o ponto `i ∈ I` (regras R12 a R14) | 30 em média |
| `I' ⊆ I` | pontos com `N_i ≠ ∅`, isto é, alcançáveis por algum candidato | 614 |

### 1.2 Parâmetros

| Símbolo | Descrição | Valor |
|---|---|---|
| `a_i` | peso de demanda do ponto `i` (regra R6) | 4 a 20 |
| `p` | número máximo de sensores | 1 a 23 na varredura; 10 no cenário de referência |
| `e` | erro do sensor (SHT31) | 0,2 °C |
| `ΔT_max` | tolerância admitida entre a leitura e o ponto representado | 1,0 °C |
| `g_i` | gradiente horizontal de temperatura na zona de `i` | 0,20 ou 0,35 °C/m |
| `S_i` | raio de cobertura no ponto `i`: `S_i = (ΔT_max − e) / g_i` | 4,0 m ou 2,29 m |

### 1.3 Variáveis de decisão

- `x_j ∈ {0, 1}`: vale 1 se um sensor é instalado no candidato `j ∈ J`.
- `y_i ∈ {0, 1}`: vale 1 se o ponto `i ∈ I'` está coberto.

### 1.4 Modelo principal: MCLP (Church & ReVelle, 1974)

```
max  Z = Σ_{i ∈ I'} a_i · y_i                                   (cobertura ponderada)

s.a. (1)  Σ_{j ∈ N_i} x_j ≥ y_i        ∀ i ∈ I'                 o ponto i só conta como coberto
                                                                se houver sensor em N_i
     (2)  Σ_{j ∈ J} x_j ≤ p                                     limite de sensores
     (3)  x_j ∈ {0, 1}                 ∀ j ∈ J
     (4)  y_i ∈ {0, 1}                 ∀ i ∈ I'
```

A cobertura é reportada em porcentagem do peso **total**: `100 · Z / Σ_{i ∈ I} a_i`. O denominador inclui os pontos sem candidato ao alcance, que nunca podem ser cobertos. Por isso o máximo possível é 98,4%.

### 1.5 Modelo auxiliar: LSCP (cobertura de conjuntos)

O LSCP dá o menor número de sensores que cobre todos os pontos alcançáveis:

```
min  Σ_{j ∈ J} x_j

s.a. (5)  Σ_{j ∈ N_i} x_j ≥ 1          ∀ i ∈ I'                 todo ponto alcançável é coberto
     (6)  x_j ∈ {0, 1}                 ∀ j ∈ J
```

Resultado: **23 sensores**. A varredura do MCLP vai até esse valor.

---

## 2. Regras de construção da instância

### 2.1 Domínio e malha

- **R1. Escopo.** Só o salão de refeições (cômodo 1 da planta), onde os alunos comem. Cozinha, câmaras, despensa e áreas de apoio ficam fora. **[premissa]**
- **R2. Contorno.** O salão é o retângulo 0–29,3 × 0–21,8 m mais o hall à frente da cozinha, em 9,5–19,8 × 21,8–25,7 m. Os dois pátios laterais (x ≤ 7,5 e x ≥ 21,9, com 7,1 ≤ y ≤ 11,2) não fazem parte dele.
  - A origem fica no canto inferior esquerdo do prédio na folha; X cresce para a direita e Y para cima.
  - A escala é de 8,2 px/m, com precisão de ±0,5 m.

  **[planta]**
- **R3. Malha.** O passo é de 1,0 m, com centros em 0,5 + k (k inteiro). Um ponto pertence a uma região quando `x0 ≤ x < x1` e `y0 ≤ y < y1`.
  - Com esse passo, as paredes podem se deslocar até 0,5 m: o prédio termina em x = 29 m e os pátios começam em x ≈ 7 e x ≈ 22 m.

  **[premissa]**
- **R4. Plano de avaliação único** em z = 1,1 m, a altura da cabeça de quem está sentado e do abdômen de quem está em pé na ISO 7726. O modelo é 2D e não representa a variação vertical de temperatura. **[norma]**

### 2.2 Zonas de demanda e pesos

- **R5. Zonas.** O salão é dividido em zonas funcionais. Quando duas zonas se sobrepõem, vale a mais específica, nesta ordem crescente de prioridade: corredor principal → corredores entre mesas → mesas → fila e serviço → balcões. **[premissa]**
- **R6. Pesos.** O peso `a_i` representa a exposição dos ocupantes, isto é, a densidade de pessoas multiplicada pelo tempo de permanência, numa escala de 4 a 20. **[premissa]**

| Zona | `a_i` | Pontos | Retângulos (m, `x0–x1 × y0–y1`) | Justificativa |
|---|---|---|---|---|
| Mesas | 20 | 300 | 0,3–29,0 × 0,3–3,0; 0,3–6,6 × 4,2–7,1; 22,6–29,0 × 4,2–7,1; colunas centrais 7,5–9,0, 9,8–12,3, 13,4–16,3 e 17,0–20,0, todas com y de 4,2 a 11,2; alas 0,3–6,6 e 22,7–29,0, ambas com y de 11,3 a 18,9 | alunos sentados por cerca de 20 min, com alta densidade |
| Fila e serviço | 16 | 50 | 10,0–19,3 × 12,3–17,8; 11,8–16,8 × 19,5–23,5 | fila densa em pé, por alguns minutos |
| Corredor principal | 10 | 177 | 0–29,3 × 19,0–21,8 (entradas); 7,5–21,9 × 11,2–19,0 (eixo central); 9,5–19,8 × 21,8–25,7 (hall) | fluxo alto, permanência curta |
| Corredores entre mesas | 6 | 75 | 0,3–29,0 × 3,0–4,2 (transversal sul); 6,6–7,5, 9,0–9,8, 12,3–13,4, 16,3–17,0 e 20,0–22,6, todos com y de 4,2 a 11,2; 6,6–7,5 e 21,9–22,7, ambos com y de 11,2 a 19,0 | fluxo moderado |
| Balcões (equipamento) | 4 | 24 | 11,0–11,8, 14,0–15,0 e 17,1–18,2, todos com y de 12,9 a 17,4; U em 12,3–16,3 × 20,0–23,0 | área sem ocupantes; fonte de calor |
| Circulação geral | 4 | 0 | restante do salão | com a malha de 1 m, esta zona ficou sem pontos |

- **R7. Áreas contínuas.** Os blocos de mesas e os balcões são tratados como áreas contínuas, sem modelar mesas, cadeiras ou cubas individuais. **[planta, `confirmar`]**

### 2.3 Sensor e raio de cobertura

- **R8. Sensor.** Sensirion SHT31, com erro típico `e = ±0,2 °C` (o DHT22 tem ±0,5 °C). **[datasheet, conferir]**
- **R9. Raio de cobertura.** É a distância horizontal a partir da qual a diferença de temperatura esperada consome o que sobra da tolerância depois do erro do sensor:

  ```
  S = (ΔT_max − e) / g
  ```

  | Zona do ponto `i` | `g` (°C/m) | `S` (m) | Origem |
  |---|---|---|---|
  | mesas e corredores | 0,20 | **4,00** | [premissa] gradiente típico de ambiente climatizado |
  | fila, serviço e balcões | 0,35 | **2,29** | [premissa] gradiente maior perto de fonte de calor |

  O valor `ΔT_max = 1,0 °C` também é **[premissa]**, inspirada nas exigências de exatidão da ISO 7726.
- **R10. Raio do ponto.** Cada ponto usa o raio da **própria** zona, não o da zona do sensor.
- **R11. Cobertura binária e isotrópica.** Um ponto está coberto ou não, sem cobertura parcial, e o raio é o mesmo em todas as direções. **[premissa]**

### 2.4 Matriz de cobertura `N_i`

O candidato `j` pertence a `N_i` quando as três regras abaixo valem ao mesmo tempo.

- **R12. Mesmo ambiente.** `j` e `i` estão no salão. Isso vale para todo o domínio, já que ele tem um só cômodo.
- **R13. Distância.** `dist(i, j) ≤ S_i`, com distância euclidiana.
- **R14. Linha de visada.** A reta entre `i` e `j` não atravessa nenhuma parede do salão nem divisória interna. Na prática:
  - um sensor não cobre pontos do outro lado de um pátio;
  - um sensor no corredor de entrada não cobre as alas de mesas.

  **[premissa]**
- **R15. Divisórias internas.** Ficam em y = 19,0 m e separam as alas de mesas do corredor de entrada. **[planta, `confirmar`]**

  | Divisória | Segmento |
  |---|---|
  | ala oeste | (0,0; 19,0) até (7,3; 19,0) |
  | ponta da ala oeste | (7,3; 18,4) até (7,3; 19,0) |
  | ala leste | (22,0; 19,0) até (29,3; 19,0) |
  | ponta da ala leste | (22,0; 18,3) até (22,0; 19,0) |

- **R16. Obstáculos que não bloqueiam.** Mesas e balcões não bloqueiam a cobertura, porque ficam abaixo de 1,1 m e não fecham a passagem do ar. **[premissa]**

### 2.5 Locais candidatos `J`

- **R17. Malha de suspensão.** Qualquer ponto da malha de 1 m pode receber um sensor, pendurado no teto. Isso dá 524 candidatos. Os dois pilares centrais, em (14,7; 7,5) e (14,7; 11,0), continuam como candidatos, mas viraram redundantes. **[premissa]**
- **R18. Exclusão por porta.** Nenhum candidato a menos de **1,5 m** de uma porta externa, onde a entrada de ar de fora distorce a leitura. **[planta, `confirmar`]**

  | Porta | Posição (m) |
  |---|---|
  | entrada oeste | (0; 20,4) |
  | entrada leste | (29,3; 20,4) |
  | porta da ala oeste | (0; 17,0) |
  | porta da ala leste | (29,3; 16,9) |
  | saída sul-oeste | (7,3; 0) |
  | saída sul-leste | (22,2; 0) |

- **R19. Exclusão por fonte de calor.** Nenhum candidato a menos de **1,0 m** de cada um dos 4 balcões térmicos (retângulos da regra R6). Isso segue o afastamento de fontes concentradas de calor da ASHRAE 55 e evita o viés térmico do sensor. **[norma + premissa]**
- **R20. Nenhum sensor obrigatório.** Não há local onde um sensor seja exigido; o modelo não tem restrições do tipo `Σ x_j ≥ 1`.

### 2.6 Execução

- **R21. Varredura.** De p = 1 a 20, mais os valores 21 a 23, até o resultado do LSCP. Cada `p` é um modelo independente.
- **R22. Solver.** PuLP 3.x com CBC, limite de 120 s por modelo. Todos os 23 modelos foram resolvidos com ótimo provado, somando cerca de 42 s.

---

## 3. Resultados

| p | Total | Mesas | Corredores entre mesas | Corredor principal | Fila/serviço | Balcões |
|---|---|---|---|---|---|---|
| 1 | 10,2% | 15,3% | 0% | 0,6% | 0% | 0% |
| 5 | 46,2% | 66,3% | 45,3% | 1,7% | 0% | 0% |
| 8 | 66,4% | 90,3% | 77,3% | 13,6% | 6,0% | 0% |
| **10** | **75,1%** | **90,3%** | **77,3%** | **49,2%** | **24,0%** | **16,7%** |
| 16 | 90,5% | 94,0% | 90,7% | 97,2% | 54,0% | 54,2% |
| 20 | 97,2% | 100% | 100% | 98,3% | 76,0% | 62,5% |
| 23 | 98,4% | 100% | 100% | 100% | 84,0% | 83,3% |

Sensores escolhidos para p = 10, com coordenadas em metros:

| Sensor | Posição | Sensor | Posição |
|---|---|---|---|
| S1 | (3,5; 3,5) | S6 | (16,5; 8,5) |
| S2 | (3,5; 15,5) | S7 | (17,5; 2,5) |
| S3 | (9,5; 11,5) | S8 | (17,5; 21,5) |
| S4 | (10,5; 3,5) | S9 | (25,5; 3,5) |
| S5 | (10,5; 18,5) | S10 | (25,5; 15,5) |

- Com p = 8, as mesas já estão 90% cobertas. Com p = 16, a cobertura total passa de 90%.
- A cobertura de uma zona pode cair quando `p` aumenta. O modelo maximiza só o total e, a cada `p`, reposiciona todos os sensores.

---

## 4. Limitações e itens a confirmar

1. **Altura do sensor suspenso.** O modelo supõe que o sensor mede o ar a 1,1 m. Na prática, um sensor pendurado acima das cabeças fica a 2–2,5 m de altura, e o raio teria de ser corrigido pelo gradiente vertical: `S = (ΔT_max − e − g_z·Δz) / g`.
2. **Premissas sem fonte verificada:** os gradientes 0,20 e 0,35 °C/m, a tolerância de 1,0 °C e os pesos de exposição.
3. **Geometria a conferir:** posições de portas e divisórias, layout das mesas e dos balcões, e a viabilidade de prender sensores no teto. Tudo isso está marcado `confirmar`.
4. **Modelo estático.** Não diferencia horário de pico de horário vazio, nem a insolação de cada fachada, porque o norte da planta não está confirmado.
5. **Fila e balcões pouco cobertos.** São a zona menos coberta (24% com p = 10), por causa do raio menor (2,29 m) e da exclusão de 1,0 m em volta dos balcões. Doze pontos perto dos balcões não têm nenhum candidato ao alcance.
6. **Zona vazia.** A zona "circulação geral" ficou sem pontos com a malha de 1 m e pode ser retirada do modelo.
