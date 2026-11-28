"""Testes da validação de entrada do menu (NOTAS_FASE1.md, item 4)."""
import pytest

from app import converter_int


@pytest.mark.parametrize("texto, esperado", [("15", 15), (" 7 ", 7), ("", 10)])
def test_entradas_validas(texto, esperado):
    assert converter_int(texto, padrao=10, minimo=1) == esperado


@pytest.mark.parametrize("texto", ["abc", "1.5", "15 reps", "²", "0", "-5"])
def test_entradas_invalidas_avisam_em_vez_de_usar_o_padrao(texto):
    with pytest.raises(ValueError):
        converter_int(texto, padrao=10, minimo=1)


def test_camera_aceita_zero():
    assert converter_int("0", padrao=0, minimo=0) == 0


def test_respeita_o_maximo():
    with pytest.raises(ValueError, match="de 1 a 3"):
        converter_int("4", padrao=1, minimo=1, maximo=3)
