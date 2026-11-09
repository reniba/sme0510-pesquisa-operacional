Implemente a segunda versão do projeto de PO (SME0510): posicionamento ótimo de sensores
DHT22 (ESP32) no Restaurante Universitário (RU) da UFSCar São Carlos, via MCLP
(Church & ReVelle, 1974) em PLI binária com PuLP 3.x + CBC.
O cenário do laboratório (USP) deve continuar funcionando sem alterações de resultado.

### 0. Fonte e convenções
- Planta: img/2_planta14.webp (escala gráfica: 8,2 px/m; precisão ≈ ±0,5 m).
  Cortes em img/3_cortesabc.webp e img/4_cortescdf.webp; ficha em img/ficha_tecnica.md.
- Origem (0,0) no canto inferior esquerdo do edifício na folha; X para a direita,
  Y para cima (do salão em direção ao recebimento). Não usar pontos cardeais.
- Toda a geometria fica em dados (data/ru_geometria.json), não espalhada em ifs.
  Cada cômodo é um polígono (retângulos ou L) com id, nome, zona, peso, raio e
  altura de referência. Itens incertos levam o campo "confirmar": true.

### 1. Domínio e malha
- Envoltória: 29,3 m (X) × 43,3 m (Y); malha com step = 0,5 m, centros em
  0,25 + 0,5k, com coordenadas geradas a partir de índices inteiros.
- I = células cujo centro cai dentro de algum cômodo. Ficam fora:
  - os recortes (pátios) laterais do salão: x ≤ 7,5 e x ≥ 21,9 com 7,1 ≤ y ≤ 11,2;
  - a área externa (varandas além de x < 0 e x > 29,3, plataforma acima do recebimento).
- Plano único z = 1,1 m (ISO 7726: cabeça sentado / abdômen em pé). As cotas
  0,6 e 1,7 m entram só como documentação, sem efeito no modelo.

### 2. Cômodos (medidas preliminares da planta, em metros)
| Id | Cômodo | x | y | Peso a_i | Raio |
|----|--------|---|---|----------|------|
| 1 | Salão de refeições | 0–29,3 | 0–21,8, mais o hall central em 9,5–19,8 × 21,8–25,7 | 15 | salão |
| 1b | Balcões térmicos (3 linhas) | 10,5–18,5 | 12,0–17,0 | 20 | cozinha |
| 1c | Balcão self-service em U | 12,0–16,5 | 20,0–23,0 | 20 | cozinha |
| 2 | Higienização | 2,1–9,5 | 21,8–25,7 | 8 | salão |
| 3 | Devolução e lavagem de bandejas (em L) | 19,8–27,3 × 21,8–25,7, mais 22,0–27,3 × 25,7–30,0 | — | 8 | salão |
| 4 | Cozinha/cocção | 7,5–22,0 | 25,7–34,8 | 20 | cozinha |
| 5 | Escritório da nutricionista | 2,1–7,5 | 25,7–30,0 | 6 | salão |
| 6 | Preparo de carnes | 4,5–7,5 | 30,0–34,8 | 25 | salão |
| 7 | Câmaras | 0–4,5 | 30,0–43,3 | 25 | câmara |
| 8 | Despensa | 4,5–11,3 | 36,8–43,3 | 12 | salão |
| 9 | Depósito de caixas | 11,3–14,7 | 39,5–43,3 | 6 | salão |
| 10 | Pré-seleção | 11,3–14,7 | 37,2–39,5 | 10 | salão |
| 11 | Recebimento | 14,7–18,8 | 36,8–43,3 | 8 | salão |
| 12 | Escritório | 18,8–22,0 | 39,5–43,3 | 6 | salão |
| 13 | Depósito de material de limpeza | 22,0–24,6 | 30,0–34,8 | 4 | salão |
| 14 | Lavagem de carros e caixas | 24,6–29,3 | 30,0–34,8 | 6 | salão |
| 15 | Vestiários (2) | 22,0–25,5 e 25,5–29,3 | 36,8–43,3 | 4 | salão |
| C | Circulações | corredor 4,5–22,0 × 34,8–36,8; faixas 0–2,1 e 27,3–29,3 em 21,8–30,0 | — | 4 | salão |

Notas sobre a tabela:
- Os pesos de 2, 3, 5 e 9–15 são proposta do grupo, a justificar no relatório.
- 1b e 1c são sub-regiões do salão: fazem parte do mesmo cômodo para a regra de
  barreira e só mudam o peso e o raio.
