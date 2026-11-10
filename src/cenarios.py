"""Carrega os cenários (lab, ru) em ambientes com a mesma interface para o solver."""
from . import lab_environment as lab
import os

from .ru_environment import RAIZ, construir_ambiente_ru

GEOMETRIA_SALAO = os.path.join(RAIZ, "data", "salao_geometria.json")


def carregar_lab():
    env = lab.construir_ambiente()
    idx = range(len(env.I_coords))
    rack = [i for i in idx if lab.na_sala_racks(*env.I_coords[i])]
    env.grupos = {
        "racks": rack,
        "lab": [i for i in idx if i not in set(rack)],
        "bancadas": [i for i in idx if env.cat[i] in ("ilha", "bancada_sul", "bancada_leste")],
    }
    env.obrigatorios = []
    env.rotulo_j = [lab.subambiente(x, y) for x, y in env.J_coords]
    return env


def carregar_ru(incluir_balcoes=False):
    return construir_ambiente_ru(incluir_balcoes=incluir_balcoes)


def carregar_salao(mesas=False, passo=None, fator_raio=1.0):
    """Só o salão de refeições, com mesas e corredores detalhados. `mesas=True` permite
    fixar sensores nas bordas dos blocos de mesas voltadas para os corredores."""
    return construir_ambiente_ru(GEOMETRIA_SALAO, suportes={"mesa"} if mesas else (), passo=passo,
                                fator_raio=fator_raio)
