"""
referencia.py - Transforma um vídeo do professor em um "exercício" do menu.

Etapas:
  1. Baixar o vídeo do YouTube (ou usar um arquivo do seu PC)
  2. Você marca o início e o fim do exercício (a aula tem vários)
  3. O programa analisa o professor quadro a quadro e salva o modelo em JSON
"""
import datetime
import json
import os
import re
import unicodedata

import cv2
import numpy as np

import analise
from pose import DetectorPose, NOMES_ANGULOS, calcular_angulos, desenhar_esqueleto

BASE = os.path.dirname(os.path.abspath(__file__))
PASTA_VIDEOS = os.path.join(BASE, "videos")
PASTA_EXERCICIOS = os.path.join(BASE, "exercicios")
FPS_ANALISE = 15  # analisar 15 quadros/s é suficiente e 2x mais rápido que 30
LIMITE_ISOMETRICO = 20  # se nada se mover mais que 20°, é exercício parado


def slug(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-") or "exercicio"


# ------------------------------------------------------------------ download
def baixar_youtube(url):
    """Baixa o vídeo em até 720p no formato mp4 'progressivo'.

    'Progressivo' = áudio e vídeo no mesmo arquivo. Assim não precisamos
    instalar o ffmpeg para juntar as partes. Para análise de pose, 360-720p
    é mais que suficiente.
    """
    from yt_dlp import YoutubeDL

    os.makedirs(PASTA_VIDEOS, exist_ok=True)
    opcoes = {
        "format": "best[height<=720][ext=mp4]/best[height<=720]/best",
        "outtmpl": os.path.join(PASTA_VIDEOS, "%(id)s.%(ext)s"),
        "quiet": True,
        "noprogress": False,
    }
    with YoutubeDL(opcoes) as ydl:
        info = ydl.extract_info(url, download=True)
        caminho = ydl.prepare_filename(info)
    print(f"Vídeo baixado: {info.get('title')}")
    return caminho, info.get("title", "")


# ------------------------------------------------------- marcar o trecho
def _texto(img, txt, pos, escala=0.6, cor=(255, 255, 255)):
    # contorno preto + texto branco = legível em qualquer fundo
    cv2.putText(img, txt, pos, cv2.FONT_HERSHEY_SIMPLEX, escala, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(img, txt, pos, cv2.FONT_HERSHEY_SIMPLEX, escala, cor, 1, cv2.LINE_AA)


def marcar_trecho(caminho):
    """Player simples para você marcar onde o exercício começa e termina.

    Obs.: o OpenCV só desenha texto sem acento, por isso a tela não usa acentos.
    """
    cap = cv2.VideoCapture(caminho)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    pos, pausado, inicio, fim = 0, False, None, None
    janela = "Marque o trecho do exercicio"
    frame = None

    while True:
        if not pausado or frame is None:
            cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            ok, frame = cap.read()
            if not ok:
                pos, pausado = max(0, total - 1), True
                continue
            pos += 1
        tela = frame.copy()
        h, w = tela.shape[:2]
        if h > 720:
            tela = cv2.resize(tela, (int(w * 720 / h), 720))
            h, w = tela.shape[:2]

        # barra de tempo com o trecho marcado em verde
        cv2.rectangle(tela, (10, h - 25), (w - 10, h - 15), (80, 80, 80), -1)
        if inicio is not None:
            x0 = 10 + int((w - 20) * inicio / total)
            x1 = 10 + int((w - 20) * (fim if fim is not None else pos) / total)
            cv2.rectangle(tela, (x0, h - 25), (x1, h - 15), (0, 200, 0), -1)
        cv2.circle(tela, (10 + int((w - 20) * pos / max(total, 1)), h - 20), 7, (0, 0, 255), -1)

        _texto(tela, f"{pos / fps:6.1f}s / {total / fps:.0f}s   {'PAUSADO' if pausado else ''}", (10, 25))
        _texto(tela, f"Inicio: {inicio / fps if inicio is not None else 0:.1f}s   "
                     f"Fim: {fim / fps if fim is not None else 0:.1f}s", (10, 50))
        _texto(tela, "ESPACO pausa | A/D -5s +5s | J/L -1s +1s | I inicio | F fim | "
                     "ENTER ok | ESC sai", (10, h - 35), 0.45)
        cv2.imshow(janela, tela)

        tecla = cv2.waitKey(int(1000 / fps) if not pausado else 30) & 0xFF
        if tecla == ord(" "):
            pausado = not pausado
        elif tecla in (ord("a"), ord("d"), ord("j"), ord("l")):
            passo = {"a": -5, "d": 5, "j": -1, "l": 1}[chr(tecla)]
            pos = int(np.clip(pos + passo * fps, 0, total - 1))
            frame = None  # força ler o novo quadro mesmo pausado
        elif tecla == ord("i"):
            inicio, fim = pos, None
        elif tecla == ord("f") and inicio is not None and pos > inicio:
            fim = pos
        elif tecla == 13 and inicio is not None and fim is not None:  # ENTER
            break
        elif tecla == 27:  # ESC
            inicio = fim = None
            break

    cap.release()
    cv2.destroyWindow(janela)
    cv2.waitKey(1)
    if inicio is None:
        return None
    return inicio / fps, fim / fps


# ------------------------------------------------------- extrair o modelo
def extrair_series(caminho, ini_s, fim_s, caminho_clip):
    """Passa o trecho pelo detector e guarda os ângulos de cada quadro.
    De quebra, grava um clipe curto com o esqueleto desenhado, que aparece
    ao lado da sua webcam durante o treino."""
    cap = cv2.VideoCapture(caminho)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    passo = max(1, round(fps / FPS_ANALISE))
    fps_util = fps / passo
    i0, i1 = int(ini_s * fps), int(fim_s * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, i0)

    det = DetectorPose()
    series = {n: [] for n in NOMES_ANGULOS}
    gravador = None
    idx = i0
    print("Analisando o professor", end="", flush=True)
    while idx <= i1:
        ok, frame = cap.read()
        if not ok:
            break
        if (idx - i0) % passo == 0:
            pontos = det.detectar(frame, idx * 1000 / fps)
            for n, v in calcular_angulos(pontos).items():
                series[n].append(v)

            desenhar_esqueleto(frame, pontos)
            h, w = frame.shape[:2]
            pequeno = cv2.resize(frame, (int(w * 480 / h), 480))
            if gravador is None:
                gravador = cv2.VideoWriter(caminho_clip, cv2.VideoWriter_fourcc(*"mp4v"),
                                           fps_util, (pequeno.shape[1], 480))
            gravador.write(pequeno)
            if len(series[NOMES_ANGULOS[0]]) % 30 == 0:
                print(".", end="", flush=True)
        idx += 1
    print(" pronto!")
    det.fechar()
    cap.release()
    if gravador:
        gravador.release()
    return {n: np.array(v, dtype=float) for n, v in series.items()}, fps_util


def criar_exercicio(caminho_video, nome, origem):
    trecho = marcar_trecho(caminho_video)
    if trecho is None:
        print("Cancelado.")
        return None
    ini_s, fim_s = trecho
    os.makedirs(PASTA_EXERCICIOS, exist_ok=True)
    s = slug(nome)
    caminho_clip = os.path.join(PASTA_EXERCICIOS, f"{s}.mp4")

    series, fps = extrair_series(caminho_video, ini_s, fim_s, caminho_clip)
    principal = analise.escolher_angulo_principal(series)
    amp = analise.amplitude(series[principal])

    dados = {
        "nome": nome, "origem": origem, "inicio_s": round(ini_s, 1), "fim_s": round(fim_s, 1),
        "clip": os.path.basename(caminho_clip), "angulo_principal": principal,
        "criado_em": datetime.datetime.now().isoformat(timespec="seconds"),
    }

    if amp < LIMITE_ISOMETRICO:
        # Exercício parado: o modelo é a postura média (mediana) do professor
        dados["tipo"] = "isometrico"
        dados["template"] = {
            n: [round(float(np.nanmedian(v)), 2)]
            for n, v in series.items() if np.mean(~np.isnan(v)) >= 0.6
        }
        print(f"Exercício ISOMÉTRICO detectado (o corpo quase não se move, {amp:.0f}°).")
    else:
        lim = analise.calcular_limiares(analise.suavizar(series[principal]))
        reps = analise.detectar_reps(series[principal], lim)
        if not reps:
            print("Não encontrei repetições completas nesse trecho. Tente marcar um "
                  "trecho com pelo menos 2 repetições inteiras e o professor visível.")
            return None
        template, dur = analise.criar_template(series, reps, fps)
        dados.update({"tipo": "repeticao", "limiares": lim, "template": template,
                      "duracao_media_s": round(dur, 2), "reps_no_video": len(reps)})
        print(f"{len(reps)} repetições encontradas. Articulação principal: {principal}. "
              f"Cada repetição leva ~{dur:.1f}s.")

    print(f"Articulações usadas na comparação: {', '.join(dados['template'])}")
    with open(os.path.join(PASTA_EXERCICIOS, f"{s}.json"), "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    print(f"Exercício '{nome}' salvo no menu!")
    return dados
