"""
tests/test_graph.py — Testes unitários do grafo LangGraph.
"""

from unittest.mock import patch, MagicMock
from graph.workflow import build_graph


def test_graph_compiles():
    """O grafo deve compilar sem erros."""
    graph = build_graph()
    assert graph is not None


def test_graph_routes_to_web_search():
    """
    Router deve escolher web_search e o grafo retornar output não-vazio.
    _get_llm() é chamada duas vezes: uma no router, outra no responder.
    Usamos side_effect com duas instâncias mock distintas.
    """
    graph = build_graph()

    mock_router_llm   = MagicMock()
    mock_router_llm.invoke.return_value = MagicMock(content="web_search")

    mock_responder_llm = MagicMock()
    mock_responder_llm.invoke.return_value = MagicMock(content="Aqui estão as notícias.")

    mock_tool_results = [
        {"title": "Test", "link": "https://test.com", "snippet": "Test snippet"}
    ]

    with patch("graph.nodes._get_llm", side_effect=[mock_router_llm, mock_responder_llm]), \
         patch("tools.web_search.SerperSearchTool.run", return_value=mock_tool_results):

        result = graph.invoke({
            "messages": [{"role": "user", "content": "latest LangChain news"}]
        })

    assert "output" in result
    assert isinstance(result["output"], str)
    assert len(result["output"]) > 0


def test_graph_handles_no_tool():
    """
    Com tool=none, o grafo deve retornar mensagem padrão sem chamar nenhuma tool.
    """
    graph = build_graph()

    mock_router_llm = MagicMock()
    mock_router_llm.invoke.return_value = MagicMock(content="none")

    # responder não é chamado quando tool_result é None
    with patch("graph.nodes._get_llm", side_effect=[mock_router_llm]):
        result = graph.invoke({
            "messages": [{"role": "user", "content": "olá"}]
        })

    assert "output" in result
    assert result["output"] == "Não encontrei informações relevantes para sua pergunta."
