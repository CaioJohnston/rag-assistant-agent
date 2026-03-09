"""
tests/test_web_search.py — Testes unitários da tool de busca web (Serper).
"""

from unittest.mock import patch, MagicMock
from tools.web_search import SerperSearchTool, WebSearchInput, WebSearchResult, SearchResultItem


def test_serper_returns_typed_result():
    """run() deve retornar WebSearchResult com lista de SearchResultItem."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "organic": [
            {"title": "T1", "link": "https://a.com", "snippet": "S1"},
            {"title": "T2", "link": "https://b.com", "snippet": "S2"},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("tools.web_search.requests.post", return_value=mock_response):
        tool = SerperSearchTool()
        tool.api_key = "fake-key"
        result = tool.run(WebSearchInput(query="LangChain agents"))

    assert isinstance(result, WebSearchResult)
    assert len(result.results) == 2
    assert isinstance(result.results[0], SearchResultItem)
    assert result.results[0].title == "T1"
    assert result.results[0].link == "https://a.com"
    assert result.results[0].snippet == "S1"


def test_serper_respects_k():
    """O parâmetro k do WebSearchInput deve limitar o número de resultados."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "organic": [{"title": f"T{i}", "link": f"https://{i}.com", "snippet": f"S{i}"} for i in range(10)]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("tools.web_search.requests.post", return_value=mock_response):
        tool = SerperSearchTool()
        tool.api_key = "fake-key"
        result = tool.run(WebSearchInput(query="test query", k=3))

    assert isinstance(result, WebSearchResult)
    assert len(result.results) == 3
