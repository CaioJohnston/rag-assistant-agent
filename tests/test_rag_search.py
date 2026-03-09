"""
tests/test_rag_search.py — Testes unitários da tool Azure AI Search (RAG).
"""

from unittest.mock import patch, MagicMock
from tools.rag_search import AzureRAGTool, RAGSearchInput, RAGSearchResult, DocumentChunk


def _make_tool() -> AzureRAGTool:
    """Instancia AzureRAGTool com credenciais falsas (sem I/O real)."""
    with patch("tools.rag_search.SearchClient"), \
         patch("tools.rag_search.AzureOpenAI"):
        tool = AzureRAGTool()
    return tool


def test_rag_returns_typed_result():
    """run() deve retornar RAGSearchResult com lista de DocumentChunk."""
    tool = _make_tool()

    mock_results = [
        {"content": "LangGraph é um framework...", "source": "doc1.pdf",
         "title": "doc1", "@search.score": 0.95},
        {"content": "Agentes RAG combinam...", "source": "doc2.pdf",
         "title": "doc2", "@search.score": 0.88},
    ]

    tool.search_client.search = MagicMock(return_value=iter(mock_results))
    tool._embed = MagicMock(return_value=[0.0] * 1536)

    result = tool.run(RAGSearchInput(query="o que é LangGraph?"))

    assert isinstance(result, RAGSearchResult)
    assert len(result.chunks) == 2
    assert isinstance(result.chunks[0], DocumentChunk)
    assert result.chunks[0].content == "LangGraph é um framework..."
    assert result.chunks[0].source == "doc1.pdf"
    assert result.chunks[0].score == 0.95


def test_rag_empty_results():
    """run() deve retornar RAGSearchResult com lista vazia se não houver resultados."""
    tool = _make_tool()

    tool.search_client.search = MagicMock(return_value=iter([]))
    tool._embed = MagicMock(return_value=[0.0] * 1536)

    result = tool.run(RAGSearchInput(query="pergunta sem resposta"))

    assert isinstance(result, RAGSearchResult)
    assert result.chunks == []

    # __str__ retorna mensagem amigavel
    assert "Nenhum documento" in str(result)


def test_rag_respects_k():
    """O parâmetro k do RAGSearchInput deve ser passado para a query vetorial."""
    tool = _make_tool()
    tool._embed = MagicMock(return_value=[0.0] * 1536)
    tool.search_client.search = MagicMock(return_value=iter([]))

    tool.run(RAGSearchInput(query="teste k", k=3))

    call_kwargs = tool.search_client.search.call_args
    vector_queries = call_kwargs.kwargs.get("vector_queries", [])
    assert vector_queries[0].k_nearest_neighbors == 3
