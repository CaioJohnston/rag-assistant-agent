"""
test_web_search.py — Testes unitários da tool de busca web (Serper).
"""

from unittest.mock import patch, MagicMock
from tools.web_search import SerperSearchTool


def test_serper_returns_list():
    """search deve retornar uma lista de dicts com title, link, snippet."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "organic": [
            {"title": "T1", "link": "https://a.com", "snippet": "S1"},
            {"title": "T2", "link": "https://b.com", "snippet": "S2"},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("my_agent.utils.tools.requests.post", return_value=mock_response):
        tool = SerperSearchTool(k=5)
        tool.api_key = "fake-key"
        results = tool.run("LangChain agents")

    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0]["title"] == "T1"
    assert "link" in results[0]
    assert "snippet" in results[0]


def test_serper_respects_k():
    """O parâmetro k deve limitar o número de resultados."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "organic": [{"title": f"T{i}", "link": f"https://{i}.com", "snippet": f"S{i}"} for i in range(10)]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("my_agent.utils.tools.requests.post", return_value=mock_response):
        tool = SerperSearchTool(k=3)
        tool.api_key = "fake-key"
        results = tool.run("test query")

    assert len(results) == 3


if __name__ == "__main__":
    # Execução manual com API key real (para debug)
    tool = SerperSearchTool(k=3)
    results = tool.run("LangChain agents")
    print(f"Resultados: {len(results)}")
    for r in results:
        print(r["title"], "—", r["link"])
