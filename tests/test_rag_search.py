"""
tests/test_rag_search.py — Testes unitários da tool Azure AI Search (RAG).
"""

from unittest.mock import patch, MagicMock
from tools.rag_search import AzureRAGTool


def _make_tool() -> AzureRAGTool:
    """Instancia AzureRAGTool com credenciais falsas (sem I/O real)."""
    with patch("tools.rag_search.SearchClient"), \
         patch("tools.rag_search.AzureOpenAI"):
        tool = AzureRAGTool(k=3)
    return tool


def test_rag_returns_list():
    """run() deve retornar uma lista de dicts com content, source, score."""
    tool = _make_tool()

    mock_results = [
        {"content": "LangGraph é um framework...", "source": "doc1.pdf",
         "title": "doc1", "@search.score": 0.95},
        {"content": "Agentes RAG combinam...", "source": "doc2.pdf",
         "title": "doc2", "@search.score": 0.88},
    ]

    tool.search_client.search = MagicMock(return_value=iter(mock_results))
    tool._embed = MagicMock(return_value=[0.0] * 1536)

    results = tool.run("o que é LangGraph?")

    assert isinstance(results, list)
    assert len(results) == 2
    assert "content" in results[0]
    assert "source" in results[0]
    assert "score" in results[0]


def test_rag_empty_results():
    """run() deve retornar lista vazia se não houver resultados."""
    tool = _make_tool()

    tool.search_client.search = MagicMock(return_value=iter([]))
    tool._embed = MagicMock(return_value=[0.0] * 1536)

    results = tool.run("pergunta sem resposta")

    assert results == []


def test_rag_respects_k():
    """O parâmetro k deve ser passado corretamente para a query vetorial."""
    tool = _make_tool()
    tool._embed = MagicMock(return_value=[0.0] * 1536)
    tool.search_client.search = MagicMock(return_value=iter([]))

    tool.run("teste k")

    call_kwargs = tool.search_client.search.call_args
    vector_queries = call_kwargs.kwargs.get("vector_queries", [])
    assert vector_queries[0].k_nearest_neighbors == 3
