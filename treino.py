"""
treino.py - Sessão de treino com a webcam, comparando você com o professor.
"""
import csv
import datetime
import json
import os
import time
import unicodedata
from collections import deque

import cv2
import numpy as np

import analise
from pose import ESPELHO, NOMES_ANGULOS, DetectorPose, calcular_angulos, desenhar_esqueleto
from referencia import PASTA_EXERCICIOS

BASE = os.path.dirname(os.path.abspath(__file__))
ARQ_HISTORICO = os.path.join(BASE, "historico.csv")
NOTA_MIN_ISOMETRICO = 70  # na prancha, só conta o tempo com postura nota >= 70


def sem_acento(t):
    # cv2.putText não desenha acentos (sairia "??"), então removemos na tela
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()


def texto(img, txt, pos, escala=0.7, cor=(255, 255, 255), esp=2):
    txt = sem_acento(txt)
    cv2.putText(img, txt, pos, cv2.FONT_HERSHEY_SIMPLEX, escala, (0, 0, 0), esp + 3, cv2.LINE_AA)
    cv2.putText(img, txt, pos, cv2.FONT_HERSHEY_SIMPLEX, escala, cor, esp, cv2.LINE_AA)


def cor_nota(n):
    return (0, 200, 0) if n >= 80 else (0, 200, 255) if n >= 60 else (0, 0, 255)


class PlayerReferencia:
    """Toca o clipe do professor em loop ao lado da webcam."""

    def __init__(self, caminho):
        self.cap = cv2.VideoCapture(caminho) if os.path.exists(caminho) else None
        self.fps = (self.cap.get(cv2.CAP_PROP_FPS) or 15) if self.cap else 15
        self.ultimo, self.t_ultimo = None, 0

    def quadro(self, altura):
        if self.cap is None:
            return None
        agora = time.monotonic()
        if self.ultimo is None or agora - self.t_ultimo >= 1 / self.fps:
            ok, f = self.cap.read()
            if not ok:  # acabou: volta para o início
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, f = self.cap.read()
            if ok:
                self.ultimo, self.t_ultimo = f, agora
        if self.ultimo is None:
            return None
        h, w = self.ultimo.shape[:2]
        return cv2.resize(self.ultimo, (int(w * altura / h), altura))

    def fechar(self):
        if self.cap:
            self.cap.release()


def carregar_exercicios():
    if not os.path.isdir(PASTA_EXERCICIOS):
        return []
    lista = []
    for arq in sorted(os.listdir(PASTA_EXERCICIOS)):
        if arq.endswith(".json"):
            with open(os.path.join(PASTA_EXERCICIOS, arq), encoding="utf-8") as f:
                d = json.load(f)
            d["_arquivo"] = arq
            lista.append(d)
    return lista


