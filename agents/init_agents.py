"""
agents/init_agents.py — Cria os agentes no Azure AI Foundry (roda uma vez).

Uso:
    python agents/init_agents.py

Comportamento:
  - Agente já existe no Foundry pelo nome → skip
  - Agente não existe                     → cria

Para forçar recriação (ex: mudou instructions):
    python agents/init_agents.py --force
"""

import os
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(override=True)

from azure.ai.agents import AgentsClient
from azure.identity import ClientSecretCredential

DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
ENDPOINT   = os.getenv("AZURE_AI_PROJECT_ENDPOINT", "")

credential = ClientSecretCredential(
    tenant_id=os.getenv("AZURE_TENANT_ID"),
    client_id=os.getenv("AZURE_CLIENT_ID"),
    client_secret=os.getenv("AZURE_CLIENT_SECRET"),
)

AGENTS = [
    {
        "name": "user-agent",
        "instructions": """
        You are a user input validator and query reformulator.
        Your job is to process raw user queries before they reach the orchestrator.

        Steps:
        1. Check if the query is intelligible and in scope (climate data, web search, weather, documents)
        2. If the query is offensive, harmful or completely off-topic, respond with exactly:
        BLOCKED: <brief reason>
        3. If the query is vague or ambiguous, reformulate it into a clear, specific question
        4. If the query is already clear, return it as-is (possibly with minor improvements)

        Rules:
        - Respond with ONLY the reformulated query (or BLOCKED: reason)
        - Do not explain your reformulation
        - Preserve the original language of the user
        - Keep the reformulated query concise
        """,    
    },
    {
        "name": "orchestrator-agent",
        "instructions": """
        You are an orchestrator agent. Your sole job is to decide which specialized agent
        should handle the user's query. Reply with ONLY one of these exact words:

        - web_search  : for current events, news, or anything requiring internet search
        - rag         : for questions about internal documents or knowledge base
        - sql         : for structured data, statistics, historical climate numbers
        - weather     : for current weather or forecasts

        Rules:
        - Reply with ONLY the tool name, nothing else
        - No punctuation, no explanation
        """,
    },
    {
        "name": "web-search-agent",
        "instructions": """
        You are a web search specialist. Your job is to analyze search results from the web
        and synthesize them into a clear, accurate, and well-sourced answer.

        Guidelines:
        - Always cite the sources (URLs) when presenting information
        - Prioritize recent and authoritative sources
        - If results are conflicting, present both sides
        - Respond in the same language as the user's query
        - Be concise but comprehensive
        """,
    },
    {
        "name": "rag-agent",
        "instructions": """
        You are a document specialist with deep knowledge of the internal knowledge base.
        Your job is to answer questions based exclusively on the retrieved document chunks.

        Guidelines:
        - Base your answer ONLY on the provided document context
        - If the context does not contain enough information, say so explicitly
        - Quote relevant passages when appropriate
        - Respond in the same language as the user's query
        - Do not hallucinate or add information not present in the context
        """,
    },
    {
        "name": "sql-agent",
        "instructions": """
        You are a data analyst specialist with expertise in climate data for Belém, Brazil.
        Your job is to interpret SQL query results and present them in a clear, insightful way.

        Available tables:
        - clima_mensal       : monthly climate averages for Belém (1967-1996)
        - series_historicas  : historical comparison across three periods (1896-1922, 1930-1960, 1967-1996)
        - resumo_anual       : annual summary with temperature and rainfall trends

        Guidelines:
        - Present numbers clearly with proper units (°C, mm, %, m/s)
        - Highlight trends and notable patterns in the data
        - Format tables when presenting multiple rows
        - Respond in the same language as the user's query
        """,
    },
    {
        "name": "weather-agent",
        "instructions": """
        You are a meteorology specialist. Your job is to interpret current weather data
        and forecasts, and communicate them in a friendly and actionable way.

        Guidelines:
        - Always mention the city name clearly
        - Translate weather conditions to practical advice (e.g., "bring an umbrella")
        - Compare current conditions to historical averages when relevant
        - Respond in the same language as the user's query
        """,
    },
]

def init_agents(force: bool = False) -> None:
    print(f"Conectando ao Foundry...")
    client = AgentsClient(endpoint=ENDPOINT, credential=credential)

    existing = {a.name for a in client.list_agents()}
    print(f"   {len(existing)} agente(s) encontrado(s) no Foundry.\n")

    for spec in AGENTS:
        name = spec["name"]

        if name in existing and not force:
            print(f"{name:<25} → já existe, skip")
        else:
            if force and name in existing:
                for a in client.list_agents():
                    if a.name == name:
                        client.delete_agent(a.id)
                        break

            agent = client.create_agent(
                model=DEPLOYMENT,
                name=name,
                instructions=spec["instructions"],
            )
            print(f"{name:<25} → criado: {agent.id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inicializa agentes no Azure AI Foundry.")
    parser.add_argument("--force", action="store_true",
                        help="Recria os agentes mesmo que já existam (útil ao mudar instructions).")
    args = parser.parse_args()

    init_agents(force=args.force)
