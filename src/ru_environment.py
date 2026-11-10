"""Ambiente do Restaurante Universitário (UFSCar): lê data/ru_geometria.json e
gera um `Ambiente` (mesmo formato do laboratório) com dados extras por célula.

Toda a geometria vive no JSON. Aqui só há regras gerais:
  - I  = células cujo centro cai dentro de algum cômodo (menos recortes);
  - J  = células junto à parede do próprio cômodo (sem quinas) + pilares,
         menos zonas de exclusão (portas externas, equipamentos de vapor);
  - N_i = candidatos do mesmo cômodo a distância <= S da zona de i.
"""
import json
import math
import os
from dataclasses import dataclass, field

import numpy as np

from .lab_environment import Ambiente

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEOMETRIA = os.path.join(RAIZ, "data", "ru_geometria.json")
IMAGEM_PLANTA = os.path.join(RAIZ, "img", "2_planta14.webp")


@dataclass
class AmbienteRU(Ambiente):
    sala_i: list = field(default_factory=list)       # id do cômodo de cada i
    sub_i: list = field(default_factory=list)        # id da sub-região (ou do cômodo)
    raio_i: list = field(default_factory=list)       # S (m) da zona de cada i
    sala_j: list = field(default_factory=list)
    raio_j: list = field(default_factory=list)       # raio desenhado para o sensor j
    rotulo_j: list = field(default_factory=list)
    grupos: dict = field(default_factory=dict)       # grupo -> índices i
    obrigatorios: list = field(default_factory=list)  # (id, nome, [j...])
    salas: dict = field(default_factory=dict)        # id -> dict do JSON
    paredes: list = field(default_factory=list)      # segmentos (x1, y1, x2, y2)
    portas: list = field(default_factory=list)
    equipamentos: list = field(default_factory=list)
    pilares: list = field(default_factory=list)
    raio_porta: float = 1.5
    step: float = 0.5
    largura: float = 0.0
    comprimento: float = 0.0
    z_ref: float = 1.1
    nao_cobriveis: list = field(default_factory=list)  # i com N_i vazio
    tipo_j: list = field(default_factory=list)       # tipo de suporte de cada candidato
    divisorias: list = field(default_factory=list)   # paredes internas (x1, y1, x2, y2)
    linha_de_visada: bool = False                    # cobertura bloqueada por paredes
    nome: str = "RU UFSCar"
    obstaculos: object = None                        # array M x 4 (paredes + divisórias)
    sensor: str = "DHT22"


def raio_cobertura(dT_max, g_xy, e_dht22):
    """S_xy = (dT_max - e_dht22) / g_xy."""
    return (dT_max - e_dht22) / g_xy


def _em_retangulos(rects, x, y):
    return any(x0 <= x < x1 and y0 <= y < y1 for x0, y0, x1, y1 in rects)


def _dist_retangulo(x, y, r):
    x0, y0, x1, y1 = r
    dx = max(x0 - x, 0.0, x - x1)
    dy = max(y0 - y, 0.0, y - y1)
    return math.hypot(dx, dy)


def _cruza(p1, p2, segs):
    """Para cada segmento em `segs` (array M x 4), True se o segmento p1-p2 o cruza
    propriamente (toques em extremidades não contam)."""
    if len(segs) == 0:
        return np.zeros(0, dtype=bool)
    q1, q2 = segs[:, :2], segs[:, 2:]

    def orient(a, b, c):
        return (b[..., 0] - a[..., 0]) * (c[..., 1] - a[..., 1]) - (b[..., 1] - a[..., 1]) * (c[..., 0] - a[..., 0])
    P1, P2 = np.broadcast_to(p1, q1.shape), np.broadcast_to(p2, q1.shape)
    o1, o2 = orient(P1, P2, q1), orient(P1, P2, q2)
    o3, o4 = orient(q1, q2, P1), orient(q1, q2, P2)
    return (o1 * o2 < -1e-12) & (o3 * o4 < -1e-12)


