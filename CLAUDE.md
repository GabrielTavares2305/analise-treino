# Projeto: Treino Fora da Água (correção de exercícios pela webcam)

## O que é este projeto
Um programa que transforma **aulas de exercícios do YouTube** em exercícios que eu posso fazer em
frente à webcam. O sistema compara meu movimento com o do professor e diz se estou fazendo corretamente.
A motivação é real: comecei natação e preciso fazer exercícios fora da água, mas faço sozinho,
por vídeo, e ninguém corrige minha postura.

## Quem sou eu
- Trabalho com **PHP e Python**. Neste projeto, Python cuida da visão computacional e PHP (Laravel)
  cuidará do sistema web (histórico, painel, planos de treino).
- Visão computacional é **nova para mim**: explique os conceitos (pose estimation, landmarks,
  ângulos, séries temporais) sem assumir conhecimento prévio.
- Prefiro explicações detalhadas: quero saber **por que** estou executando cada ação.
- Este projeto também é meu **portfólio**. Quero entender cada decisão a ponto de explicá-la numa entrevista.

## Como você (Claude) deve me ajudar

> **Modo de trabalho (decidido em 2026-11-28):**
> - **Etapa 1 (Python, Fases 1–4):** o Claude escreve o código, roda os testes automatizados e me
>   entrega um resumo curto do que mudou e por quê, mais uma **lista do que eu preciso testar com a
>   webcam** (o que só um corpo real na câmera valida). As regras 2, 5 e 8 abaixo não se aplicam ao
>   Python; a regra 3 vale de forma resumida.
> - **Etapa 2 em diante (Laravel e web):** voltam todas as regras abaixo: eu escrevo, o Claude guia.

1. **Explique antes de fazer.** Antes de qualquer código ou comando, explique o conceito envolvido,
   por que ele existe e qual problema resolve.
2. **Me deixe escrever o código.** Por padrão, me guie com instruções e dicas. Só escreva o código
   completo quando eu pedir explicitamente (ex.: "pode escrever").
3. **Comandos (pip, artisan, git):** sempre mostre o comando, explique cada parte/flag e, depois de
   rodar, explique o que mudou ou o que cada arquivo gerado faz.
4. **Revise meu código** apontando o jeito idiomático (PEP 8 e type hints no Python; convenções do
   Laravel, Eloquent e Form Requests no PHP), explicando o porquê de cada sugestão.
5. **Erros:** ao aparecer um erro, me ensine a ler a mensagem/traceback e me deixe tentar corrigir
   primeiro antes de dar a solução.
