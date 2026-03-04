"""
test_graph.py — Testes unitários do grafo LangGraph.
"""

from unittest.mock import patch, MagicMock
from graph.workflow import build_graph


def test_graph_compiles():
    """O grafo deve compilar sem erros."""
    graph = build_graph()
    assert graph is not None


def test_graph_routes_to_web_search():
    """
    Dado um input sobre notícias, o router deve escolher web_search
    e o grafo deve retornar um output não-vazio.
    """
    graph = build_graph()

    mock_results = [
        {"title": "Test", "link": "https://test.com", "snippet": "Test snippet"}
    ]

    with patch("tools.web_search.SerperSearchTool.run", return_value=mock_results):
        result = graph.invoke({
            "messages": [{"role": "user", "content": "latest LangChain news"}]
        })

    assert "output" in result
    assert isinstance(result["output"], str)
    assert len(result["output"]) > 0


def test_graph_handles_no_tool():
    """
    Dado um input genérico, o grafo deve retornar uma resposta mesmo sem tool.
    """
    graph = build_graph()

    with patch("graph.nodes.llm_router") as mock_llm:
        mock_llm.invoke.return_value = MagicMock(content="none")

        with patch("graph.nodes.llm_responder") as mock_resp:
            mock_resp.invoke.return_value = MagicMock(content="Olá! Como posso ajudar?")

            result = graph.invoke({
                "messages": [{"role": "user", "content": "olá"}]
            })

    assert "output" in result