def _bloqueados(p, Q, segs):
    """Versão vetorizada de `_cruza`: para um ponto p e vários pontos Q (k x 2), True
    onde o segmento p-Q[k] cruza propriamente algum segmento de `segs` (M x 4)."""
    if len(segs) == 0 or len(Q) == 0:
        return np.zeros(len(Q), dtype=bool)
    q1, q2 = segs[None, :, :2], segs[None, :, 2:]            # 1 x M x 2
    a, b = np.asarray(p, float)[None, None, :], np.asarray(Q, float)[:, None, :]  # k x 1 x 2

    def orient(u, v, w):
        return (v[..., 0] - u[..., 0]) * (w[..., 1] - u[..., 1]) - (v[..., 1] - u[..., 1]) * (w[..., 0] - u[..., 0])
    o1, o2 = orient(a, b, q1), orient(a, b, q2)
    o3, o4 = orient(q1, q2, a), orient(q1, q2, b)
    return ((o1 * o2 < -1e-12) & (o3 * o4 < -1e-12)).any(1)


def cobertos_por_coordenadas(env, coords):
    """Pontos de `env` cobertos por sensores em coordenadas arbitrárias (x, y), com as
    mesmas regras da matriz N: mesmo cômodo, distância <= raio da zona do ponto e,
    se ativa, linha de visada. Serve para avaliar a solução de uma malha em outra."""
    Ic = np.asarray(env.I_coords, float)
    si = np.asarray(env.sala_i, dtype=object)
    ri = np.asarray(env.raio_i, float)
    obst = env.obstaculos if env.obstaculos is not None else np.zeros((0, 4))
    cob = np.zeros(len(Ic), dtype=bool)
    for x, y in coords:
        sala = si[np.argmin(np.hypot(Ic[:, 0] - x, Ic[:, 1] - y))]   # cômodo do sensor
        cand = np.nonzero((si == sala) & (np.hypot(Ic[:, 0] - x, Ic[:, 1] - y) <= ri + 1e-9) & ~cob)[0]
        if env.linha_de_visada:
            cand = cand[~_bloqueados((x, y), Ic[cand], obst)]
        cob[cand] = True
    return set(np.nonzero(cob)[0].tolist())


def _dist_segmento(x, y, s):
    x1, y1, x2, y2 = s
    dx, dy = x2 - x1, y2 - y1
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))


