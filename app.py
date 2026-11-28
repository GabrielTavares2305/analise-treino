"""
app.py - Menu principal. Rode com:  python app.py
"""
import csv
import os

from yt_dlp.utils import DownloadError

import referencia
import treino


def converter_int(texto: str, padrao: int, minimo: int = 0, maximo: int | None = None) -> int:
    """Converte a resposta do usuário. Vazio = padrão. Lança ValueError com a explicação.

    Separada de pedir_int (que faz o input) para poder ser testada sem teclado.
    """
    texto = texto.strip()
    if not texto:
        return padrao
    try:
        valor = int(texto)
    except ValueError:
        raise ValueError(f"'{texto}' não é um número inteiro.") from None
    if valor < minimo or (maximo is not None and valor > maximo):
        faixa = f"de {minimo} a {maximo}" if maximo is not None else f"a partir de {minimo}"
        raise ValueError(f"Digite um número {faixa}.")
    return valor


def pedir_int(msg: str, padrao: int, minimo: int = 0, maximo: int | None = None) -> int:
    """Pergunta até receber um inteiro válido (EAFP: tenta converter e trata o erro)."""
    while True:
        try:
            return converter_int(input(f"{msg} [{padrao}]: "), padrao, minimo, maximo)
        except ValueError as e:
            print(f"  {e}")


def adicionar_exercicio() -> None:
    print("\nCole o link do YouTube OU o caminho de um vídeo no seu computador.")
    origem = input("> ").strip().strip('"')
    if not origem:
        return
    if origem.startswith("http"):
        # só o download fica no try: outros erros (bugs) devem aparecer com traceback
        try:
            caminho, _titulo = referencia.baixar_youtube(origem)
        except DownloadError as e:
            print(f"Erro ao baixar: {e}\nDica: rode 'pip install -U yt-dlp' e tente de novo.")
            return
    else:
        caminho = origem
        if not os.path.exists(caminho):
            print("Arquivo não encontrado.")
            return

    while True:
        nome = input("\nNome do exercício (ex.: Prancha, Flexão, Superman): ").strip()
        if not nome:
            break
        print("Vai abrir o vídeo. Marque o INÍCIO (I) e o FIM (F) do exercício e aperte ENTER.")
        referencia.criar_exercicio(caminho, nome, origem)
        # uma aula costuma ter vários exercícios: aproveita o mesmo vídeo
        if input("Cadastrar outro exercício deste mesmo vídeo? (s/n) ").lower() != "s":
            break


def escolher_exercicio(titulo):
    lista = treino.carregar_exercicios()
    if not lista:
        print("\nNenhum exercício cadastrado. Use a opção 1 primeiro.")
        return None
    print(f"\n{titulo}")
    for i, ex in enumerate(lista, 1):
        tipo = "isométrico" if ex["tipo"] == "isometrico" else f"reps, ~{ex['duracao_media_s']}s cada"
        print(f"  {i}. {ex['nome']}  ({tipo})")
    n = pedir_int("Número", 1, minimo=1, maximo=len(lista))
    return lista[n - 1]


def menu_treinar():
    ex = escolher_exercicio("Qual exercício?")
    if not ex:
        return
    if ex["tipo"] == "isometrico":
        meta = pedir_int("Quantos segundos segurar a posição?", 30, minimo=1)
    else:
        meta = pedir_int("Quantas repetições?", 10, minimo=1)
    camera = pedir_int("Número da câmera (0 = webcam padrão)", 0)
    treino.treinar(ex, meta, camera)


def ver_historico():
    if not os.path.exists(treino.ARQ_HISTORICO):
        print("\nAinda não há treinos registrados.")
        return
    with open(treino.ARQ_HISTORICO, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    print(f"\n{'Data':17} {'Exercício':20} {'Qtd':>6} {'Nota':>6}")
    for l in linhas[-20:]:
        print(f"{l['data']:17} {l['exercicio'][:20]:20} {l['reps_ou_segundos']:>6} {l['nota_media']:>6}")


def remover_exercicio():
    ex = escolher_exercicio("Qual exercício remover?")
    if not ex:
        return
    base = os.path.join(referencia.PASTA_EXERCICIOS, ex["_arquivo"][:-5])
    for ext in (".json", ".mp4"):
        if os.path.exists(base + ext):
            os.remove(base + ext)
    print(f"'{ex['nome']}' removido.")


def main():
    opcoes = {
        "1": ("Adicionar exercício a partir de um vídeo (YouTube ou arquivo)", adicionar_exercicio),
        "2": ("Treinar", menu_treinar),
        "3": ("Ver histórico", ver_historico),
        "4": ("Remover exercício", remover_exercicio),
    }
    while True:
        print("\n=== TREINO FORA DA ÁGUA ===")
        for k, (txt, _) in opcoes.items():
            print(f"  {k}. {txt}")
        print("  0. Sair")
        escolha = input("> ").strip()
        if escolha == "0":
            break
        if escolha in opcoes:
            opcoes[escolha][1]()


if __name__ == "__main__":
    main()
