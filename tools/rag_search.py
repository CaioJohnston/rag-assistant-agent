"""
tools/rag_search.py — Similarity search no Azure AI Search.

Usa ada-002 (Azure OpenAI) para gerar embeddings da query
e faz busca vetorial no Index do Azure AI Search.

Tier Free: sem semantic ranking — usamos apenas vector search.

Entrada : query (str), k (int)
Saída   : List[Dict] com content, source, score
"""

import os
from typing import List, Dict

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from langchain_core.tools import tool
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()


class AzureRAGTool:
    """
    Wrapper sobre Azure AI Search + Azure OpenAI ada-002.

    Fluxo:
      1. Gera embedding da query via ada-002 (Azure OpenAI / Foundry)
      2. Executa vector search no Index do Azure AI Search
      3. Retorna os k documentos mais similares
    """

    def __init__(self, k: int = 3):
        self.k = k

        self.search_client = SearchClient(
            endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
            index_name=os.getenv("AZURE_SEARCH_INDEX", "rag-index"),
            credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY")),
        )

        self.openai_client = AzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            api_version="2024-05-01-preview",
        )
        self.embedding_deployment = os.getenv(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002"
        )

    def _embed(self, text: str) -> List[float]:
        """Gera embedding via ada-002 no Foundry."""
        response = self.openai_client.embeddings.create(
            input=text,
            model=self.embedding_deployment,
        )
        return response.data[0].embedding

    def run(self, query: str) -> List[Dict]:
        """
        Executa vector search e retorna os k resultados mais relevantes.
        """
        query_vector = self._embed(query)

        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=self.k,
            fields="content_vector",   # campo vetorial no Index
        )

        results = self.search_client.search(
            search_text=None,           # pure vector search (Free tier)
            vector_queries=[vector_query],
            select=["content", "source", "title"],
            top=self.k,
        )

        return [
            {
                "content": r.get("content", ""),
                "source": r.get("source", ""),
                "title": r.get("title", ""),
                "score": r["@search.score"],
            }
            for r in results
        ]


rag_tool = AzureRAGTool(k=3)

@tool
def rag_search(query: str) -> str:
    """
    Busca informações em documentos internos e FAQs via Azure AI Search.
    Use para perguntas sobre conteúdo da base de conhecimento,
    documentos carregados ou informações internas da empresa.
    """
    results = rag_tool.run(query)

    if not results:
        return "Nenhum documento relevante encontrado na base de conhecimento."

    return "\n\n".join(
        f"**{r['title'] or r['source']}**\n{r['content']}\n Fonte: {r['source']}"
        for r in results
    )
