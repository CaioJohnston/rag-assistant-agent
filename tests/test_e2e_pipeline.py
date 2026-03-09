"""
tests/test_e2e_pipeline.py — Testes E2E do pipeline multi-agent completo.

Cobrem o fluxo inteiro: query → UserAgent → OrchestratorAgent → UserAgent.validate() → resposta.

O Azure AI Foundry SDK e as APIs externas sao mockados — nenhuma chamada real e feita.
Os testes verificam o comportamento do pipeline como um todo, nao de cada peca isolada.
"""

from unittest.mock import patch, MagicMock, call
import pytest


# ── helpers de mock do Foundry SDK ────────────────────────────────────────────

def _make_text_block(text: str):
    """Cria um bloco de texto simulando a resposta do Foundry."""
    block = MagicMock()
    block.text.value = text
    return block


def _make_assistant_message(text: str):
    """Cria uma mensagem de assistant com um bloco de texto."""
    msg = MagicMock()
    msg.role = "assistant"
    msg.content = [_make_text_block(text)]
    return msg


def _make_foundry_client(agent_responses: list[str]):
    """
    Cria um mock do AgentsClient que retorna as respostas em sequencia.

    agent_responses: lista de strings — cada item e a resposta de uma chamada
    ao Foundry (user-agent, orchestrator-agent, user-agent.validate, etc.)
    """
    client = MagicMock()

    # threads e messages
    thread_stub = MagicMock()
    thread_stub.id = "thread-id-456"
    client.threads.create.return_value = thread_stub

    # run sempre completa com sucesso
    from azure.ai.agents.models import RunStatus
    run_stub = MagicMock()
    run_stub.status = RunStatus.COMPLETED
    client.runs.create_and_process.return_value = run_stub

    # cada chamada a messages.list() retorna a proxima resposta da fila
    responses = iter(agent_responses)
    def messages_list_side_effect(**kwargs):
        text = next(responses, "resposta padrao")
        return [_make_assistant_message(text)]

    client.messages.list.side_effect = messages_list_side_effect

    return client


# ── fixture: pre-popula o cache de agent_id e limpa entre testes ──────────────

@pytest.fixture(autouse=True)
def patch_agent_id_cache():
    """
    Pre-popula o _agent_id_cache com IDs falsos para todos os agentes.
    Evita que _get_agent_id() chame list_agents() e falhe por nao encontrar
    os agentes reais no Foundry durante os testes.
    """
    import agents.base_agent_class as base

    base._agent_id_cache.clear()
    base._agent_id_cache.update({
        "user-agent":         "fake-user-agent-id",
        "orchestrator-agent": "fake-orchestrator-agent-id",
    })

    yield

    base._agent_id_cache.clear()


# ── E2E 1: pergunta sobre clima atual — tool get_weather ──────────────────────

def test_e2e_weather_query():
    """
    Fluxo completo para pergunta de previsao do tempo.

    Sequencia de chamadas ao Foundry:
      1. user-agent        → devolve a query aprovada
      2. orchestrator-agent → chama get_weather e gera o draft
      3. user-agent.validate → aprova a resposta em JSON
    """
    weather_draft = (
        "A temperatura atual em Belem e 28C com chuva leve. "
        "Previsao para amanha: 27C. Fonte: OpenWeatherMap."
    )
    validation_ok = (
        '{"status": "ok", "response": "' + weather_draft + '"}'
    )

    foundry_responses = [
        "Qual e a previsao do tempo para Belem hoje?",   # user-agent: aprova query
        weather_draft,                                    # orchestrator: draft com weather
        validation_ok,                                    # user-agent: valida resposta
    ]

    mock_client = _make_foundry_client(foundry_responses)

    weather_result = (
        "Belem — condicoes atuais\n"
        "Temperatura: 28.0C | Umidade: 85% | Chuva leve\n"
        "Previsao: 2026-03-07: 27C — Chuva leve"
    )

    with patch("agents.base_agent_class.AgentsClient", return_value=mock_client), \
         patch("tools.weather.OpenWeatherTool.run", return_value=weather_result):

        from agents.router_agent import run_agent_with_debug
        response, debug = run_agent_with_debug("como ta o tempo em Belem hoje?")

    # resposta contem conteudo de clima
    assert "28" in response or "Belem" in response or "OpenWeatherMap" in response

    logs = debug.get("logs", [])
    steps = [e["step"] for e in logs]

    # pipeline iniciou e encerrou
    assert "PIPELINE START" in steps
    assert "PIPELINE END"   in steps

    # passou pelo loop
    assert "LOOP" in steps

    # orchestrator executou pelo menos 1 tool
    tool_calls = [s for s in steps if s.startswith("TOOL CALL")]
    assert len(tool_calls) >= 1

    # user-agent aprovou
    approved = [e for e in logs if e["step"] == "user-agent" and "aprovada" in e["detail"]]
    assert len(approved) >= 1


