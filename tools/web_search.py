"""
tools/web_search.py — Busca no Google via Serper API.

Entrada : query (str), k (int)
Saída   : List[Dict] com title, link, snippet
"""

import os
import requests
from typing import List, Dict
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()


class SerperSearchTool:
    """
    Wrapper sobre a Serper API (Google Search).
    Entrada : query (str), k (int) — número de resultados
    Saída   : List[Dict] com title, link, snippet
    """

    def __init__(self, k: int = 5):
        self.k = k
        self.api_key = os.getenv("SERPAPI_API_KEY")
        if not self.api_key:
            raise ValueError("SERPAPI_API_KEY não encontrada no .env")
        self.url = "https://google.serper.dev/search"

    def run(self, query: str) -> List[Dict]:
        response = requests.post(
            self.url,
            json={"q": query},
            headers={
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        response.raise_for_status()

        organic = response.json().get("organic", [])[: self.k]

        return [
            {
                "title": r.get("title"),
                "link": r.get("link"),
                "snippet": r.get("snippet"),
            }
            for r in organic
        ]


# Instância pronta para uso nos nós
web_search_tool = SerperSearchTool(k=5)


@tool
def web_search(query: str) -> str:
    """
    Realiza busca no Google via Serper e retorna os top resultados formatados.
    Use para perguntas sobre eventos recentes, fatos, notícias ou qualquer
    informação que exija busca na internet.
    """
    results = web_search_tool.run(query)
    if not results:
        return "Nenhum resultado encontrado."

    return "\n\n".join(
        f"**{r['title']}**\n{r['snippet']}\n🔗 {r['link']}"
        for r in results
    )
