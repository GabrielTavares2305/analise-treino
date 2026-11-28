"""
analise.py - A "inteligência" do treino, sem câmera nem tela.

Fica separado de propósito: assim dá para testar a lógica com números
simulados, sem precisar ficar fazendo exercício na frente da webcam.
"""
import numpy as np

from pose import ESPELHO

PONTOS_TEMPLATE = 50  # toda repetição é "esticada/encolhida" para 50 amostras


# ---------------------------------------------------------------- séries
def interpolar_nan(serie):
    """Preenche buracos (quadros em que o corpo não foi visto) ligando os vizinhos."""
    s = np.asarray(serie, dtype=float)
    ok = ~np.isnan(s)
    if ok.sum() < 2:
        return s
    idx = np.arange(len(s))
    return np.interp(idx, idx[ok], s[ok])


def suavizar(serie, janela=5):
    """Média móvel: a detecção 'treme' alguns graus de um quadro para o outro."""
    s = interpolar_nan(serie)
    if len(s) < janela or np.isnan(s).all():
        return s
    kernel = np.ones(janela) / janela
    pad = janela // 2
    return np.convolve(np.pad(s, pad, mode="edge"), kernel, mode="valid")[: len(s)]


def amplitude(serie):
    """Diferença entre os percentis 95 e 5: ignora picos causados por erro de detecção."""
    s = np.asarray(serie, dtype=float)
    s = s[~np.isnan(s)]
    if len(s) < 5:
        return 0.0
    return float(np.percentile(s, 95) - np.percentile(s, 5))


def reamostrar(serie, n=PONTOS_TEMPLATE):
    """Transforma uma repetição de qualquer duração em n pontos.
    Assim dá para comparar uma flexão sua de 2 s com uma de 3 s do professor."""
    s = interpolar_nan(serie)
    if len(s) < 2 or np.isnan(s).all():
        return np.full(n, np.nan)
    return np.interp(np.linspace(0, len(s) - 1, n), np.arange(len(s)), s)


# ------------------------------------------------- escolha do ângulo-chave
def escolher_angulo_principal(series):
    """O ângulo que mais se move no vídeo é o que define o exercício.
    Ex.: na flexão é o cotovelo; no agachamento, o joelho."""
    candidatos = {}
    for nome, s in series.items():
        s = np.asarray(s, dtype=float)
        if np.mean(~np.isnan(s)) >= 0.6:  # precisa estar visível em 60% do tempo
            candidatos[nome] = amplitude(s)
    if not candidatos:
        raise ValueError("O corpo não ficou visível o suficiente no trecho escolhido.")
    return max(candidatos, key=candidatos.get)


