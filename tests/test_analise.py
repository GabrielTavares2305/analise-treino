"""Testes de analise.py com dados simulados (Fase 2)."""
import numpy as np
import pytest

import analise
from conftest import FPS, serie_flexao, series_corpo
from pose import ESPELHO, NOMES_ANGULOS

NAN = float("nan")


# ------------------------------------------------------------- limpeza da série
class TestInterpolarNan:
    def test_preenche_buraco_com_reta_entre_vizinhos(self):
        assert analise.interpolar_nan([10, NAN, NAN, 40]).tolist() == [10, 20, 30, 40]

    def test_pontas_repetem_o_valor_conhecido_mais_proximo(self):
        assert analise.interpolar_nan([NAN, 5, 7, NAN]).tolist() == [5, 5, 7, 7]

    def test_com_menos_de_dois_valores_devolve_sem_mexer(self):
        assert np.isnan(analise.interpolar_nan([NAN, 3, NAN])[0])


class TestSuavizar:
    def test_mantem_o_tamanho(self, flexao_ruidosa):
        assert len(analise.suavizar(flexao_ruidosa)) == len(flexao_ruidosa)

    def test_nao_deixa_nan(self, flexao_ruidosa):
        assert not np.isnan(analise.suavizar(flexao_ruidosa)).any()

    def test_reduz_o_tremor(self, flexao, flexao_ruidosa):
        erro_antes = np.nanstd(flexao_ruidosa - flexao)
        erro_depois = np.std(analise.suavizar(flexao_ruidosa) - flexao)
        assert erro_depois < erro_antes

    def test_serie_constante_continua_constante(self):
        assert np.allclose(analise.suavizar([90.0] * 20), 90.0)


class TestAmplitude:
    def test_flexao_tem_amplitude_proxima_de_120(self, flexao):
        assert 100 < analise.amplitude(flexao) <= 120

    def test_ignora_um_pico_isolado_de_erro(self):
        s = [90.0] * 50
        s[25] = 180.0  # o detector "pulou" num quadro
        assert analise.amplitude(s) == 0.0

    def test_serie_curta_demais_vale_zero(self):
        assert analise.amplitude([10, 100, 10]) == 0.0


class TestReamostrar:
    @pytest.mark.parametrize("tamanho", [10, 37, 200])
    def test_qualquer_duracao_vira_50_pontos(self, tamanho):
        assert len(analise.reamostrar(np.linspace(0, 1, tamanho))) == analise.PONTOS_TEMPLATE

    def test_preserva_inicio_e_fim(self):
        r = analise.reamostrar([170, 120, 50, 120, 170])
        assert r[0] == 170 and r[-1] == 170

    def test_tudo_nan_devolve_tudo_nan(self):
        assert np.isnan(analise.reamostrar([NAN] * 10)).all()


# ------------------------------------------------------- ângulo principal
class TestAnguloPrincipal:
    def test_escolhe_a_articulacao_que_mais_se_move(self, flexao):
        series = series_corpo(flexao)
        series["joelho esq"] = np.full(len(flexao), 170.0)
        assert analise.escolher_angulo_principal(series).startswith("cotovelo")

    def test_ignora_articulacao_pouco_visivel_mesmo_que_se_mova(self, flexao):
        series = series_corpo(np.full(len(flexao), 170.0))
        quase_invisivel = serie_flexao(fechado=0)
        quase_invisivel[: int(len(quase_invisivel) * 0.5)] = np.nan
        series["joelho dir"] = quase_invisivel
        assert analise.escolher_angulo_principal(series) != "joelho dir"

    def test_corpo_invisivel_gera_erro_claro(self):
        with pytest.raises(ValueError, match="visível"):
            analise.escolher_angulo_principal({n: [NAN] * 30 for n in NOMES_ANGULOS})


class TestLimiares:
    def test_flexao_comeca_em_repouso_alto(self, flexao):
        lim = analise.calcular_limiares(flexao)
        assert lim["repouso_alto"] is True
        assert lim["minimo"] < lim["baixo"] < lim["alto"] < lim["maximo"]

    def test_folga_de_30_por_cento(self, flexao):
        lim = analise.calcular_limiares(flexao)
        faixa = lim["maximo"] - lim["minimo"]
        assert lim["baixo"] == pytest.approx(lim["minimo"] + 0.3 * faixa)

    def test_exercicio_que_comeca_fechado(self):
        # ex.: elevação de perna, que começa com o quadril "fechado"
        lim = analise.calcular_limiares(220 - serie_flexao())
        assert lim["repouso_alto"] is False


# --------------------------------------------------------- contador de reps
LIM_FIXOS = {"minimo": 50, "maximo": 170, "baixo": 86, "alto": 134, "repouso_alto": True}


def rodar(valores, limiares=LIM_FIXOS):
    c = analise.ContadorReps(limiares)
    return [ev for i, v in enumerate(valores) if (ev := c.atualizar(v, i))]


