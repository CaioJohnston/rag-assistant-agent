# Multi-Agent Assistant

Assistente conversacional projetado para responder perguntas sobre o clima de Belém, PA. Baseado em múltiplos agentes orquestrados via **Azure AI Foundry**, com interface em **Streamlit** e suporte a quatro fontes de dados distintas: busca na web, base vetorial, banco de dados e previsão do tempo.

---

## Sumário

- [Visão geral da arquitetura](#visao-geral-da-arquitetura)
- [Agentes e responsabilidades](#agentes-e-responsabilidades)
- [Pipeline de execução](#pipeline-de-execucao)
- [Fontes de dados e tools](#fontes-de-dados-e-tools)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Pré-requisitos](#pre-requisitos)
- [Configuração do ambiente](#configuracao-do-ambiente)
- [Inicialização dos agentes no Foundry](#inicializacao-dos-agentes-no-foundry)
- [Ingestão de documentos na base vetorial](#ingestao-de-documentos-na-base-vetorial)
- [Subindo com Docker](#subindo-com-docker)
- [Rodando os testes](#rodando-os-testes)
- [Avaliação automatizada com RAGAS](#avaliacao-automatizada-com-ragas)
- [Decisões técnicas e trade-offs](#decisoes-tecnicas-e-trade-offs)
- [Segurança](#seguranca)
- [Observabilidade](#observabilidade)

---

## Visão geral da arquitetura

O sistema adota o padrão **Plan-and-Execute** com loop de refinamento e **thread persistente**. Em vez de um agente único com todas as responsabilidades, o trabalho é dividido entre dois agentes com papéis bem definidos e orquestrados por código Python.

```
Streamlit UI
     |
     v
router_agent.run_agent_with_debug()
     |
     v
[1] UserAgent           -- valida e reformula a query do usuario
     |
     v
[2] OrchestratorAgent   -- seleciona e executa tools (ate 4 por resposta)
     |                     Function Calling via Azure AI Foundry SDK
     |                     Thread persistente: iteracoes 2-3 reutilizam a mesma
     |                     thread do Foundry, o modelo ve o historico completo
     v
[3] UserAgent.validate()  -- avalia a resposta: "ok" ou "insufficient"
     |
     +-- ok          --> resposta final entregue ao usuario
     |
     +-- insufficient --> injeta feedback na mesma thread e volta para [2] (max 3x)
```

Toda a orquestração vive em Python. O Azure AI Foundry hospeda os agentes (modelo + instructions) e executa o loop de Function Calling. Nenhuma conexão entre agentes é configurada no portal (isso é responsabilidade do `router_agent.py`).

<img width="1471" height="801" alt="architecture" src="docs\architecture.png" />

---

## Agentes e responsabilidades

### UserAgent (`user-agent`)

Opera em dois modos detectados por prefixo de input:

**Modo 1 — validacao de entrada (sem prefixo)**

- Verifica se a query é inteligível e está no escopo do sistema
- Bloqueia queries ofensivas ou completamente fora de escopo com `BLOCKED: <motivo>`
- Reformula queries vagas ou ambíguas em perguntas claras e específicas

**Modo 2 — revisao de resposta (prefixo `REVIEW:`)**

- Avalia se o rascunho da resposta responde completamente à query
- Verifica se fontes estão citadas (URL, nome do documento, nome da tabela, OpenWeatherMap)
- Retorna JSON estruturado: `{"status": "ok"|"insufficient", "response": "...", "feedback": "..."}`
- O campo `feedback` é injetado como mensagem na thread existente do OrchestratorAgent

### OrchestratorAgent (`orchestrator-agent`)

Agente central com acesso direto a todas as 4 tools via Function Calling. Decide quais tools chamar, pode chamar múltiplas em sequência (máximo 4 por resposta), e sintetiza os resultados em uma resposta única com fontes citadas.

Regras de seleção de tool embutidas nas instructions:

- `sql_query` para dados históricos de Belém (médias, séries, tendências)
- `get_weather` para condições atuais e previsão
- `search_documents` para documentos internos e base vetorial
- `search_web` para conhecimento geral, notícias e afins

---

## Pipeline de execução

```
query do usuario
      |
      v
UserAgent.run(query)
      |
      +-- BLOCKED --> encerra, retorna mensagem de bloqueio
      |
      v
query validada / reformulada
      |
      v
OrchestratorAgent criado (instancia unica para todas as iteracoes)
thread_id = None  (sera criado na primeira iteracao)
      |
      v
loop (max 3 iteracoes):
      |
      +-- iteracao 1: envia query, Foundry cria thread nova
      |               thread_id retornado e guardado
      |
      +-- iteracao 2+: envia mensagem de feedback na MESMA thread
      |                modelo ve historico e chama tools que faltavam
      |
      v
   OrchestratorAgent.run_with_debug(mensagem, thread_id=thread_id)
      |
      v
   UserAgent.validate(query_original, draft)
      |
      +-- "ok"          --> resposta final, sai do loop
      +-- "insufficient"--> prepara mensagem de feedback, proxima iteracao
      +-- max iteracoes --> usa ultima resposta disponivel
      |
      v
resposta final + debug logs
```

---

## Fontes de dados e tools

| Tool                 | Classe               | Fonte                                                          |
| -------------------- | -------------------- | -------------------------------------------------------------- |
| `get_weather`      | `OpenWeatherTool`  | OpenWeatherMap API                                             |
| `sql_query`        | `SQLQueryTool`     | Aspectos Climáticos de Belém nos Últimos Cem Anos - Embrapa |
| `search_documents` | `AzureRAGTool`     | Aspectos Climáticos de Belém nos Últimos Cem Anos - Embrapa |
| `search_web`       | `SerperSearchTool` | Serper API                                                     |

### Banco de dados climáticos (PostgreSQL)

Três tabelas com dados históricos de Belém:

- `clima_mensal`: médias mensais por período (temperatura, precipitação, umidade, insolação)
- `series_historicas`: séries diárias e mensais de longo prazo
- `resumo_anual`: síntese por período histórico (1896-1922, 1930-1960, 1967-1996)

---

## Estrutura do projeto

```
agents/
  base_agent_class.py      -- BaseFoundryAgent com thread persistente
  user_agent.py            -- UserAgent dual-mode com validate()
  orchestrator_agent.py    -- OrchestratorAgent + 4 tool functions
  router_agent.py          -- pipeline com loop e thread persistente
  init_agents.py           -- cria user-agent e orchestrator-agent no Foundry

app/
  config.py                -- configurações centralizadas da aplicação
  Dockerfile

db/
  init.sql                 -- schema e dados climáticos do PostgreSQL

docs/
  architecture.puml        -- diagrama PlantUML
  architecture.png         -- diagrama renderizado

graph/                     -- implementação LangGraph (não utilizada na versão final)
  nodes.py
  state.py
  workflow.py

tools/
  weather.py               -- OpenWeatherTool
  sql_query.py             -- SQLQueryTool (NL para SQL via LLM)
  rag_search.py            -- AzureRAGTool (busca vetorial)
  web_search.py            -- SerperSearchTool

ui/
  app.py                   -- Streamlit com debug panel JSON

tests/
  test_weather.py          -- testes unitários da tool de clima
  test_sql_query.py        -- testes unitários da tool SQL
  test_rag_search.py       -- testes unitários da tool RAG
  test_web_search.py       -- testes unitários da tool de busca
  test_e2e_pipeline.py     -- 6 testes E2E do pipeline completo
  test_ragas_eval.py       -- avaliação automatizada com RAGAS

vector_db/
  ingest.py                -- indexação de documentos no Azure AI Search

docker-compose.yml
requirements.txt
.env.example
langgraph.json
pytest.ini
README.md
```

---

## Pré-requisitos

- Docker e Docker Compose
- Conta Azure com:
  - Azure AI Foundry (projeto criado)
  - Azure OpenAI (deployment `gpt-4o` e `text-embedding-ada-002`)
  - Azure AI Search (índice criado)
  - Service Principal com role `Azure AI User` no Foundry
- SerpAPI key
- OpenWeatherMap API key

---

## Configuração do ambiente

Copie `.env.example` para `.env` e preencha:

```env
# Azure Service Principal
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=

# Azure AI Foundry
AZURE_AI_PROJECT_ENDPOINT=https://<seu-hub>.services.ai.azure.com/api/projects/<seu-projeto>

# Azure OpenAI
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_ENDPOINT=https://<seu-recurso>.openai.azure.com
AZURE_OPENAI_KEY=
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002

# Azure AI Search
AZURE_SEARCH_ENDPOINT=https://<seu-service>.search.windows.net
AZURE_SEARCH_KEY=
AZURE_SEARCH_INDEX=rag-index

# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=ragdb
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# APIs externas
SERPAPI_API_KEY=
OPENWEATHER_API_KEY=

# Streamlit
STREAMLIT_PORT=8501
```

Para criar o Service Principal via CLI:

```bash
az ad sp create-for-rbac \
  --name "sp-multi-agent-dev" \
  --role contributor \
  --scopes /subscriptions/<subscription-id>
```

Após criar, adicione a role `Azure AI User` no portal do Foundry para o Service Principal gerado.

---

## Inicialização dos agentes no Foundry

Os agentes precisam existir no Foundry antes de rodar a aplicação. Esse passo é executado uma única vez (ou com `--force` ao mudar instructions):

```bash
# dentro do container
docker compose exec app python agents/init_agents.py

# fora do container (com ambiente virtual ativo)
python agents/init_agents.py

# forcando recriacao (ao atualizar instructions)
python agents/init_agents.py --force
```

O script cria os agentes `user-agent` e `orchestrator-agent`. Agentes já existentes são ignorados por padrão.

---

## Ingestão de documentos na base vetorial

Para alimentar a base vetorial com PDFs ou arquivos de texto:

```bash
# ingere todos os documentos em docs/
docker compose exec app python vector_db/ingest.py --docs docs/

# ingere um arquivo especifico
docker compose exec app python vector_db/ingest.py --docs caminho/para/arquivo.pdf
```

O script fragmenta os documentos em chunks, gera embeddings com `text-embedding-ada-002` e indexa no Azure AI Search. Documentos já indexados são ignorados por padrão.

---

## Subindo com Docker

```bash
git clone https://github.com/CaioJohnston/rag-assistant-agent
cd rag-assistant-agent

cp .env.example .env
# edite o .env com suas credenciais

docker compose up --build
```

A interface estará disponível em: `http://localhost:8501`

O Docker Compose sobe dois serviços:

- `postgres`: PostgreSQL 16 com o schema e dados climaticos carregados automaticamente via `db/init.sql`
- `app`: aplicação Streamlit com todo o código dos agentes

Para subir em background:

```bash
docker compose up --build -d
docker compose logs -f app   # acompanhar logs JSON estruturados
```

Para parar e remover volumes:

```bash
docker compose down -v
```

---

## Rodando os testes

```bash
# todos os testes (unitarios + E2E)
pytest tests/ -v

# suite especifica
pytest tests/test_weather.py -v
pytest tests/test_sql_query.py -v
pytest tests/test_web_search.py -v
pytest tests/test_rag_search.py -v
pytest tests/test_e2e_pipeline.py -v
```

Os testes unitários cobrem cada tool de forma isolada com mocks nos clientes externos. Os testes E2E cobrem o pipeline completo com o Foundry SDK mockado.

---

## Avaliação automatizada com RAGAS

O projeto inclui avaliação automatizada usando **RAGAS** (Retrieval Augmented Generation Assessment), que mede a qualidade das respostas do pipeline em 4 métricas:

| Métrica              | O que mede                                    | Threshold |
| --------------------- | --------------------------------------------- | --------- |
| `answer_relevancy`  | A resposta responde a pergunta?               | 0.7       |
| `faithfulness`      | A resposta é fiel aos contextos recuperados? | 0.7       |
| `context_recall`    | Os contextos cobrem o ground truth?           | 0.5       |
| `context_precision` | Os contextos são precisos para a pergunta?   | 0.5       |

### Instalação

```bash
pip install ragas>=0.2.0
```

### Rodando

```bash
# modo simulado — pipeline mockado, apenas o RAGAS avaliador consome tokens
pytest tests/test_ragas_eval.py -v -s

# modo real — pipeline completo contra as APIs (requer Docker up)
pytest tests/test_ragas_eval.py -v -s --eval-real
```

O modo simulado usa respostas e contextos pré-definidos no dataset para avaliar rapidamente sem custo de pipeline. O modo real executa cada query no pipeline completo e usa os contextos reais retornados pelas tools.

O dataset cobre 5 cenários: `get_weather`, `query_climate_database` (2 casos), `search_web` e multi-tool (weather + SQL na mesma resposta).

### Exemplo de output

```
[weather-01]
  answer_relevancy       = 0.937  (threshold: 0.7)  [PASS]
  faithfulness           = 1.000  (threshold: 0.7)  [PASS]
  context_recall         = 1.000  (threshold: 0.5)  [PASS]
  context_precision      = 1.000  (threshold: 0.5)  [PASS]

=== RAGAS EVALUATION SUMMARY ===
Metric                        Mean      Min      Max
----------------------------------------------------
answer_relevancy             0.927    0.918    0.938
faithfulness                 0.933    0.667    1.000
context_recall               0.933    0.667    1.000
context_precision            0.800    0.000    1.000
```

---

## Decisões técnicas e trade-offs

### Azure AI Foundry em vez de LangGraph

A escolha foi feita pelos seguintes motivos:

- Os agentes vivem no Foundry como entidades persistentes com nome e instructions fixas, desacoplando configuração de execução. Mudar o comportamento de um agente não exige redeploy da aplicação — basta rodar `init_agents.py --force`.
- O Function Calling nativo do Foundry SDK substitui o `ExecutorNode` do LangGraph sem adicionar overhead de grafo para um pipeline linear.
- A integração com Azure OpenAI, Azure AI Search e Azure Monitor é nativa, sem adapters.

Trade-off: o pipeline é menos flexível para grafos não-lineares complexos. Para workflows com múltiplos ramos paralelos ou ciclos condicionais mais elaborados, LangGraph seria mais apropriado.

### Thread persistente no loop de refinamento

Nas versões anteriores, cada iteração do loop criava uma thread nova no Foundry. O modelo não tinha memória das tentativas anteriores e tendia a repetir o mesmo comportamento mesmo após receber feedback.

A solução foi manter uma instância única do `OrchestratorAgent` para todo o pipeline e reutilizar a mesma thread entre iterações. O feedback do `UserAgent` é injetado como mensagem de usuário na thread existente. O modelo vê o histórico completo e decide naturalmente quais tools ainda precisam ser chamadas para complementar a resposta.

Trade-off: threads persistentes consomem storage no Foundry e precisam ser gerenciadas (limpas periodicamente em produção). O custo é justificado pela melhora significativa na qualidade das respostas multi-tool.

### Azure AI Search em vez de Chroma

- Azure AI Search oferece escalabilidade gerenciada, autenticação via Service Principal (sem chaves hardcoded) e integração nativa com o restante da stack Azure.
- Trade-off: requer provisionamento na nuvem, o que aumenta a complexidade do setup inicial comparado ao Chroma local.

### OrchestratorAgent com todas as tools

- O OrchestratorAgent tem acesso direto a todas as 4 tools e decide a sequência de chamadas sozinho.
- Isso elimina uma camada de indireção e permite que o modelo chame múltiplas tools em uma única resposta.
- Trade-off: as instructions do OrchestratorAgent ficaram mais longas e precisam de regras explícitas para evitar confusão entre tools similares (ex: `query_climate_database` vs `search_web` para dados históricos de Belém).

### NL para SQL via LLM

A tool `sql_query` usa um LLM para converter a pergunta em linguagem natural para SQL, em vez de queries fixas. Isso oferece flexibilidade e segurança para perguntas variadas sobre os dados.

Trade-off de segurança: queries geradas por LLM podem ser imprevisíveis. A mitigação atual usa `sqlglot` para parse e validação antes da execução, e o usuário do banco tem permissões somente de leitura.

---

## Segurança

**Credenciais**

- Todas as chaves e secrets são lidas de variáveis de ambiente via `python-dotenv`.
- O `.env` está no `.gitignore` e nunca deve ser commitado.
- A autenticação no Azure usa Service Principal com `ClientSecretCredential`.

**PostgreSQL**

- O usuário do banco tem permissão apenas de `SELECT` nas tabelas de dados.
- Queries geradas pelo LLM passam por validação com `sqlglot` antes da execução para rejeitar DDL e DML.
- Parâmetros são passados via placeholders do psycopg2, nunca por concatenação de string.

**Rate limiting**

- OpenWeatherMap: o plano gratuito permite 60 chamadas/minuto.
- SerperAPI: 2.500 buscas/mês no plano gratuito.

**Azure AI Search**

- O índice usa autenticação por chave de API armazenada em variável de ambiente.
- Pode substituir por autenticação via Managed Identity ou Service Principal.

---

## Observabilidade

**Logs estruturados (JSON)**

Cada etapa do pipeline emite uma linha JSON para o stdout do container:

```json
{"timestamp": "2026-03-08T22:09:10", "level": "INFO", "logger": "multi_agent.pipeline", "message": "Input recebido: '...'", "pipeline_step": "PIPELINE START"}
{"timestamp": "2026-03-08T22:09:32", "level": "INFO", "logger": "multi_agent.pipeline", "message": "1 tool(s) executada(s)", "pipeline_step": "orchestrator-agent", "elapsed_s": 13.876, "attempt": 1, "thread_id": "thread_K6Jc..."}
{"timestamp": "2026-03-08T22:09:32", "level": "INFO", "logger": "multi_agent.pipeline", "message": "Input: \"{'city': 'Belem,BR'}\"", "pipeline_step": "TOOL CALL", "tool": "get_weather"}
{"timestamp": "2026-03-08T22:09:37", "level": "INFO", "logger": "multi_agent.pipeline", "message": "Pipeline concluido", "pipeline_step": "PIPELINE END", "elapsed_s": 26.1}
```

Para acompanhar em tempo real:

```bash
docker compose logs -f app
```

**Debug panel na UI**

O debug panel na interface Streamlit exibe o log completo de cada execução, incluindo iterações do loop, tools chamadas com input/output, tempo por etapa, thread ID reutilizada e status da validação.

**OpenTelemetry**

O projeto inclui `opentelemetry-sdk` e `opentelemetry-exporter-otlp-proto-grpc` no `requirements.txt`, prontos para integração com Azure Monitor ou qualquer backend compatível com OTLP.
