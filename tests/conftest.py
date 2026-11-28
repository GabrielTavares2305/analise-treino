"""Fixtures compartilhadas: séries de ângulos simuladas, sem câmera.

Fixture = função que prepara um dado de teste. O pytest a injeta em qualquer
teste que tenha um parâmetro com o mesmo nome.
"""
import numpy as np
import pytest

from pose import NOMES_ANGULOS

FPS = 15


def serie_flexao(reps: int = 5, duracao_rep_s: float = 2.0, fps: int = FPS,
                 aberto: float = 170.0, fechado: float = 50.0, repouso_s: float = 0.5) -> np.ndarray:
    """Cotovelo numa flexão: começa esticado, dobra e volta (um cosseno por repetição)."""
    n_rep = int(duracao_rep_s * fps)
    t = np.arange(n_rep * reps)
    meio, amp = (aberto + fechado) / 2, (aberto - fechado) / 2
    movimento = meio + amp * np.cos(2 * np.pi * t / n_rep)
    parado = np.full(int(repouso_s * fps), aberto)
    return np.concatenate([parado, movimento, parado])


def series_corpo(principal: np.ndarray) -> dict[str, np.ndarray]:
    """Os 8 ângulos: os dois cotovelos seguem `principal`, o resto fica quase parado."""
    rng = np.random.default_rng(0)
    series = {}
    for nome in NOMES_ANGULOS:
        if nome.startswith("cotovelo"):
            series[nome] = principal.copy()
        else:
            series[nome] = 160 + rng.normal(0, 1, len(principal))
    return series


@pytest.fixture
def flexao() -> np.ndarray:
    return serie_flexao()


@pytest.fixture
def flexao_ruidosa() -> np.ndarray:
    """Mesma flexão com o tremor típico da detecção (desvio de 3°) e alguns quadros perdidos."""
    rng = np.random.default_rng(42)
    s = serie_flexao() + rng.normal(0, 3, len(serie_flexao()))
    s[[20, 21, 60, 100]] = np.nan
    return s


@pytest.fixture
def template_assimetrico() -> dict[str, list[float]]:
    """Modelo de 50 pontos em que esquerda e direita são diferentes (para testar o espelho)."""
    x = np.linspace(0, 2 * np.pi, 50)
    t = {}
    for i, nome in enumerate(NOMES_ANGULOS):
        base = 100 + 10 * i  # cada articulação com um valor diferente
        t[nome] = list(base + 20 * np.cos(x))
    return t