def salvar_historico(ex, quantidade, nota_media):
    novo = not os.path.exists(ARQ_HISTORICO)
    with open(ARQ_HISTORICO, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if novo:
            w.writerow(["data", "exercicio", "tipo", "reps_ou_segundos", "nota_media"])
        w.writerow([datetime.datetime.now().isoformat(timespec="minutes"), ex["nome"],
                    ex["tipo"], quantidade, nota_media])


def treinar(ex, meta, camera=0):
    """meta = número de repetições (exercício com reps) ou segundos (isométrico)."""
    isometrico = ex["tipo"] == "isometrico"
    template = ex["template"]
    principal = ex["angulo_principal"]

    cap = cv2.VideoCapture(camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        print("Não consegui abrir a webcam. Feche outros apps que estejam usando a câmera.")
        return

    det = DetectorPose()
    ref = PlayerReferencia(os.path.join(PASTA_EXERCICIOS, ex.get("clip", "")))
    janela = "Treino - Q para sair"

    if not isometrico:
        contador = analise.ContadorReps(ex["limiares"])
        janela_amp = {principal: deque(maxlen=90), ESPELHO[principal]: deque(maxlen=90)}
    historico = deque(maxlen=600)  # ~20 s de quadros, para recortar cada repetição
    reps, notas = 0, []
    tempo_ok, nota_viva = 0.0, 0.0
    sinal_suave = None
    ultima = {"nota": None, "dica": "Fique de corpo inteiro na camera", "pior": None}
    t0 = time.monotonic()
    t_anterior = t0
    contagem = 5  # segundos para você se posicionar
    fim_meta = None

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)  # efeito espelho: fica natural, igual a se olhar no espelho
        agora = time.monotonic()
        dt, t_anterior = agora - t_anterior, agora

        pontos = det.detectar(frame, (agora - t0) * 1000)
        angulos = calcular_angulos(pontos)
        h, w = frame.shape[:2]
        restante = contagem - (agora - t0)

        if restante > 0:
            texto(frame, f"Prepare-se: {int(restante) + 1}", (w // 2 - 150, h // 2), 1.5, esp=3)
            texto(frame, "Afaste-se ate aparecer o corpo inteiro", (w // 2 - 260, h // 2 + 50), 0.8)
        elif fim_meta is None:
            if isometrico:
                r = analise.comparar_pose(angulos, template)
                nota_viva = 0.8 * nota_viva + 0.2 * r["nota"]  # suaviza p/ o número não pular
                ultima = {"nota": int(nota_viva), "dica": r["dica"], "pior": r.get("pior")}
                if nota_viva >= NOTA_MIN_ISOMETRICO:
                    tempo_ok += dt
                    notas.append(nota_viva)
                if tempo_ok >= meta:
                    fim_meta = agora
            else:
                historico.append((agora, angulos))
                for n in janela_amp:
                    janela_amp[n].append(angulos[n])
                # usa o lado (esq/dir) que está se movendo mais: resolve o espelho
                lado = max(janela_amp, key=lambda n: analise.amplitude(list(janela_amp[n])))
                v = angulos[lado]
                if not np.isnan(v):
                    sinal_suave = v if sinal_suave is None else 0.5 * sinal_suave + 0.5 * v
                ev = contador.atualizar(sinal_suave, agora)
                if ev:
                    tipo, t_ini, t_fim = ev
                    if tipo == "parcial":
                        ultima = {"nota": ultima["nota"], "pior": principal,
                                  "dica": "Faltou amplitude: va ate o fim do movimento"}
                    else:
                        reps += 1
                        trecho = [a for t, a in historico if t_ini <= t <= t_fim]
                        serie = {n: [a[n] for a in trecho] for n in NOMES_ANGULOS}
                        r = analise.comparar_rep(serie, template)
                        if (t_fim - t_ini) < 0.5 * ex["duracao_media_s"]:
                            r["dica"] = "Muito rapido! Controle o movimento"
                        notas.append(r["nota"])
                        ultima = r
                        if reps >= meta:
                            fim_meta = agora

        # ------------------------------------------------ desenho da tela
        desenhar_esqueleto(frame, pontos, destaque=ultima.get("pior"))

        if not isometrico and restante <= 0:  # barra de profundidade (como no app do anúncio)
            p = contador.progresso(sinal_suave)
            x = w - 50
            cv2.rectangle(frame, (x, 120), (x + 25, h - 120), (60, 60, 60), -1)
            topo = int((h - 120) - p * (h - 240))
            cv2.rectangle(frame, (x, topo), (x + 25, h - 120), (255, 120, 200), -1)
            texto(frame, "PROF.", (x - 25, 110), 0.5)

        cv2.rectangle(frame, (0, 0), (w, 95), (30, 30, 30), -1)
        texto(frame, ex["nome"], (15, 35), 0.9)
        if isometrico:
            texto(frame, f"{tempo_ok:4.1f}s / {meta}s", (15, 80), 1.1, (255, 255, 0), 3)
        else:
            texto(frame, f"{reps} / {meta} reps", (15, 80), 1.1, (255, 255, 0), 3)
        if ultima["nota"] is not None:
            texto(frame, f"Nota {ultima['nota']}", (w - 220, 40), 1.0, cor_nota(ultima["nota"]), 3)
        texto(frame, ultima["dica"], (15, h - 20), 0.75,
              (0, 200, 255) if ultima.get("pior") else (0, 255, 0))
        if fim_meta:
            texto(frame, "META ATINGIDA!", (w // 2 - 200, h // 2), 1.6, (0, 255, 0), 4)

        quadro_ref = ref.quadro(h)
        tela = np.hstack([frame, quadro_ref]) if quadro_ref is not None else frame
        if tela.shape[1] > 1600:  # cabe na tela do notebook
            esc = 1600 / tela.shape[1]
            tela = cv2.resize(tela, None, fx=esc, fy=esc)
        cv2.imshow(janela, tela)

        tecla = cv2.waitKey(1) & 0xFF
        if tecla in (ord("q"), 27) or (fim_meta and agora - fim_meta > 3):
            break

    cap.release()
    ref.fechar()
    det.fechar()
    cv2.destroyAllWindows()
    cv2.waitKey(1)

    media = round(float(np.mean(notas)), 1) if notas else 0
    quantidade = round(tempo_ok, 1) if isometrico else reps
    salvar_historico(ex, quantidade, media)
    unidade = "segundos na posição correta" if isometrico else "repetições"
    print(f"\nResumo: {quantidade} {unidade}, nota média {media}.")
