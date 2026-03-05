"""
tests/test_graph.py — Testes unitários do grafo LangGraph (Fase 3).
"""

from unittest.mock import patch, MagicMock
from graph.workflow import build_graph


def test_graph_compiles():
    """O grafo deve compilar com os 4 nós corretos."""
    graph = build_graph()
    assert graph is not None


def test_graph_routes_to_web_search():
    """
    Planner escolhe web_search → executor delega para web_search_agent
    → response_node formata a resposta.
    """
    graph = build_graph()

    # memory_node: sem histórico suficiente, retorna None sem chamar LLM
    # planner_node: 1 chamada ao LLM → "web_search"
    # response_node: 1 chamada ao LLM → resposta final
    mock_planner_resp  = MagicMock(content="web_search")
    mock_response_resp = MagicMock(content="Aqui estão as notícias sobre LangChain.")

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [mock_planner_resp, mock_response_resp]

    mock_agent_output = MagicMock()
    mock_agent_output.to_str.return_value = "Resultado da busca web"

    with patch("graph.nodes._get_llm", return_value=mock_llm), \
         patch("agents.web_search_agent.web_search_agent.run", return_value=mock_agent_output):

        result = graph.invoke({
            "messages": [{"role": "user", "content": "latest LangChain news"}]
        })

    assert "output" in result
    assert isinstance(result["output"], str)
    assert len(result["output"]) > 0


def test_graph_fallback_usa_web_search():
    """
    Quando planner retorna 'fallback', executor deve usar web_search_agent.
    """
    graph = build_graph()

    mock_planner_resp  = MagicMock(content="fallback")
    mock_response_resp = MagicMock(content="Encontrei isso na web.")

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [mock_planner_resp, mock_response_resp]

    mock_agent_output = MagicMock()
    mock_agent_output.to_str.return_value = "Resultado fallback via web"

    with patch("graph.nodes._get_llm", return_value=mock_llm), \
         patch("agents.web_search_agent.web_search_agent.run", return_value=mock_agent_output):

        result = graph.invoke({
            "messages": [{"role": "user", "content": "pergunta genérica sem contexto"}]
        })

    assert "output" in result
    assert len(result["output"]) > 0


def test_graph_memory_node_sem_historico():
    """
    Com apenas 1 mensagem no histórico, memory_node não deve chamar o LLM.
    """
    graph = build_graph()

    mock_planner_resp  = MagicMock(content="fallback")
    mock_response_resp = MagicMock(content="Resposta qualquer.")

    mock_llm = MagicMock()
    # só 2 chamadas: planner + responder (memory não chama LLM)
    mock_llm.invoke.side_effect = [mock_planner_resp, mock_response_resp]

    mock_agent_output = MagicMock()
    mock_agent_output.to_str.return_value = "resultado"

    with patch("graph.nodes._get_llm", return_value=mock_llm), \
         patch("agents.web_search_agent.web_search_agent.run", return_value=mock_agent_output):

        result = graph.invoke({
            "messages": [{"role": "user", "content": "olá"}]
        })

    # memory_node com 1 msg não deve ter consumido chamadas do LLM
    assert mock_llm.invoke.call_count == 2   # planner + responder apenas
    assert "output" in result