def construir_ambiente_ru(caminho=GEOMETRIA, incluir_balcoes=False, suportes=(), passo=None, fator_raio=1.0):
    """`suportes`: tipos extras de suporte a ativar (ex.: {"mesa", "balcao"}); cada
    sub-região do JSON pode declarar `"suporte": "<tipo>"` (`true` equivale a "balcao")."""
    with open(caminho, encoding="utf-8") as f:
        g = json.load(f)
    if passo:  # sobrescreve o passo da malha do JSON (ex.: 0.5 para comparar com 1.0)
        g["malha"]["step"] = passo
    tipos_ativos = set(suportes) | ({"balcao"} if incluir_balcoes else set())

    step = g["malha"]["step"]
    W, L = g["malha"]["largura"], g["malha"]["comprimento"]
    nx, ny = math.ceil(W / step - 1e-9), math.ceil(L / step - 1e-9)
    # erro do sensor: bloco "sensor" (modelo e erro), ou o DHT22 do cenário RU
    sensor = g.get("sensor", {"modelo": "DHT22", "erro": g.get("e_dht22", 0.5)})
    e = sensor["erro"]
    malha_candidatos = g.get("candidatos", {}).get("modo") == "malha"
    # fator_raio multiplica todos os raios (0.5 = metade; equivale a dobrar o gradiente g_xy)
    S = {k: fator_raio * raio_cobertura(v["dT_max"], v["g_xy"], e) for k, v in g["tipos_raio"].items()}
    salas = {s["id"]: s for s in g["salas"]}

    # --- classificação de cada célula da malha (centros 0,25 + 0,5k) ---
    sala_g = np.full((nx, ny), "", dtype=object)
    sub_g = np.full((nx, ny), "", dtype=object)
    peso_g = np.zeros((nx, ny))
    raio_g = np.zeros((nx, ny))
    grupo_g = np.full((nx, ny), "", dtype=object)
    for ix in range(nx):
        for iy in range(ny):
            x, y = step * (ix + 0.5), step * (iy + 0.5)
            donos = [s for s in g["salas"]
                     if _em_retangulos(s["retangulos"], x, y)
                     and not _em_retangulos(s.get("recortes", []), x, y)]
            if len(donos) > 1:
                raise ValueError(f"Cômodos sobrepostos em ({x}, {y}): {[d['id'] for d in donos]}")
            if not donos:
                continue
            s = donos[0]
            reg = s
            for sub in s.get("subregioes", []):
                if _em_retangulos(sub["retangulos"], x, y):
                    reg = sub
            sala_g[ix, iy], sub_g[ix, iy] = s["id"], reg["id"]
            peso_g[ix, iy], grupo_g[ix, iy] = reg["peso"], reg["grupo"]
            raio_g[ix, iy] = S[reg["raio"]]

    # --- demanda I (mesma ordem de varredura do laboratório: x externo, y interno) ---
    I_coords, idx = [], {}
    a, cat, sala_i, sub_i, raio_i, grupo_i = [], [], [], [], [], []
    for ix in range(nx):
        for iy in range(ny):
            if not sala_g[ix, iy]:
                continue
            idx[ix, iy] = len(I_coords)
            I_coords.append((step * (ix + 0.5), step * (iy + 0.5)))
            a.append(float(peso_g[ix, iy]))
            cat.append(sub_g[ix, iy])
            sala_i.append(sala_g[ix, iy])
            sub_i.append(sub_g[ix, iy])
            raio_i.append(float(raio_g[ix, iy]))
            grupo_i.append(grupo_g[ix, iy])

    def vizinho(ix, iy, dx, dy):
        jx, jy = ix + dx, iy + dy
        if 0 <= jx < nx and 0 <= jy < ny:
            return sala_g[jx, jy], sub_g[jx, jy]
        return "", ""

    # --- paredes: arestas entre células de cômodos diferentes (ou com o exterior) ---
    paredes = []
    for (ix, iy) in idx:
        x0, y0 = ix * step, iy * step
        for dx, dy, seg in ((1, 0, (x0 + step, y0, x0 + step, y0 + step)),
                            (-1, 0, (x0, y0, x0, y0 + step)),
                            (0, 1, (x0, y0 + step, x0 + step, y0 + step)),
                            (0, -1, (x0, y0, x0 + step, y0))):
            if vizinho(ix, iy, dx, dy)[0] != sala_g[ix, iy]:
                paredes.append(seg)

    # --- candidatos J ---
    portas = g["portas_externas"]["pontos"]
    raio_porta = g["portas_externas"]["raio_exclusao"]
    equip = g.get("equipamentos_vapor", []) + g.get("fontes_calor", [])
    divisorias = [tuple(d["seg"]) for d in g.get("divisorias", [])]
    pilar_cel = set()
    for p in g["pilares"]:
        pilar_cel.add((min(int(p["x"] / step), nx - 1), min(int(p["y"] / step), ny - 1)))

    J_coords, J_cel, tipo_j = [], [], []
    for (ix, iy), i in idx.items():
        x, y = I_coords[i]
        diff_h = [vizinho(ix, iy, d, 0)[0] != sala_g[ix, iy] for d in (-1, 1)]
        diff_v = [vizinho(ix, iy, 0, d)[0] != sala_g[ix, iy] for d in (-1, 1)]
        # divisórias internas contam como parede (horizontal -> parede em y; vertical -> em x)
        div_perto = [d for d in divisorias if _dist_segmento(x, y, d) <= step / 2 + 1e-9]
        div_y = any(d[1] == d[3] for d in div_perto)
        div_x = any(d[0] == d[2] for d in div_perto)
        tem_x, tem_y = any(diff_h) or div_x, any(diff_v) or div_y
        tipo = None
        if (tem_x or tem_y) and not (tem_x and tem_y):  # junto à parede, sem quinas
            tipo = "divisória" if div_perto and not (any(diff_h) or any(diff_v)) else "parede"
        if malha_candidatos:  # sensor suspenso: qualquer ponto da malha serve de suporte
            tipo = "malha"
        if (ix, iy) in pilar_cel:
            tipo = "pilar"
        if tipo is None and tipos_ativos and salas[sala_g[ix, iy]].get("subregioes"):
            reg = next((sr for sr in salas[sala_g[ix, iy]]["subregioes"] if sr["id"] == sub_g[ix, iy]), None)
            sup = reg.get("suporte") if reg else None
            sup = "balcao" if sup is True else sup
            if sup in tipos_ativos and any(
                    vizinho(ix, iy, dx, dy)[0] == sala_g[ix, iy] and vizinho(ix, iy, dx, dy)[1] != sub_g[ix, iy]
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                tipo = {"mesa": "borda de mesa", "balcao": "balcão"}.get(sup, sup)
        if tipo is None:
            continue
        if any(math.hypot(x - p["x"], y - p["y"]) < raio_porta for p in portas):
            continue
        if any(_dist_retangulo(x, y, q["retangulo"]) < q["margem"] for q in equip):
            continue
        J_coords.append((x, y))
        J_cel.append((ix, iy))
        tipo_j.append(tipo)

    # --- matriz de cobertura N_i (barreira = mesmo cômodo) ---
    sala_j = [sala_g[c] for c in J_cel]
    raio_j = [float(raio_g[c]) for c in J_cel]
    Ic, Jc = np.array(I_coords), np.array(J_coords)
    si, sj = np.array(sala_i, dtype=object), np.array(sala_j, dtype=object)
    ri = np.array(raio_i)
    visada = bool(g.get("linha_de_visada", False))
    obst = np.array(paredes + divisorias, dtype=float).reshape(-1, 4)
    N = []
    for i in range(len(I_coords)):
        d = np.hypot(Jc[:, 0] - Ic[i, 0], Jc[:, 1] - Ic[i, 1])
        js = np.nonzero((sj == si[i]) & (d <= ri[i] + 1e-9))[0]
        if visada:  # a reta sensor-ponto não pode atravessar parede nem divisória
            js = js[~_bloqueados(Ic[i], Jc[js], obst)]
        N.append([int(j) for j in js])

    grupos = {nome: [i for i, gi in enumerate(grupo_i) if gi == nome] for nome in g["grupos"]}
    obrig = [(s["id"], s["nome"], [j for j, sj_ in enumerate(sala_j) if sj_ == s["id"]])
             for s in g["salas"] if s.get("exige_sensor")]
    rotulo_j = [f"{salas[s]['nome']} (cômodo {s}), {t}" for s, t in zip(sala_j, tipo_j)]

    return AmbienteRU(
        I_coords=I_coords, a=a, cat=cat, J_coords=J_coords, N=N, s_xy=max(S.values()),
        sala_i=sala_i, sub_i=sub_i, raio_i=raio_i, sala_j=sala_j, raio_j=raio_j,
        rotulo_j=rotulo_j, grupos=grupos, obrigatorios=obrig, salas=salas,
        paredes=paredes, portas=portas, equipamentos=equip, pilares=g["pilares"],
        raio_porta=raio_porta, step=step, largura=W, comprimento=L, z_ref=g["malha"]["z_ref"],
        nao_cobriveis=[i for i, n in enumerate(N) if not n],
        tipo_j=tipo_j, divisorias=divisorias, linha_de_visada=visada, obstaculos=obst,
        nome=g.get("meta", {}).get("nome", "RU UFSCar"), sensor=sensor["modelo"],
    )