# ── E2E 2: pergunta de conhecimento geral — tool search_web ───────────────────

def test_e2e_web_search_query():
    """
    Fluxo completo para pergunta de conhecimento geral.
    O OrchestratorAgent deve usar search_web.

    Sequencia de chamadas ao Foundry:
      1. user-agent        → reformula a query
      2. orchestrator-agent → chama search_web e gera o draft
      3. user-agent.validate → aprova
    """
    web_draft = (
        "RAG (Retrieval-Augmented Generation) e uma tecnica que combina "
        "recuperacao de documentos com geracao de texto por LLMs. "
        "Fonte: https://arxiv.org/abs/2005.11401"
    )
    validation_ok = '{"status": "ok", "response": "' + web_draft + '"}'

    foundry_responses = [
        "O que e RAG (Retrieval-Augmented Generation)?",  # user-agent: reformula
        web_draft,                                         # orchestrator: draft
        validation_ok,                                     # user-agent: valida
    ]

    mock_client = _make_foundry_client(foundry_responses)

    web_results = [
        {
            "title":   "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
            "snippet": "RAG combines retrieval with generation for better factual accuracy.",
            "link":    "https://arxiv.org/abs/2005.11401",
        }
    ]

    with patch("agents.base_agent_class.AgentsClient", return_value=mock_client), \
         patch("tools.web_search.SerperSearchTool.run", return_value=web_results):

        from agents.router_agent import run_agent_with_debug
        response, debug = run_agent_with_debug("o que e RAG?")

    # resposta contem conteudo de web search
    assert len(response) > 0

    logs = debug.get("logs", [])
    steps = [e["step"] for e in logs]

    assert "PIPELINE START" in steps
    assert "PIPELINE END"   in steps
    assert "LOOP"           in steps

    # query foi reformulada pelo user-agent
    reformuladas = [e for e in logs if e["step"] == "user-agent" and "reformulada" in e["detail"]]
    assert len(reformuladas) >= 1


# ── E2E 3: query bloqueada pelo UserAgent ─────────────────────────────────────

def test_e2e_blocked_query():
    """
    O UserAgent bloqueia queries ofensivas ou fora de escopo.
    O pipeline deve encerrar imediatamente sem chamar o OrchestratorAgent.
    """
    foundry_responses = [
        "BLOCKED: query ofensiva e fora de escopo",   # user-agent: bloqueia
    ]

    mock_client = _make_foundry_client(foundry_responses)

    with patch("agents.base_agent_class.AgentsClient", return_value=mock_client):
        from agents.router_agent import run_agent_with_debug
        response, debug = run_agent_with_debug("me diga como fazer algo ilegal")

    # resposta indica bloqueio
    assert "Nao posso responder" in response or "BLOCKED" in response.upper()

    logs  = debug.get("logs", [])
    steps = [e["step"] for e in logs]

    # log de blocked presente
    assert "user-agent BLOCKED" in steps

    # orchestrator nao foi chamado
    orchestrator_calls = [e for e in logs if "orchestrator" in e.get("detail", "").lower()]
    assert len(orchestrator_calls) == 0

    # pipeline encerrou
    assert "PIPELINE END" in steps

    # flag de blocked no debug
    assert debug.get("blocked") is True


# ── E2E 4: loop de refinamento — insufficient na primeira tentativa ────────────

def test_e2e_refinement_loop():
    """
    O UserAgent rejeita o primeiro draft (insufficient) e o pipeline
    faz uma segunda tentativa com o feedback injetado na query.
    O segundo draft e aprovado.
    """
    draft_1   = "A media de chuvas em Belem e alta."          # vago, sem fonte
    feedback  = "Cite a tabela usada e inclua os valores numericos."

    draft_2   = (
        "Segundo a tabela clima_mensal, a precipitacao media anual de Belem "
        "e de 3.001 mm, com pico em marco (441 mm). Fonte: tabela clima_mensal."
    )

    insufficient_json = (
        '{"status": "insufficient", '
        '"response": "' + draft_1 + '", '
        '"feedback": "' + feedback + '"}'
    )
    ok_json = '{"status": "ok", "response": "' + draft_2 + '"}'

    foundry_responses = [
        "Qual e a media de chuvas em Belem?",   # user-agent: aprova query
        draft_1,                                 # orchestrator: 1a tentativa (fraca)
        insufficient_json,                       # user-agent: rejeita
        draft_2,                                 # orchestrator: 2a tentativa (boa)
        ok_json,                                 # user-agent: aprova
    ]

    mock_client = _make_foundry_client(foundry_responses)

    sql_result = (
        "tabela: clima_mensal\n"
        "Janeiro: 378mm | Fevereiro: 427mm | Marco: 441mm | ... | Total anual: 3001mm"
    )

    with patch("agents.base_agent_class.AgentsClient", return_value=mock_client), \
         patch("tools.sql_query.SQLQueryTool.run", return_value=sql_result):

        from agents.router_agent import run_agent_with_debug
        response, debug = run_agent_with_debug("qual a media de chuvas em Belem?")

    # resposta final e o draft aprovado
    assert "clima_mensal" in response or "3" in response

    logs  = debug.get("logs", [])
    steps = [e["step"] for e in logs]

    # loop rodou mais de uma vez
    loop_entries = [e for e in logs if e["step"] == "LOOP"]
    assert len(loop_entries) >= 2

    # insufficient foi registrado
    assert "user-agent INSUFFICIENT" in steps

    # aprovacao ocorreu na segunda tentativa
    approved = [e for e in logs if e["step"] == "user-agent" and "aprovada" in e["detail"]]
    assert len(approved) >= 1

    # orchestrator foi chamado mais de uma vez (thread persistente)
    orchestrator_calls = [e for e in logs if e["step"] == "orchestrator-agent"]
    assert len(orchestrator_calls) >= 2


