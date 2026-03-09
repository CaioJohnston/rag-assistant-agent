"""
tools/web_search.py — Busca no Google via Serper API.

Entrada : WebSearchInput(query, k)
Saída   : WebSearchResult(results: list[SearchResultItem])
"""

import os
import requests
from dataclasses import dataclass, field
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()


# ── dataclasses de entrada e saída ────────────────────────────────────────────

@dataclass
class WebSearchInput:
    """Entrada tipada para a tool de busca web."""
    query: str
    k: int = 5


@dataclass
class SearchResultItem:
    """Um resultado individual da busca web."""
    title: str = ""
    link: str = ""
    snippet: str = ""


@dataclass
class WebSearchResult:
    """Saída tipada da tool de busca web."""
    results: list[SearchResultItem] = field(default_factory=list)

    def __str__(self) -> str:
        if not self.results:
            return "Nenhum resultado encontrado."
        return "\n\n".join(
            f"**{r.title}**\n{r.snippet}\n🔗 {r.link}"
            for r in self.results
        )


# ── tool class ────────────────────────────────────────────────────────────────

class SerperSearchTool:
    """
    Wrapper sobre a Serper API (Google Search).
    Entrada : WebSearchInput (dataclass com campos query e k)
    Saída   : WebSearchResult (dataclass tipada)
    """

    def __init__(self):
        self.api_key = os.getenv("SERPAPI_API_KEY")
        if not self.api_key:
            raise ValueError("SERPAPI_API_KEY não encontrada no .env")
        self.url = "https://google.serper.dev/search"

    def run(self, input: WebSearchInput) -> WebSearchResult:
        """Executa a busca e retorna WebSearchResult tipado."""
        response = requests.post(
            self.url,
            json={"q": input.query},
            headers={
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        response.raise_for_status()

        organic = response.json().get("organic", [])[:input.k]

        return WebSearchResult(
            results=[
                SearchResultItem(
                    title=r.get("title", ""),
                    link=r.get("link", ""),
                    snippet=r.get("snippet", ""),
                )
                for r in organic
            ]
        )


# Instância pronta para uso nos nós
web_search_tool = SerperSearchTool()


@tool
def web_search(query: str) -> str:
    """
    Realiza busca no Google via Serper e retorna os top resultados formatados.
    Use para perguntas sobre eventos recentes, fatos, notícias ou qualquer
    informação que exija busca na internet.
    """
    return str(web_search_tool.run(WebSearchInput(query=query)))
