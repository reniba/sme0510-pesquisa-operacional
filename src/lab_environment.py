"""Geração da malha 2D, pesos a_i, candidatos J e matriz de cobertura N_i."""
from dataclasses import dataclass
import math

# --- Parâmetros físicos (ISO 7726 / DHT22) ---
STEP = 0.5
LX, LY = 10.0, 7.0
Z_LAB = 1.1    # m, cota de respiração (ocupante sentado)
Z_RACK = 1.5   # m, cota de exaustão da sala de racks
E_DHT22 = 0.5  # °C
DT_MAX = 1.0   # °C (ISO 7726 Classe C)
G_XY = 0.2     # °C/m
S_XY = (DT_MAX - E_DHT22) / G_XY  # 2.5 m

ACS = [(2.5, 0.0), (6.5, 0.0), (1.8, 7.0), (4.0, 7.0), (6.2, 7.0)]
AC_EXCL = 1.0
RACK_X = [1.2, 3.0, 4.8, 6.5]

SUB_RACKS, SUB_LAB = "Sala de Racks", "Laboratório"


def na_sala_racks(x, y):
    return x <= 7.5 and y >= 5.0


def subambiente(x, y):
    return SUB_RACKS if na_sala_racks(x, y) else SUB_LAB


def categoria(x, y):
    """Retorna (categoria, peso a_i)."""
    if na_sala_racks(x, y):
        if 5.5 <= y <= 6.5 and any(abs(x - rx) <= 0.5 for rx in RACK_X):
            return "rack", 20
        return "corredor_racks", 4
    if 1.0 <= x <= 7.5 and 2.0 <= y <= 3.5:
        return "ilha", 15
    if 0.5 <= x <= 7.5 and 0.25 <= y <= 1.0:
        return "bancada_sul", 12
    if 9.0 <= x <= 9.75 and 0.5 <= y <= 4.75:
        return "bancada_leste", 12
    return "corredor", 2


@dataclass
class Ambiente:
    I_coords: list
    a: list
    cat: list
    J_coords: list
    N: list          # N[i] = lista de índices j que cobrem i
    s_xy: float = S_XY


def _grade():
    nx, ny = round(LX / STEP), round(LY / STEP)
    return [(0.25 + STEP * ix, 0.25 + STEP * iy) for ix in range(nx) for iy in range(ny)]


def candidato_valido(x, y):
    xmin, xmax, ymin, ymax = 0.25, LX - 0.25, 0.25, LY - 0.25
    parede = x in (xmin, xmax) or y in (ymin, ymax)
    divis = (abs(y - 4.75) <= 0.25 or abs(y - 5.25) <= 0.25) and x <= 7.5
    ilha = 1.0 <= x <= 7.5 and y == 2.75
    quina = x in (xmin, xmax) and y in (ymin, ymax)
    perto_ac = any(math.hypot(x - ax, y - ay) < AC_EXCL for ax, ay in ACS)
    return (parede or divis or ilha) and not quina and not perto_ac


def construir_ambiente():
    I_coords = _grade()
    cc = [categoria(x, y) for x, y in I_coords]
    cat = [c for c, _ in cc]
    a = [w for _, w in cc]
    J_coords = [p for p in I_coords if candidato_valido(*p)]
    N = []
    for xi, yi in I_coords:
        amb = na_sala_racks(xi, yi)
        N.append([j for j, (xj, yj) in enumerate(J_coords)
                  if na_sala_racks(xj, yj) == amb
                  and math.hypot(xi - xj, yi - yj) <= S_XY + 1e-9])
    return Ambiente(I_coords, a, cat, J_coords, N)
