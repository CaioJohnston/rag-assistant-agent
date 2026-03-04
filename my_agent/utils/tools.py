"""
tools.py — Todas as ferramentas do agente ficam aqui.

Cada tool é uma função decorada com @tool do LangChain,
ou uma classe com interface padronizada (entrada tipada, saída tipada).

Tools disponíveis (sendo expandidas nas próximas fases):
  - web_search  : busca no Google via Serper API
  - rag_search  : similarity search no Azure AI Search       [TODO fase 2.2]
  - sql_query   : queries no PostgreSQL via SQLDatabaseToolkit [TODO fase 2.3]
  - weather     : previsão do tempo via OpenWeatherMap        [TODO fase 2.4]
"""

import os
from typing import List, Dict

import requests
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()


# ─────────────────────────────────────────────
# WEB SEARCH — Serper API
# ─────────────────────────────────────────────

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


# ─────────────────────────────────────────────
# Instâncias prontas para uso nos nós
# ─────────────────────────────────────────────

web_search_tool = SerperSearchTool(k=5)


# ─────────────────────────────────────────────
# @tool wrappers — expostos ao LangGraph/LangChain
# ─────────────────────────────────────────────

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


# Lista de todas as tools disponíveis (cresce nas próximas fases)
ALL_TOOLS = [web_search]
