import math
import time

import cv2

from pose import DetectorPose, calcular_angulos, desenhar_esqueleto

ARTICULACAO = "cotovelo esq"  # troque por qualquer chave de pose.ANGULOS
FONTE = cv2.FONT_HERSHEY_SIMPLEX


def escrever(frame, texto: str, posicao: tuple[int, int]) -> None:
    """Escreve texto com contorno preto para ficar legível em qualquer fundo."""
    cv2.putText(frame, texto, posicao, FONTE, 1.0, (0, 0, 0), 4)    # contorno
    cv2.putText(frame, texto, posicao, FONTE, 1.0, (0, 255, 0), 2)  # verde


def main() -> None:
    detector = DetectorPose()
    cap = cv2.VideoCapture(0)

    try:
        ok, frame = cap.read()
        if ok:
            print(frame.shape)
        t0 = time.monotonic()
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Não consegui ler a camera")
                break
            timestamp_ms = (time.monotonic() - t0) * 1000
            pontos = detector.detectar(frame, timestamp_ms)
            desenhar_esqueleto(frame, pontos, destaque=ARTICULACAO)

            angulos = calcular_angulos(pontos)
            valor = angulos[ARTICULACAO]
            numero = "--" if math.isnan(valor) else f"{valor:.0f}"
            escrever(frame, f"{ARTICULACAO}: {numero}", (20, 40))

            cv2.imshow("Experimento", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        detector.fechar()


if __name__ == "__main__":
    main()