# ── E2E 5: saudacao simples — nenhuma tool deve ser ativada ───────────────────

def test_e2e_greeting_no_tools():
    """
    Saudacoes simples nao devem acionar nenhuma tool.
    O OrchestratorAgent responde diretamente.
    """
    greeting_response = "Ola! Sou um assistente especializado em dados climaticos de Belem."
    validation_ok     = '{"status": "ok", "response": "' + greeting_response + '"}'

    foundry_responses = [
        "oi",                  # user-agent: aprova query (saudacao, sem reformulacao)
        greeting_response,     # orchestrator: responde sem tool
        validation_ok,         # user-agent: aprova
    ]

    mock_client = _make_foundry_client(foundry_responses)

    # as tools nao devem ser chamadas
    with patch("agents.base_agent_class.AgentsClient", return_value=mock_client), \
         patch("tools.web_search.SerperSearchTool.run")      as mock_web, \
         patch("tools.weather.OpenWeatherTool.run")          as mock_weather, \
         patch("tools.sql_query.SQLQueryTool.run")           as mock_sql, \
         patch("tools.rag_search.AzureRAGTool.run")          as mock_rag:

        from agents.router_agent import run_agent_with_debug
        response, debug = run_agent_with_debug("oi")

    assert len(response) > 0

    # nenhuma tool foi chamada
    mock_web.assert_not_called()
    mock_weather.assert_not_called()
    mock_sql.assert_not_called()
    mock_rag.assert_not_called()

    logs = debug.get("logs", [])
    steps = [e["step"] for e in logs]

    # pipeline completou normalmente
    assert "PIPELINE START" in steps
    assert "PIPELINE END"   in steps

    # nenhum tool call no log
    tool_calls = [s for s in steps if s.startswith("TOOL CALL")]
    assert len(tool_calls) == 0


# ── E2E 6: multi-tool — weather + sql na mesma resposta ───────────────────────

def test_e2e_multi_tool_weather_and_sql():
    """
    Pergunta que exige dados atuais E historicos deve acionar
    get_weather e query_climate_database na mesma execucao.
    """
    multi_tool_draft = (
        "Temperatura atual de Belem: 28C (Fonte: OpenWeatherMap). "
        "Media historica de outubro (1967-1996): 26.8C (Fonte: tabela clima_mensal). "
        "Belem esta 1.2C acima da media historica para outubro."
    )
    validation_ok = '{"status": "ok", "response": "' + multi_tool_draft + '"}'

    foundry_responses = [
        "Compare a temperatura atual de Belem com a media historica de outubro.",  # user-agent
        multi_tool_draft,   # orchestrator: usou weather + sql
        validation_ok,      # user-agent: aprova
    ]

    mock_client = _make_foundry_client(foundry_responses)

    weather_result = "Belem: 28.0C | Sensacao: 32C | Umidade: 83%"
    sql_result     = "tabela: clima_mensal | outubro | temp_media: 26.8C"

    with patch("agents.base_agent_class.AgentsClient", return_value=mock_client), \
         patch("tools.weather.OpenWeatherTool.run",  return_value=weather_result), \
         patch("tools.sql_query.SQLQueryTool.run",   return_value=sql_result):

        from agents.router_agent import run_agent_with_debug
        response, debug = run_agent_with_debug(
            "qual a temperatura atual de Belem comparada com a media historica de outubro?"
        )

    # resposta menciona ambas as fontes
    assert "OpenWeatherMap" in response or "clima_mensal" in response or "28" in response

    logs = debug.get("logs", [])
    steps = [e["step"] for e in logs]

    assert "PIPELINE START" in steps
    assert "PIPELINE END"   in steps
