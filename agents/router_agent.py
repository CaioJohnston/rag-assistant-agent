"""
agents/router_agent.py — Ponto de entrada do pipeline multi-agent (Foundry).

Pipeline:
  query → UserAgent → OrchestratorAgent → Agente Especializado → resposta

UserAgent     : valida e reformula a query
OrchestratorAgent : decide qual especialista usar
Especialistas : WebSearchAgent, RAGAgent, SQLAgent, WeatherAgent
"""

import os
from dotenv import load_dotenv

load_dotenv(override=True)


def run_agent(user_input: str) -> str:
    """
    Executa o pipeline completo:
      1. UserAgent valida e reformula a query
      2. Bloqueia se UserAgent retornar BLOCKED
      3. OrchestratorAgent decide e delega ao especialista
    """
    from agents.user_agent import user_agent
    from agents.specialized_agents import OrchestratorAgent

    # etapa 1 — validação e reformulação
    processed_query = user_agent.run(user_input)

    # etapa 2 — bloqueia queries inválidas
    if processed_query.upper().startswith("BLOCKED:"):
        reason = processed_query.split(":", 1)[-1].strip()
        return f"Não posso responder a essa pergunta: {reason}"

    # etapa 3 — orquestração e resposta
    return OrchestratorAgent().run(processed_query)
