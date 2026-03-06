"""
agents/specialized_agents.py — Agentes especializados com Function Calling via Foundry.

Cada agente define _get_tool_functions() com a função Python que o Foundry pode chamar.
O SDK executa automaticamente o tool_call quando o Foundry decide usar a tool.
"""

from agents.base_agent_class import BaseFoundryAgent


# funções Python expostas ao Foundry via Function Calling
# docstrings são obrigatórias — o Foundry as usa para decidir quando chamar cada função

def search_web(query: str) -> str:
    """
    Search the web for current information, news, or real-time data.
    Use this when the user asks about recent events or anything requiring internet search.

    :param query: The search query string.
    :return: Search results with titles, snippets and source URLs.
    """
    from tools.web_search import SerperSearchTool
    results = SerperSearchTool().run(query)
    if not isinstance(results, list):
        return str(results)
    lines = [f"• {r.get('title','')}\n  {r.get('snippet','')}\n  {r.get('link','')}" for r in results]
    return "\n\n".join(lines) if lines else "Nenhum resultado encontrado."


def search_documents(query: str) -> str:
    """
    Search the internal knowledge base and documents using semantic similarity.
    Use this when the user asks about internal documents, PDFs or the knowledge base.

    :param query: The search query string.
    :return: Relevant document chunks with source information.
    """
    from tools.rag_search import AzureRAGTool
    return str(AzureRAGTool().run(query))


def query_climate_database(question: str) -> str:
    """
    Query the PostgreSQL climate database for Belém, Brazil using natural language.
    Use this for questions about temperature, rainfall, humidity or historical climate statistics.

    :param question: The question in natural language about climate data.
    :return: Query results with climate statistics.
    """
    from tools.sql_query import SQLQueryTool
    return str(SQLQueryTool().run(question))


def get_weather(city: str) -> str:
    """
    Get current weather conditions and forecast for a city.
    Use this when the user asks about weather or forecast for any location.

    :param city: City name, optionally with country code (e.g. 'Belém,BR', 'São Paulo').
    :return: Current weather and 5-day forecast.
    """
    from tools.weather import OpenWeatherTool
    return str(OpenWeatherTool().run(city))


def _extract_city(query: str) -> str:
    """Extrai nome da cidade da query. Fallback para Belém,BR."""
    triggers = ["em ", "para ", "de ", "no ", "na ", "in ", "for "]
    query_lower = query.lower()
    for trigger in triggers:
        idx = query_lower.find(trigger)
        if idx != -1:
            candidate = query[idx + len(trigger):].strip().split("?")[0].split(".")[0].strip()
            if candidate and len(candidate) > 2:
                return candidate
    return "Belém,BR"


class WebSearchAgent(BaseFoundryAgent):
    NAME = "web-search-agent"
    INSTRUCTIONS = """
    You are a web search specialist. Search the web using the search_web function
    and synthesize results into a clear, well-sourced answer.
    Always cite URLs. Respond in the same language as the user's query.
    """

    def _get_tool_functions(self) -> set:
        return {search_web}


class RAGAgent(BaseFoundryAgent):
    NAME = "rag-agent"
    INSTRUCTIONS = """
    You are a document specialist. Search the knowledge base using search_documents
    and answer based exclusively on the retrieved context.
    If context is insufficient, say so. Respond in the same language as the user's query.
    """

    def _get_tool_functions(self) -> set:
        return {search_documents}


class SQLAgent(BaseFoundryAgent):
    NAME = "sql-agent"
    INSTRUCTIONS = """
    You are a climate data analyst for Belém, Brazil. Use query_climate_database
    to fetch data and present results clearly with proper units (°C, mm, %).
    Respond in the same language as the user's query.
    """

    def _get_tool_functions(self) -> set:
        return {query_climate_database}


class WeatherAgent(BaseFoundryAgent):
    NAME = "weather-agent"
    INSTRUCTIONS = """
    You are a meteorology specialist. Use get_weather to fetch current conditions
    and forecasts. Give practical advice and use emojis.
    Respond in the same language as the user's query.
    """

    def run(self, query: str) -> str:
        # injeta a cidade na query antes de passar ao Foundry
        city = _extract_city(query)
        return super().run(f"{query} [city: {city}]")

    def _get_tool_functions(self) -> set:
        return {get_weather}


class OrchestratorAgent(BaseFoundryAgent):
    """
    Decide qual agente especializado deve responder e delega.
    Não usa tools — apenas roteia com base na query.
    """
    NAME = "orchestrator-agent"
    INSTRUCTIONS = """
    You are an orchestrator agent. Decide which specialized agent handles the query.
    Reply with ONLY one word — no punctuation, no explanation:

    - web_search  : current events, news, internet search
    - rag         : internal documents, knowledge base
    - sql         : climate statistics, historical data, database queries
    - weather     : current weather or forecast
    """

    _AGENT_MAP = {
        "web_search": WebSearchAgent,
        "rag":        RAGAgent,
        "sql":        SQLAgent,
        "weather":    WeatherAgent,
    }

    def run(self, query: str) -> str:
        client   = self._get_client()
        agent_id = self._get_agent_id(client)

        thread = client.threads.create()
        client.messages.create(thread_id=thread.id, role="user", content=query)

        from azure.ai.agents.models import RunStatus
        run = client.runs.create_and_process(thread_id=thread.id, agent_id=agent_id)

        if run.status != RunStatus.COMPLETED:
            return f"[orchestrator] Run com status inesperado: {run.status}"

        messages   = list(client.messages.list(thread_id=thread.id))
        agent_msgs = [m for m in messages if m.role == "assistant"]

        if not agent_msgs:
            return "Não foi possível determinar o agente responsável."

        decision = "".join(
            block.text.value for block in agent_msgs[-1].content if hasattr(block, "text")
        ).strip().lower()

        specialized_cls = self._AGENT_MAP.get(decision)
        if not specialized_cls:
            return f"[orchestrator] Decisão '{decision}' não reconhecida."

        return specialized_cls().run(query)
