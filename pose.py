"""
pose.py - Detecção de pose com MediaPipe (API nova "Tasks") + cálculo de ângulos.

Por que a API "Tasks"? A partir do mediapipe 0.10.3x a API antiga
(mp.solutions.pose) foi removida. A maioria dos tutoriais na internet ainda
usa a antiga, então se você copiar código de lá vai dar erro.
"""
import os
import urllib.request

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

PASTA_BASE = os.path.dirname(os.path.abspath(__file__))
PASTA_MODELOS = os.path.join(PASTA_BASE, "modelos")

# "full" é o equilíbrio entre precisão e velocidade. Se ficar lento no seu PC,
# troque para "lite" (mais rápido, menos preciso) ou "heavy" (mais preciso, lento).
VARIANTE_MODELO = "full"
URL_MODELO = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    f"pose_landmarker_{VARIANTE_MODELO}/float16/latest/pose_landmarker_{VARIANTE_MODELO}.task"
)

# Índices dos 33 pontos do MediaPipe que usamos
# 11/12 ombros, 13/14 cotovelos, 15/16 pulsos, 23/24 quadris, 25/26 joelhos, 27/28 tornozelos
# Cada ângulo é definido por 3 pontos: (ponta, VÉRTICE, ponta)
ANGULOS = {
    "cotovelo esq": (11, 13, 15),
    "cotovelo dir": (12, 14, 16),
    "ombro esq":    (13, 11, 23),
    "ombro dir":    (14, 12, 24),
    "quadril esq":  (11, 23, 25),
    "quadril dir":  (12, 24, 26),
    "joelho esq":   (23, 25, 27),
    "joelho dir":   (24, 26, 28),
}
NOMES_ANGULOS = list(ANGULOS.keys())

# Pares esquerdo<->direito. Usado porque, quando você imita o professor de
# frente, o seu braço direito corresponde ao braço esquerdo dele (efeito espelho).
ESPELHO = {
    "cotovelo esq": "cotovelo dir", "cotovelo dir": "cotovelo esq",
    "ombro esq": "ombro dir", "ombro dir": "ombro esq",
    "quadril esq": "quadril dir", "quadril dir": "quadril esq",
    "joelho esq": "joelho dir", "joelho dir": "joelho esq",
}

# Linhas do "esqueleto" que desenhamos na tela
CONEXOES = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27), (24, 26), (26, 28),
]

VISIBILIDADE_MIN = 0.5  # abaixo disso o ponto é considerado "não visto"


def garantir_modelo():
    """Baixa o arquivo do modelo de IA na primeira execução (~10 MB)."""
    os.makedirs(PASTA_MODELOS, exist_ok=True)
    caminho = os.path.join(PASTA_MODELOS, f"pose_landmarker_{VARIANTE_MODELO}.task")
    if not os.path.exists(caminho) or os.path.getsize(caminho) < 1_000_000:
        print("Baixando modelo de pose do MediaPipe (só na primeira vez)...")
        urllib.request.urlretrieve(URL_MODELO, caminho)
    return caminho


class DetectorPose:
    """Envolve o PoseLandmarker em modo VIDEO.

    Modo VIDEO = o modelo usa o quadro anterior para "seguir" a pessoa,
    o que é mais estável e rápido do que analisar cada foto do zero.
    Exige que o timestamp de cada quadro seja sempre crescente.
    """

    def __init__(self):
        opcoes = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=garantir_modelo()),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._det = vision.PoseLandmarker.create_from_options(opcoes)
        self._ultimo_ts = -1

    def detectar(self, frame_bgr, timestamp_ms):
        """Retorna lista de 33 pontos (x_px, y_px, visibilidade) ou None."""
        ts = int(timestamp_ms)
        if ts <= self._ultimo_ts:  # garante tempo sempre crescente
            ts = self._ultimo_ts + 1
        self._ultimo_ts = ts

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)  # OpenCV usa BGR, o modelo espera RGB
        imagem = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        resultado = self._det.detect_for_video(imagem, ts)
        if not resultado.pose_landmarks:
            return None

        h, w = frame_bgr.shape[:2]
        # O modelo devolve coordenadas de 0 a 1. Convertemos para pixels para que
        # o ângulo não fique distorcido em telas que não são quadradas.
        return [(p.x * w, p.y * h, p.visibility if p.visibility is not None else 1.0)
                for p in resultado.pose_landmarks[0]]

    def fechar(self):
        self._det.close()


def angulo_3_pontos(a, b, c):
    """Ângulo (0-180°) no ponto b, formado pelos segmentos b->a e b->c."""
    ba = np.array(a[:2]) - np.array(b[:2])
    bc = np.array(c[:2]) - np.array(b[:2])
    norma = np.linalg.norm(ba) * np.linalg.norm(bc)
    if norma == 0:
        return float("nan")
    cos = np.clip(np.dot(ba, bc) / norma, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos)))


def calcular_angulos(pontos):
    """Dicionário {nome: ângulo}. NaN quando algum dos 3 pontos não está visível."""
    if pontos is None:
        return {n: float("nan") for n in NOMES_ANGULOS}
    res = {}
    for nome, (i, j, k) in ANGULOS.items():
        if min(pontos[i][2], pontos[j][2], pontos[k][2]) < VISIBILIDADE_MIN:
            res[nome] = float("nan")
        else:
            res[nome] = angulo_3_pontos(pontos[i], pontos[j], pontos[k])
    return res


def desenhar_esqueleto(frame, pontos, destaque=None, cor=(255, 120, 200)):
    """Desenha linhas e pontos. 'destaque' = nome de um ângulo para pintar de vermelho."""
    if pontos is None:
        return
    vermelhos = set(ANGULOS[destaque]) if destaque in ANGULOS else set()
    for i, j in CONEXOES:
        if pontos[i][2] >= VISIBILIDADE_MIN and pontos[j][2] >= VISIBILIDADE_MIN:
            c = (0, 0, 255) if (i in vermelhos and j in vermelhos) else cor
            cv2.line(frame, (int(pontos[i][0]), int(pontos[i][1])),
                     (int(pontos[j][0]), int(pontos[j][1])), c, 3)
    for idx in {i for par in CONEXOES for i in par}:
        x, y, v = pontos[idx]
        if v >= VISIBILIDADE_MIN:
            c = (0, 0, 255) if idx in vermelhos else (255, 255, 255)
            cv2.circle(frame, (int(x), int(y)), 6, c, -1)