6. **Documentação:** indique a seção da documentação oficial relacionada
   (MediaPipe: https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker ;
   OpenCV: https://docs.opencv.org ; Laravel: https://laravel.com/docs).
7. **Versão:** confira as versões em `requirements.txt` / `pip show` (e em `composer.json` na parte PHP)
   antes de explicar algo que mudou entre versões. **Atenção:** a API antiga `mp.solutions.pose` foi
   **removida** a partir do MediaPipe 0.10.30; este projeto usa a API `PoseLandmarker` (Tasks) e foi
   testado com a versão travada em `requirements.txt` (MediaPipe 1.2.x, Python 3.14). Não sugira
   código de tutoriais antigos.
8. **Um passo de cada vez.** Não implemente várias coisas de uma vez; termine um passo, confirme que
   entendi, e só então siga.
9. Responda sempre em **português**.

## Arquitetura atual (protótipo Python)
| Arquivo | Responsabilidade |
|---|---|
| `app.py` | Menu no terminal |
| `pose.py` | Detecção de pose (MediaPipe), cálculo de ângulos, desenho do esqueleto |
| `analise.py` | Lógica pura: contagem de repetições, modelo do professor, nota. **Sem câmera/tela.** |
| `referencia.py` | Download do YouTube (yt-dlp), marcação do trecho, extração do modelo |
| `treino.py` | Sessão de treino com webcam |
| `exercicios/` | Um `.json` (modelo) + `.mp4` (clipe) por exercício |

> O protótipo inicial foi gerado com ajuda do Claude. A **Fase 1** existe justamente para eu ler,
> entender e assumir esse código antes de evoluí-lo.

## Decisões do projeto
- **Python para visão, PHP para o sistema.** Cada linguagem no que faz melhor.
- **`analise.py` não importa OpenCV nem webcam.** Lógica pura = testável com dados simulados.
  Manter essa separação.
- **Processamento local.** O vídeo da webcam **nunca sai do computador**. Para o servidor só vão
  resultados (exercício, reps, nota, data). Na versão web futura, a detecção roda no navegador
  (MediaPipe JS), não no servidor.
- **Comparação por ângulos 2D** de 8 articulações (cotovelos, ombros, quadris, joelhos).
  Limitação conhecida: depende do ângulo da câmera ser parecido com o do professor.
- **Ângulo principal = o que mais se move** no vídeo; ele conta as repetições (máquina de estados
  com histerese de 30%).
- **Isométricos** (prancha, superman): detectados quando nada se move mais que 20°; contam
  segundos com nota ≥ 70.
- **Espelho:** a comparação testa lado normal e lado trocado (esq↔dir) e fica com o melhor.
- **Nota:** `100 − 1,5 × erro médio − max(0, pior erro − 15)`. O segundo termo impede que um erro
  grande (quadril caído) se dilua na média.
- **Nomes no código:** o protótipo está em português. Ao começar a parte PHP, decidir comigo um
  padrão (Laravel segue nomes em inglês) e registrar aqui.

## Segurança, privacidade e saúde
- Imagens da webcam e vídeos baixados **não vão para o Git** (ver `.gitignore`) nem para servidores.
- Vídeos do YouTube: apenas uso pessoal. Não redistribuir os clipes.
- Na parte web: validar dados recebidos (Form Requests), autenticação por token na API, chaves no `.env`.
- O sistema **não é fisioterapeuta**: a nota indica semelhança com o professor, não se o exercício é
  seguro para mim. Textos devem orientar a parar em caso de dor. Não sugerir cargas ou volumes
  como recomendação médica.

## Fases do projeto

**Regra:** seguir as fases NA ORDEM. Se eu pedir algo de uma fase futura, me lembre do plano e
explique o que falta. Dentro de cada fase, dividir em passos pequenos e fazer um de cada vez.

### Etapa 1: Protótipo Python (AGORA)
- [ ] **Fase 1:** Rodar e entender o protótipo: venv, instalar, cadastrar um exercício real, treinar,
      ler cada módulo e anotar problemas. *(venv, OpenCV, MediaPipe Tasks, NumPy)*
- [ ] **Fase 2:** Testes automatizados de `analise.py` com dados simulados. *(pytest, fixtures)*
- [ ] **Fase 3:** Calibração com exercícios reais da natação: gravar vídeos meus fazendo certo e
      errado e medir se a nota separa os dois; ajustar limiares/tolerâncias por exercício.
      *(conjunto de teste, métricas)*
- [ ] **Fase 4:** Melhorias de uso: texto com acento na tela (Pillow), aviso por voz da dica,
      sessão com vários exercícios em sequência. *(refatoração, type hints)*

### Etapa 2: Sistema em PHP / Laravel
- [ ] **Fase 5:** API Laravel que recebe o resultado de cada treino (substitui o `historico.csv`).
      *(rotas de API, Sanctum/token, Form Requests, migrations, Eloquent)*
- [ ] **Fase 6:** Integração Python → API (`requests`), com fila local se estiver offline.
      *(integração entre sistemas, tratamento de erros)*
- [ ] **Fase 7:** Painel web com evolução (gráficos por exercício, nota média, frequência semanal).
      *(Blade/Livewire, consultas agregadas)*
- [ ] **Fase 8:** Planos de treino montados no painel e baixados pelo app Python. *(relacionamentos)*

### Etapa 3: Web e IA (DEPOIS das Etapas 1 e 2)
- [ ] **Fase 9:** Versão no navegador: portar `analise.py` para JavaScript com MediaPipe JS,
      servida pelo Laravel. *(getUserMedia, Tasks Vision JS)*
- [ ] **Fase 10:** Resumo da semana em linguagem natural via API de LLM. *(prompts, saída em JSON,
      custos)*. A IA explica os dados; não inventa recomendação de saúde.

## Comandos úteis
- `python -m venv venv` e ativar: `venv\Scripts\activate` (Windows) / `source venv/bin/activate`
- `pip install -r requirements.txt`: instala dependências
- `python app.py`: abre o menu
- `pytest`: roda os testes (a partir da Fase 2)
- `pip install -U yt-dlp`: quando o download do YouTube quebrar
