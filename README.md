# 🏊 Treino Fora da Água

**Transforme aulas do YouTube em exercícios com correção de postura pela webcam.**

> 🚧 **Status:** em desenvolvimento ativo (Etapa 1, Fase 1). Este README separa o que já funciona do que está planejado. Veja o [roadmap](#️-roadmap).

---

## 💡 O problema

Comecei a fazer natação e, além das aulas na piscina, preciso fazer exercícios **fora da água** (prancha, flexões, fortalecimento de ombro e core). As aulas que sigo estão no YouTube, mas ninguém corrige minha postura: faço sozinho e não sei se o quadril está caído ou se estou descendo o suficiente.

Apps de exercício com câmera existem, mas só trabalham com exercícios **pré-definidos** por eles. Eu queria usar **as aulas que eu já sigo**.

**O Treino Fora da Água usa o próprio professor do vídeo como referência e me diz, a cada repetição, o quanto estou parecido com ele e o que corrigir.**

---

## 🔍 Como funciona

```
Link da aula no YouTube
      │
      ├─▶ Baixa o vídeo e eu marco o trecho do exercício
      ├─▶ IA de pose (MediaPipe) encontra 33 pontos do corpo do professor
      ├─▶ Calcula 8 ângulos (cotovelos, ombros, quadris, joelhos) quadro a quadro
      ├─▶ Detecta as repetições e cria o "modelo" do movimento ideal
      │
      ▼
Menu de exercícios ──▶ Webcam ──▶ mesmos ângulos em tempo real
      │
      ▼
Contagem de repetições + nota (0-100) + dica: "quadril: 30 graus mais dobrado"
```

### O que já funciona

| Recurso | Como |
|---|---|
| Cadastro a partir do YouTube ou arquivo local | `yt-dlp` + player com atalhos para marcar início e fim |
| Detecção automática do tipo de exercício | Com repetições (flexão, agachamento) ou isométrico (prancha, superman) |
| Contagem de repetições | Máquina de estados com histerese: não conta meia repetição e avisa "faltou amplitude" |
| Nota e dica por repetição | Comparação com o modelo do professor; a articulação mais errada fica vermelha |
| Professor ao lado em loop | Clipe gravado com o esqueleto desenhado |
| Funciona espelhado ou não | Compara lado esquerdo e direito trocados e usa o melhor |
| Histórico | `historico.csv` com data, exercício, repetições/segundos e nota média |

---

## ⚖️ Decisões de projeto

| Decisão | Por quê |
|---|---|
| **O professor do vídeo é a referência** | Não preciso programar regras para cada exercício; qualquer aula vira exercício. |
| **Comparar ângulos, não posições** | Ângulos não dependem da altura da pessoa nem da distância da câmera. |
| **O ângulo que mais se move conta as repetições** | Funciona para exercícios diferentes sem configuração manual. |
| **Histerese (dois limites) na contagem** | Um limite único contaria repetições em dobro quando o ângulo "treme" perto dele. |
| **Nota penaliza o pior erro** | Um quadril caído se diluiria na média das articulações corretas. |
| **Lógica pura separada da câmera (`analise.py`)** | Dá para testar com dados simulados, sem ficar na frente da webcam. |
| **Vídeo nunca sai do computador** | Privacidade: só os resultados (reps, nota) serão enviados ao servidor. |
| **Python para visão, PHP para o sistema** | Cada linguagem no ponto forte: ecossistema de IA no Python, web e dados no Laravel. |

### Limitações conhecidas
- A comparação usa ângulos 2D: a câmera precisa estar **no mesmo ângulo do professor** (de frente ou de lado).
- A nota mede **semelhança com o professor**, não segurança do exercício. Em caso de dor, pare.

---

## 🛠️ Tecnologias

**Em uso:** Python 3.14 · MediaPipe 1.2 (API `PoseLandmarker`) · OpenCV 5.1 (contrib) · NumPy · yt-dlp · pytest

(versões exatas em `requirements-lock.txt`)

**Planejadas:** Laravel · Sanctum · Livewire · MediaPipe JS · API de LLM

---

## 🗺️ Roadmap

### Etapa 1: Protótipo Python
- [ ] **Fase 1**: Rodar e entender o protótipo *(em andamento)*
- [x] **Fase 2**: Testes automatizados da lógica de análise (`pytest`, 51 testes)
- [ ] **Fase 3**: Calibração com vídeos meus fazendo certo × errado
- [ ] **Fase 4**: Texto com acento, aviso por voz, sessões com vários exercícios

### Etapa 2: Sistema em PHP / Laravel
- [ ] **Fase 5**: API que recebe os resultados dos treinos
- [ ] **Fase 6**: Envio automático do Python para a API
- [ ] **Fase 7**: Painel web com evolução
- [ ] **Fase 8**: Planos de treino

### Etapa 3: Web e IA
- [ ] **Fase 9**: Versão no navegador (MediaPipe JS)
- [ ] **Fase 10**: Resumo semanal com LLM

---

## 🧠 Como desenvolvo: IA como tutora, não como atalho

Uso o **Claude Code** como tutor e par de programação, com regras definidas no [`CLAUDE.md`](CLAUDE.md):

- **Explicar antes de fazer**: entendo o conceito antes de escrever o código.
- **Divisão clara do trabalho**: o protótipo Python (visão computacional) é escrito com o Claude, e eu valido na webcam, registro problemas (`NOTAS_FASE1.md`) e decido; a parte Laravel eu escrevo, com a IA revisando.
- **Conferir a versão**: a API do MediaPipe mudou (a antiga `mp.solutions` foi removida), então toda sugestão é conferida contra a versão instalada.
- **Desconfiar e verificar**: quando a IA assume algo que não corresponde ao meu ambiente, corrijo e registro.

---

## 🚀 Como rodar

Pré-requisitos: Python 3.14 e uma webcam **fixa** (desligue enquadramento automático, ex.: Windows Studio Effects).

```bash
git clone https://github.com/SEU-USUARIO/treino-natacao.git
cd treino-natacao

python -m venv venv                # ambiente isolado para as bibliotecas deste projeto
# Windows: venv\Scripts\activate  |  Linux/macOS: source venv/bin/activate
pip install -r requirements.txt    # instala MediaPipe, OpenCV, NumPy e yt-dlp
# reprodução exata do ambiente testado: pip install -r requirements-lock.txt
# desenvolvimento (testes): pip install -r requirements-dev.txt && pytest

python app.py                      # abre o menu (o modelo de IA é baixado na 1ª vez)
```

### Uso
1. **Adicionar exercício**: cole o link da aula. No player: `ESPAÇO` pausa · `A`/`D` ±5 s · `J`/`L` ±1 s · `I` início · `F` fim · `ENTER` confirma.
   - Com repetições: marque pelo menos 2 ou 3 repetições inteiras.
   - Isométricos: marque só o trecho em que o professor segura a posição.
2. **Treinar**: escolha o exercício e a meta. Você tem 5 s para se posicionar com o corpo inteiro na câmera.
3. **Histórico**: veja seus últimos treinos.

### Problemas comuns
| Problema | Solução |
|---|---|
| Erro ao baixar do YouTube | `pip install -U yt-dlp`, ou informe o caminho de um vídeo local |
| Lento | Em `pose.py`, troque `VARIANTE_MODELO = "full"` por `"lite"` |
| "Não encontrei repetições" | Trecho curto ou professor fora do quadro: marque de novo |
| Webcam não abre | Feche outros apps que usam a câmera ou escolha a câmera 1 |
| Imagem dá zoom / segue o rosto | Desligue o "Enquadramento automático": Configurações → Bluetooth e dispositivos → Câmeras (Windows Studio Effects) |

---

## ⚠️ Aviso

Este projeto compara movimentos com um vídeo de referência e **não substitui um profissional de educação física ou fisioterapeuta**. Em caso de dor ou desconforto, pare o exercício. Use os vídeos baixados apenas para treino pessoal.
