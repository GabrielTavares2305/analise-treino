# Notas da Fase 1

## 1. OpenCV instalado duas vezes (opencv-python + opencv-contrib-python)
- O que encontrei - Utilizando o pip list encontrei o opencv-python e o opencv-contrib-python e depois usando o pip show o pip show opencv-contrib-python mostrou Required-by: mediapipe, ou seja, o contrib é dependência do mediapipe

- Por que é um problema - Se um for atualizado e o outro não, teremos problemas por versões divergentes, desinstalando um deles podemos apagar a pasta cv2 que é compartilhada com o contrib, deixando o contrib quebrado

- Causa - No requirements pede o opencv-python mas o mediapipe já traz o opencv-contrib-python  

- Correção proposta - Trocar no requirements para o opencv-contrib-python e, como no venv atual estão os 2 pacotes, desinstalar o opencv-python e forçar a reinstalação do opencv-contrib-python (para recriar a pasta cv2 que a desinstalação apaga)

## 2. requirements.txt sem versões travadas
- **O que encontrei:** o `requirements.txt` tem 4 pacotes e só um com especificador de versão
  (`mediapipe>=0.10.30`); os outros três aceitam qualquer versão. O `pip freeze` lista 30 pacotes
  instalados: os outros 26 são dependências transitivas (dependências das dependências) e não estão
  registrados em lugar nenhum. O `>=0.10.30` deixou instalar o `mediapipe==1.2.3`.

- **Por que é um problema:** falta reprodutibilidade. Um `pip install -r requirements.txt` feito em outro
  dia (ou em outra máquina) baixa as versões mais novas daquele momento, que podem mudar a API e quebrar
  o código, como aconteceu quando o MediaPipe removeu o `mp.solutions.pose`. O `>=` sem limite superior
  aceita até uma mudança de versão MAIOR (0.x → 1.x), que pelo Versionamento Semântico indica mudanças
  incompatíveis.

- **Causa:** comparando com o Composer, o `requirements.txt` faz o papel do `composer.json` de forma
  frouxa (faixas abertas demais), e não existe nenhum equivalente do `composer.lock` com as versões exatas
  de todos os pacotes.

- **Correção proposta:** separar as duas peças.
  - `requirements.txt` (papel do `composer.json`): só os pacotes diretos, com faixas seguras baseadas nas
    versões que funcionam hoje no venv, por exemplo `mediapipe~=1.2.3` (aceita só correções da série 1.2).
  - `requirements-lock.txt` (papel do `composer.lock`): gerado com `pip freeze > requirements-lock.txt`,
    com os 30 pacotes exatos. Para reproduzir o ambiente: `pip install -r requirements-lock.txt`.
  - Alternativa a estudar: o **pip-tools** (`pip-compile`) automatiza esse fluxo, como o `composer update`.

## 3. CLAUDE.md cita o MediaPipe 0.10.3x, mas está instalado o 1.2.3
- **O que encontrei:** o CLAUDE.md fala em "MediaPipe 0.10.3x" e o `requirements.txt` pede
  `mediapipe>=0.10.30`, mas o `pip freeze` mostra `mediapipe==1.2.3`. Testei no venv: na 1.2.3 a API antiga
  continua ausente (`hasattr(mp, "solutions")` → `False`) e a API nova existe
  (`vision.PoseLandmarker` → `True`). O protótipo roda normalmente com a 1.2.3.

- **Por que é um problema:** a documentação não descreve o ambiente real. Quem lê o CLAUDE.md (eu, o
  Claude ou um entrevistador) vai consultar a documentação e os exemplos da série 0.10, que pode ter
  diferenças em relação à 1.x, e vai achar que o projeto foi testado com uma versão que não é a instalada.

- **Causa:** é consequência da nota 2. O `>=0.10.30` sem limite superior deixou o pip instalar a versão mais
  nova disponível, e a documentação ficou parada na versão da época em que o protótipo foi escrito.

- **Correção proposta:** primeiro travar a versão (nota 2, ex.: `mediapipe~=1.2.3`) e depois atualizar o
  CLAUDE.md para refletir isso: "a API antiga `mp.solutions.pose` foi removida a partir da 0.10.30; o projeto
  usa a API `PoseLandmarker` (Tasks) e foi testado com o MediaPipe 1.2.3". Regra geral: a fonte da verdade
  sobre versões é o arquivo de dependências; a documentação só aponta para ele.

## 4. pedir_int aceita entrada inválida em silêncio e aceita meta 0
- **O que encontrei:** em `app.py:11-13`, `pedir_int` faz `int(r) if r.isdigit() else padrao`. Testes:
  - `"abc"`, `"-5"`, `"1.5"`, `"15 reps"` → `isdigit()` é `False` → devolve o padrão **sem avisar**. O
    usuário pede 15 repetições digitando `"15 reps"` e treina 10 sem saber.
  - `"0"` → `isdigit()` é `True` → aceita meta 0 (treino que termina antes de começar).
  - `"²"` → `isdigit()` é `True` (caracteres como sobrescritos contam como dígito), mas `int("²")` lança
    `ValueError` → **o programa quebra**. Confirmei no venv.
  - Em `escolher_exercicio`, um número fora da lista devolve `None` e volta ao menu, também sem mensagem.

- **Por que é um problema:** falha silenciosa: o programa faz algo diferente do que o usuário pediu e não
  avisa, o que é pior do que dar erro. E o caso do `"²"` mostra que a validação nem protege contra o crash
  que ela deveria evitar.