class TestContadorReps:
    def test_um_ciclo_completo_e_uma_rep(self):
        assert rodar([170, 120, 60, 120, 170]) == [("rep", 1, 4)]

    def test_volta_sem_chegar_ao_extremo_e_parcial(self):
        assert rodar([170, 120, 100, 150]) == [("parcial", 1, 3)]

    def test_histerese_tremor_no_extremo_nao_conta_reps_a_mais(self):
        # no fundo da flexão o ângulo treme em volta do limite "baixo" (86)
        assert [e[0] for e in rodar([170, 80, 90, 80, 90, 80, 160])] == ["rep"]

    def test_nan_e_none_sao_ignorados(self):
        assert [e[0] for e in rodar([170, NAN, 60, None, 170])] == ["rep"]

    def test_progresso_vai_de_0_no_repouso_a_1_no_extremo(self):
        c = analise.ContadorReps(LIM_FIXOS)
        assert c.progresso(170) == 0.0
        assert c.progresso(50) == 1.0
        assert c.progresso(110) == pytest.approx(0.5)


class TestDetectarReps:
    @pytest.mark.parametrize("reps", [1, 3, 8])
    def test_conta_as_reps_da_serie_limpa(self, reps):
        s = serie_flexao(reps=reps)
        lim = analise.calcular_limiares(analise.suavizar(s))
        assert len(analise.detectar_reps(s, lim)) == reps

    def test_conta_certo_mesmo_com_ruido_e_buracos(self, flexao_ruidosa):
        lim = analise.calcular_limiares(analise.suavizar(flexao_ruidosa))
        assert len(analise.detectar_reps(flexao_ruidosa, lim)) == 5


# ------------------------------------------------------ modelo do professor
class TestCriarTemplate:
    def test_template_tem_50_pontos_por_articulacao(self, flexao):
        series = series_corpo(flexao)
        reps = analise.detectar_reps(flexao, analise.calcular_limiares(flexao))
        template, _ = analise.criar_template(series, reps, FPS)
        assert set(template) == set(NOMES_ANGULOS)
        assert all(len(v) == analise.PONTOS_TEMPLATE for v in template.values())

    def test_descarta_articulacao_fora_do_quadro(self, flexao):
        series = series_corpo(flexao)
        series["joelho esq"] = np.full(len(flexao), NAN)
        reps = analise.detectar_reps(flexao, analise.calcular_limiares(flexao))
        template, _ = analise.criar_template(series, reps, FPS)
        assert "joelho esq" not in template

    def test_duracao_conta_so_o_trecho_fora_do_repouso(self, flexao):
        # Cada rep simulada dura 2 s, mas o contador só "liga" ao sair da zona de
        # repouso (30% da faixa). Num cosseno isso dá ~63% do ciclo ≈ 1,3 s.
        # Professor e aluno são medidos igual, então a comparação é justa,
        # mas o "~Xs cada" do menu subestima a duração real (NOTAS_FASE1, item 7).
        reps = analise.detectar_reps(flexao, analise.calcular_limiares(flexao))
        _, duracao = analise.criar_template(series_corpo(flexao), reps, FPS)
        assert duracao == pytest.approx(1.3, abs=0.15)


# ------------------------------------------------------ comparação e nota
class TestCompararRep:
    def test_rep_identica_ao_modelo_tira_100(self, template_assimetrico):
        r = analise.comparar_rep(template_assimetrico, template_assimetrico)
        assert r["nota"] == 100 and r["pior"] is None

    def test_rep_espelhada_tambem_tira_100(self, template_assimetrico):
        espelhada = {ESPELHO[n]: v for n, v in template_assimetrico.items()}
        assert analise.comparar_rep(espelhada, template_assimetrico)["nota"] == 100

    def test_formula_da_nota_com_um_erro_grande(self, template_assimetrico):
        # joelho 30° mais aberto, o resto perfeito:
        # erro médio = 30/8 = 3,75 → 100 - 1,5*3,75 - (30-15) = 79,4 → 79
        rep = dict(template_assimetrico)
        rep["joelho dir"] = [v + 30 for v in rep["joelho dir"]]
        r = analise.comparar_rep(rep, template_assimetrico)
        assert r["nota"] == 79
        assert r["pior"] == "joelho dir"
        assert "esticado" in r["dica"]

    def test_corpo_fora_da_camera(self, template_assimetrico):
        assert analise.comparar_rep({}, template_assimetrico)["nota"] == 0


class TestCompararPose:
    POSE = {n: [150.0 + i] for i, n in enumerate(NOMES_ANGULOS)}

    def test_postura_identica_tira_100(self):
        angulos = {n: v[0] for n, v in self.POSE.items()}
        assert analise.comparar_pose(angulos, self.POSE)["nota"] == 100

    def test_quadril_caido_na_prancha_derruba_a_nota(self):
        angulos = {n: v[0] for n, v in self.POSE.items()}
        angulos["quadril esq"] -= 40
        r = analise.comparar_pose(angulos, self.POSE)
        assert r["nota"] < analise_nota_min_isometrico()
        assert "dobrado" in r["dica"]

    def test_menos_da_metade_visivel_nao_da_nota(self):
        angulos = {n: NAN for n in NOMES_ANGULOS}
        angulos["cotovelo esq"] = 150.0
        assert analise.comparar_pose(angulos, self.POSE)["nota"] == 0


def analise_nota_min_isometrico() -> int:
    from treino import NOTA_MIN_ISOMETRICO
    return NOTA_MIN_ISOMETRICO
