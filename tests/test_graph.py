"""
tests/test_graph.py — Testes unitários do grafo LangGraph (pre-Foundry).
"""

from unittest.mock import patch, MagicMock
from graph.workflow import build_graph


def test_graph_compiles():
    graph = build_graph()
    assert graph is not None


def test_graph_routes_to_web_search():
    graph = build_graph()

    mock_router   = MagicMock(content="web_search")
    mock_response = MagicMock(content="Aqui estao as noticias sobre LangChain.")

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [mock_router, mock_response]

    with patch("graph.nodes._get_llm", return_value=mock_llm), \
         patch("tools.web_search.SerperSearchTool.run",
               return_value=[{"title": "T", "link": "https://t.com", "snippet": "S"}]):

        result = graph.invoke({
            "messages": [{"role": "user", "content": "latest LangChain news"}]
        })

    assert "output" in result
    assert len(result["output"]) > 0


def test_graph_routes_to_weather():
    graph = build_graph()

    mock_router   = MagicMock(content="weather")
    mock_response = MagicMock(content="Temperatura: 30C.")

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [mock_router, mock_response]

    with patch("graph.nodes._get_llm", return_value=mock_llm), \
         patch("tools.weather.OpenWeatherTool.run", return_value="Belem: 30C"):

        result = graph.invoke({
            "messages": [{"role": "user", "content": "tempo em Belem"}]
        })

    assert "output" in result
    assert len(result["output"]) > 0


def test_graph_handles_no_tool():
    graph = build_graph()

    mock_router = MagicMock(content="none")

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_router

    with patch("graph.nodes._get_llm", return_value=mock_llm):
        result = graph.invoke({
            "messages": [{"role": "user", "content": "ola"}]
        })

    assert "output" in result