- **Causa:** `isdigit()` foi usado como validação, mas ele responde "todos os caracteres são dígitos
  Unicode?", que não é a mesma pergunta que "o `int()` aceita este texto?". Além disso, a função não tem
  noção de valor mínimo: para a câmera, 0 é válido; para a meta, não.

- **Correção proposta:** seguir o idioma Python **EAFP** ("é mais fácil pedir perdão do que permissão"):
  tentar `int(r)` dentro de `try/except ValueError` em vez de verificar antes. Repetir a pergunta até a
  entrada ser válida, com uma mensagem explicando o erro. Adicionar um parâmetro `minimo` (meta: 1,
  câmera: 0), aceitar ENTER vazio como "usar o padrão" e incluir type hints
  (`def pedir_int(msg: str, padrao: int, minimo: int = 0) -> int`). É um bom candidato para os testes da
  Fase 2.

## 5. except Exception em adicionar_exercicio esconde bugs com uma mensagem enganosa
- **O que encontrei:** em `app.py:21-31`, um único `try` envolve tanto o download
  (`referencia.baixar_youtube`) quanto o ramo de arquivo local, e o `except Exception` mostra sempre
  "Erro ao baixar... rode `pip install -U yt-dlp`". De quebra, a variável `titulo` é atribuída e nunca usada.

- **Por que é um problema:** `Exception` captura quase tudo: falta de internet, disco cheio, falta de
  permissão na pasta, e também **bugs do próprio código** (`TypeError`, `KeyError`, `NameError` em
  `referencia.py`). Em todos os casos a mensagem manda atualizar o yt-dlp, o que engana o usuário, e o
  traceback some, então não dá para saber em que linha o erro aconteceu. Um bug real vira "o YouTube
  mudou de novo".

- **Causa:** `try` grande demais e `except` genérico demais. O tratamento foi escrito pensando num único
  erro esperado (o yt-dlp desatualizado), mas captura todos.

- **Correção proposta:**
  - Deixar dentro do `try` só a chamada que pode falhar de forma esperada (`baixar_youtube`).
  - Capturar a exceção específica do yt-dlp (`yt_dlp.utils.DownloadError`), que é o caso em que a dica de
    atualizar faz sentido.
  - Deixar os erros inesperados subirem com o traceback (ou, se quiser uma mensagem amigável, registrar o
    traceback com `logging.exception` antes de mostrá-la).
  - Remover a variável `titulo` não usada, ou usá-la (ex.: como nome sugerido do exercício).
## 6. Enquadramento automático da webcam (Windows Studio Effects) mexe na imagem
- **O que encontrei:** ao me afastar para aparecer de corpo inteiro, a imagem dava zoom e seguia meu
  rosto. Não era o código: o notebook tem NPU (Intel AI Boost) e o Windows Studio Effects aplica
  "Enquadramento automático" antes de o OpenCV receber o quadro.
- **Por que é um problema:** o sistema precisa de câmera fixa. O corte tira pernas/quadril da imagem
  (ângulos viram NaN) e o enquadramento que muda no meio do movimento faz os pontos "saltarem", o que
  vira ruído na série e pode gerar reps falsas.
- **Correção:** desligar em Configurações → Bluetooth e dispositivos → Câmeras → ASUS FHD webcam (ou no
  bloco "Studio Effects" das Configurações rápidas, com a câmera em uso). Requisito registrado no README.
  Lição: entre a câmera e o código existe processamento que não controlo (autofoco, exposição, IA).

## 7. A duração da repetição só mede o trecho fora da zona de repouso
- **O que encontrei (pelos testes da Fase 2):** numa flexão simulada de 2 s, `criar_template` registra
  ~1,3 s. O `ContadorReps` só começa a contar quando o ângulo sai da zona de repouso (30% da faixa).
- **Por que importa:** professor e aluno são medidos do mesmo jeito, então a comparação é justa. Mas o
  "~Xs cada" do menu subestima a duração real, e o modelo não inclui o começo/fim do movimento.
- **Decisão:** manter por enquanto (comportamento documentado no teste
  `test_duracao_conta_so_o_trecho_fora_do_repouso`); reavaliar na Fase 3 com vídeos reais.

## 8. Bug: pular do repouso direto ao extremo virava "parcial"
- **O que encontrei (pelos testes):** se entre duas leituras válidas o ângulo ia do repouso direto ao
  extremo (ex.: corpo some por alguns quadros no fundo da flexão), o contador ia para "saindo" sem checar
  o extremo e, na volta, gerava "parcial" ("faltou amplitude") em vez de contar a rep.
- **Correção aplicada:** no estado "repouso", se o valor já está no extremo, vai direto para "extremo".

## Status das correções (2026-11-28)
| Item | Status |
|---|---|
| 1. OpenCV duplicado | Corrigido: `requirements.txt` usa `opencv-contrib-python`; venv refeito |
| 2. Versões sem trava | Corrigido: `requirements.txt` com `~=`, `requirements-lock.txt` (pip freeze), `requirements-dev.txt` (pytest) |
| 3. CLAUDE.md desatualizado | Corrigido: aponta para a versão travada |
| 4. `pedir_int` | Corrigido: EAFP, mínimo/máximo, repete a pergunta; testado em `tests/test_app.py` |
| 5. `except Exception` | Corrigido: só o download no `try`, captura `DownloadError` |
| 6. Studio Effects | Desligado; documentado no README |
| 7. Duração da rep | Documentado; reavaliar na Fase 3 |
| 8. Repouso → extremo | Corrigido e coberto por teste |
| Extra | Treino com 0 reps/segundos não é mais salvo no histórico |
