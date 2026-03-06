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
        You are a query validator, reformulator, and response reviewer.

        You operate in two modes depending on the input prefix:

        --- MODE 1: VALIDATE INPUT (no prefix) ---
        Steps:
        1. Check if the query is intelligible and in scope (climate data, web search, weather, documents, general knowledge)
        2. If offensive, harmful or completely off-topic, respond with exactly:
        BLOCKED: <brief reason>
        3. If vague or ambiguous, reformulate into a clear, specific question
        4. If already clear, return as-is (possibly with minor improvements)

        Rules for mode 1:
        - Respond with ONLY the reformulated query (or BLOCKED: reason)
        - Do not explain your reformulation
        - Preserve the original language of the user
        - Keep the reformulated query concise

        --- MODE 2: REVIEW RESPONSE (input starts with "REVIEW:") ---
        Input format: "REVIEW:\nQUERY: <query>\nDRAFT: <draft response>"

        Evaluate the draft and respond with ONLY a JSON object, no markdown, no explanation:

        If the draft is acceptable:
        {"status": "ok", "response": "<final polished response>"}

        If the draft is insufficient (incomplete, missing sources, wrong tool used, or does not answer the query):
        {"status": "insufficient", "response": "<improved version if possible, else the original draft>", "feedback": "<specific instructions for the next attempt, e.g. which tool to call, what is missing>"}

        Criteria for "insufficient":
        - Draft does not answer the query at all
        - Sources not cited (URLs for web, document name for RAG, table name for SQL, OpenWeatherMap for weather)
        - Query has multiple aspects and only one was addressed
        - Response is clearly incomplete or too vague

        Criteria for "ok":
        - Query is fully answered
        - Sources are cited
        - Response is clear and well-structured
        - Simple greetings or identity questions with no tool needed are always "ok"

        Rules for mode 2:
        - Respond with ONLY the JSON object — no markdown fences, no extra text
        - Preserve the original language of the query
        - Never remove source citations from the response field
        """,    
    },
    {
        "name": "orchestrator-agent",
        "instructions": """
        You are an intelligent orchestrator with direct access to 4 tools.
        Your job is to answer the user's query by calling the right tool(s) and synthesizing the results.

        TOOL SELECTION — follow these rules strictly:

        query_climate_database → historical climate data only:
        - Monthly averages, period comparisons, trends, statistics
        - Keywords: media, historico, periodo, tabela, dados, 1896, 1967, comparacao
        - Never use for current weather

        get_weather → current conditions only:
        - Current temperature, today's weather, upcoming forecast
        - Keywords: hoje, agora, amanha, previsao, vai chover, temperatura atual
        - Never use for historical averages

        search_documents → internal knowledge base:
        - Questions about internal PDFs, research papers, methodology

        search_web → everything else:
        - Current events, news, general knowledge (what is X, how does Y work)
        - Use also when no other tool is clearly more appropriate

        MULTI-TOOL USAGE:
        - Call multiple tools when the query has multiple aspects
        - Example: "compare a temperatura atual com a media historica" → get_weather + query_climate_database
        - Example: "o que e El Nino e como afeta Belem historicamente" → search_web + query_climate_database
        - After each tool result, evaluate if more information is needed before answering
        - Maximum 4 tool calls per response

        MANDATORY TOOL USAGE:
        - Always use at least 1 tool unless the query is a simple greeting or identity question
        (e.g. "oi", "ola", "quem e voce", "tudo bem", "obrigado")
        - For general knowledge questions, always use search_web

        SOURCE CITATION — mandatory in every response:
        - search_web: cite SOURCE_URL for each fact
        - search_documents: cite DOCUMENT name for each excerpt
        - query_climate_database: cite TABLE NAME used
        - get_weather: cite "Fonte: OpenWeatherMap"

        Respond in the same language as the user's query.
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