- Se a câmara 7 tiver subdivisões visíveis, modelar cada câmara como um cômodo próprio.

### 3. Raio de cobertura por zona: S = (ΔT_max − e) / g, com e = 0,5 °C
O código guarda ΔT_max e g de cada tipo de raio e calcula S a partir deles:
- salão (áreas abertas e de apoio): ΔT_max = 1,0 e g = 0,20 → S = 2,50 m
- cozinha (cocção e balcões térmicos): ΔT_max = 1,0 e g = 0,35 → S = 1,43 m
- câmara: ΔT_max = 0,7 e g = 0,133 → S = 1,50 m

### 4. Matriz de cobertura
j cobre i se e somente se:
- cômodo(j) == cômodo(i), generalizando a barreira da divisória do laboratório; e
- dist(i, j) ≤ S(zona de i).

### 5. Candidatos J
Entram como candidatos:
- células de cada cômodo a ≤ 0,5 m da parede do próprio cômodo, sem contar vãos de porta;
- células dos pilares do salão: elementos no eixo x ≈ 14,7, em y ≈ 7,5 e y ≈ 11,0
  (confirmar). Se o grupo adotar uma grade de pilares, declarar o espaçamento como premissa.
- opcional (cenário extra): faces dos balcões térmicos, que já têm energia.

Ficam de fora:
- quinas de cada cômodo;
- pontos a < 1,5 m das portas externas, todas com "confirmar": true:
  - fachada inferior em (6,8; 0), (15,0; 0) e (22,7; 0);
  - laterais do salão em (0; 13,0) e (29,3; 13,0);
  - acessos laterais em (0; ≈26) e (29,3; ≈26);
  - doca do recebimento em (16,8; 43,3);
- pontos a < 1,0 m de equipamentos de cocção ou vapor da cozinha, como retângulos em
  dados (provisoriamente, a bancada junto à parede direita da cozinha em
  20,2–21,3 × 28,0–33,0, a confirmar).

### 6. Modelo e experimentos (src/mclp_solver.py)
- MCLP: max Σ a_i·y_i  s.a.  Σ_{j∈N_i} x_j ≥ y_i;  Σ x_j ≤ p;  x, y binárias.
- LSCP: min Σ x_j  s.a.  Σ_{j∈N_i} x_j ≥ 1 (só para i com N_i não vazio). Isso dá
  o p mínimo para 100% de cobertura. Reportar as células sem nenhum candidato.
- Variante com restrição Σ_{j ∈ J_câmara} x_j ≥ 1 para cada câmara (boas práticas
  sanitárias; conferir a RDC 216/ANVISA), comparada ao MCLP puro.
- Varredura: p = 1..15, mais pontos espaçados até o p do LSCP.
- CBC com msg=False, timeLimit configurável e registro do gap e do status.
- Métricas por p: tempo, cobertura ponderada total, cobertura por zona e número de
  variáveis e restrições do modelo.

### 7. Arquivos
- data/ru_geometria.json: cômodos, sub-regiões, portas, equipamentos e pilares.
- src/ru_environment.py: lê o JSON e gera o mesmo tipo `Ambiente` usado pelo
  laboratório (I, a, cat, J, N), acrescentando o cômodo e o raio de cada célula.
  src/lab_environment.py fica intocado.
- src/mclp_solver.py: reaproveitar resolver_mclp e varrer_pareto, adicionando o
  LSCP, a restrição por câmara e métricas por zona genéricas, sem os nomes do
  laboratório fixos no código.
- src/visualizer.py: plotagem genérica com:
  - polígonos dos cômodos coloridos por peso e paredes desenhadas;
  - portas e equipamentos com os raios de exclusão;
  - candidatos J e sensores com círculos de raio próprio.
  Opcional: img/2_planta14.webp ao fundo, semitransparente, alinhada pela escala,
  para validar a digitalização.
- main.py: `--cenario {lab,ru}` (padrão lab, para não quebrar o que existe),
  `--p` (padrão 10 no RU) e `--p-max`. As saídas do RU vão para
  results/ru/metricas_ru_pareto.csv, results/ru/planta_ru_cobertura.png e
  results/ru/curva_pareto_ru.png, e o terminal mostra (x, y), cômodo e zona de cada sensor.

### 8. Validação
- Rodar `.venv/bin/python main.py --cenario ru` e `--cenario lab`. O lab deve
  reproduzir os resultados atuais (p = 6 → 96,85%).
- Gerar a figura de sobreposição com a planta e conferir visualmente a geometria.
- Atualizar README.md e CLAUDE.md com o novo cenário.