def calcular_limiares(serie):
    """Define 'zona de repouso' e 'zona do outro extremo' com folga de 30%.

    Usar dois limites diferentes (histerese) evita contar repetição em dobro
    quando o ângulo fica 'tremendo' perto de um único valor.
    """
    s = interpolar_nan(serie)
    p5, p95 = np.nanpercentile(s, 5), np.nanpercentile(s, 95)
    faixa = p95 - p5
    inicio = np.nanmedian(s[: max(3, len(s) // 10)])
    return {
        "minimo": float(p5),
        "maximo": float(p95),
        "baixo": float(p5 + 0.3 * faixa),
        "alto": float(p95 - 0.3 * faixa),
        # o exercício começa com o ângulo aberto (ex.: braço esticado) ou fechado?
        "repouso_alto": bool(inicio >= (p5 + p95) / 2),
    }


# --------------------------------------------------------- contador de reps
class ContadorReps:
    """Máquina de estados: repouso -> saindo -> extremo -> repouso (= 1 rep).

    Se a pessoa sai do repouso mas volta sem chegar ao outro extremo,
    gera um evento 'parcial', usado para avisar 'faltou amplitude'.
    """

    def __init__(self, limiares):
        self.lim = limiares
        self.estado = "repouso"
        self.t_inicio = None

    def _em_repouso(self, v):
        return v >= self.lim["alto"] if self.lim["repouso_alto"] else v <= self.lim["baixo"]

    def _no_extremo(self, v):
        return v <= self.lim["baixo"] if self.lim["repouso_alto"] else v >= self.lim["alto"]

    def atualizar(self, valor, t):
        """Retorna None, ('rep', t_ini, t_fim) ou ('parcial', t_ini, t_fim)."""
        if valor is None or np.isnan(valor):
            return None
        if self.estado == "repouso":
            if not self._em_repouso(valor):
                # pode já chegar no extremo (ex.: quadros perdidos no meio da descida)
                self.estado = "extremo" if self._no_extremo(valor) else "saindo"
                self.t_inicio = t
        elif self.estado == "saindo":
            if self._no_extremo(valor):
                self.estado = "extremo"
            elif self._em_repouso(valor):
                self.estado = "repouso"
                return ("parcial", self.t_inicio, t)
        elif self.estado == "extremo":
            if self._em_repouso(valor):
                self.estado = "repouso"
                return ("rep", self.t_inicio, t)
        return None

    def progresso(self, valor):
        """0 = posição de repouso, 1 = outro extremo. Usado na barra lateral."""
        if valor is None or np.isnan(valor):
            return 0.0
        lo, hi = self.lim["minimo"], self.lim["maximo"]
        p = (valor - lo) / (hi - lo) if hi > lo else 0.0
        p = 1 - p if self.lim["repouso_alto"] else p
        return float(np.clip(p, 0, 1))


def detectar_reps(serie, limiares):
    """Roda o contador sobre uma série inteira. Retorna [(i_ini, i_fim), ...]."""
    c = ContadorReps(limiares)
    reps = []
    for i, v in enumerate(suavizar(serie)):
        ev = c.atualizar(v, i)
        if ev and ev[0] == "rep":
            reps.append((ev[1], ev[2]))
    return reps


# ------------------------------------------------------ modelo do professor
def criar_template(series, reps, fps):
    """Média de todas as repetições do professor, ângulo por ângulo.

    A média 'apaga' pequenas variações e deixa o movimento ideal.
    Ângulos que não aparecem no vídeo (ex.: pernas fora do quadro) são descartados.
    """
    template = {}
    for nome, s in series.items():
        s = suavizar(s)
        if np.mean(~np.isnan(np.asarray(series[nome], dtype=float))) < 0.6:
            continue
        curvas = [reamostrar(s[i:f + 1]) for i, f in reps]
        media = np.nanmean(np.vstack(curvas), axis=0)
        if not np.isnan(media).any():
            template[nome] = [round(float(x), 2) for x in media]
    duracoes = [(f - i + 1) / fps for i, f in reps]
    return template, float(np.mean(duracoes))


# ------------------------------------------------------ comparar com você
def _diferencas(rep, template, espelhar):
    difs = {}
    for nome, ref in template.items():
        nome_vivo = ESPELHO[nome] if espelhar else nome
        vivo = reamostrar(rep.get(nome_vivo, []))
        if np.isnan(vivo).all():
            continue
        d = vivo - np.asarray(ref)
        difs[nome_vivo] = (float(np.nanmean(np.abs(d))), float(np.nanmean(d)))
    return difs


def comparar_rep(rep, template):
    """Compara uma repetição sua com o modelo.

    Testa as duas formas (normal e espelhada) e fica com a melhor, porque não
    sabemos se você está imitando o professor como num espelho ou não.

    A fórmula da nota está em _montar_resultado.
    """
    melhor = None
    for espelhar in (False, True):
        difs = _diferencas(rep, template, espelhar)
        if not difs:
            continue
        erro = float(np.mean([v[0] for v in difs.values()]))
        if melhor is None or erro < melhor["erro_medio"]:
            melhor = {"erro_medio": erro, "difs": difs, "espelhado": espelhar}
    if melhor is None:
        return {"nota": 0, "dica": "Corpo fora da camera", "difs": {}}

    return _montar_resultado(melhor)


def comparar_pose(angulos, pose_ref):
    """Para exercícios isométricos (prancha, superman...): compara a postura
    de UM quadro com a postura média do professor. Também testa o espelho."""
    melhor = None
    for espelhar in (False, True):
        difs = {}
        for nome, ref in pose_ref.items():
            nome_vivo = ESPELHO[nome] if espelhar else nome
            v = angulos.get(nome_vivo, np.nan)
            if not np.isnan(v):
                d = v - ref[0]
                difs[nome_vivo] = (abs(d), d)
        # exige ver ao menos metade das articulações, senão a nota seria enganosa
        if len(difs) < max(1, len(pose_ref) // 2):
            continue
        erro = float(np.mean([x[0] for x in difs.values()]))
        if melhor is None or erro < melhor["erro_medio"]:
            melhor = {"erro_medio": erro, "difs": difs, "espelhado": espelhar}
    if melhor is None:
        return {"nota": 0, "dica": "Corpo fora da camera", "difs": {}, "pior": None}
    return _montar_resultado(melhor)


def _montar_resultado(melhor):
    # Nota = 100 - 1.5 x erro médio - 1 x (quanto o PIOR erro passa de 15°).
    # O segundo termo existe porque um único erro grande (ex.: quadril caído
    # na prancha) se "dilui" na média das outras articulações que estão certas.
    pior_nome, (pior_abs, pior_sinal) = max(melhor["difs"].items(), key=lambda kv: kv[1][0])
    nota = int(np.clip(100 - 1.5 * melhor["erro_medio"] - max(0.0, pior_abs - 15), 0, 100))
    if pior_abs < 15:
        dica = "Boa! Movimento parecido com o do professor"
    else:
        sentido = "esticado" if pior_sinal > 0 else "dobrado"
        dica = f"{pior_nome}: {pior_abs:.0f} graus mais {sentido}"
    return {"nota": nota, "dica": dica, "pior": pior_nome if pior_abs >= 15 else None,
            "difs": melhor["difs"]}
