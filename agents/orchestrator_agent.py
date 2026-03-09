"""
agents\orchestrator_agent.py — Agentes especializados com Function Calling via Foundry.

Cada agente define _get_tool_functions() com a funcao Python que o Foundry pode chamar.
O SDK executa automaticamente o tool_call quando o Foundry decide usar a tool.

OrchestratorAgent agora tem acesso a TODAS as tools diretamente.
Pode chamar multiplas tools por resposta — o Foundry decide a sequencia.
"""

from agents.base_agent_class import BaseFoundryAgent


def search_web(query: str) -> str:
    """
    Search the web for current information, news, real-time data, or general knowledge.
    Use this when the user asks about recent events, news, or general concepts (e.g. "what is RAG?").
    Do NOT use for historical climate statistics or database queries — use query_climate_database instead.
    Do NOT use for current weather conditions — use get_weather instead.

    :param query: The search query string.
    :return: Search results with titles, snippets and source URLs.
    """
    from tools.web_search import SerperSearchTool, WebSearchInput
    result = SerperSearchTool().run(WebSearchInput(query=query))
    if not result.results:
        return "Nenhum resultado encontrado."
    lines = [
        f"TITLE: {r.title}\nSNIPPET: {r.snippet}\nSOURCE_URL: {r.link}"
        for r in result.results
    ]
    return "\n\n".join(lines)


def search_documents(query: str) -> str:
    """
    Search the internal knowledge base and documents using semantic similarity.
    Use this when the user asks about internal documents, PDFs or the knowledge base.
    Always cite the DOCUMENT name in the response.

    :param query: The search query string.
    :return: Relevant document chunks with document name and source path.
    """
    from tools.rag_search import AzureRAGTool, RAGSearchInput
    result = AzureRAGTool().run(RAGSearchInput(query=query))
    if not result.chunks:
        return "Nenhum documento encontrado."
    lines = [
        f"DOCUMENT: {c.title or c.source}\n"
        f"CONTENT: {c.content}\n"
        f"SOURCE_PATH: {c.source}\n"
        f"SCORE: {c.score:.2f}"
        for c in result.chunks
    ]
    return "\n\n".join(lines)


def query_climate_database(question: str) -> str:
    """
    Query the PostgreSQL climate database for historical climate data of Belem, Brazil.
    Use ONLY for historical statistics, monthly averages, period comparisons, trends.
    Do NOT use for current weather or forecast — use get_weather instead.
    Always cite the TABLE NAME used (clima_mensal, series_historicas or resumo_anual).

    Available tables:
    - clima_mensal      : monthly averages for Belem (1967-1996)
    - series_historicas : comparisons across periods 1896-1922, 1930-1960, 1967-1996
    - resumo_anual      : annual trends and century-long summaries

    :param question: Natural language question about historical climate data.
    :return: SQL query executed, table used, and query results.
    """
    from tools.sql_query import SQLQueryTool, SQLQueryInput
    return str(SQLQueryTool().run(SQLQueryInput(question=question)))


def get_weather(city: str) -> str:
    """
    Get CURRENT weather conditions and upcoming forecast for a city.
    Use ONLY for current temperature, today's conditions, upcoming days forecast.
    Do NOT use for historical averages or statistics — use query_climate_database instead.
    Always cite OpenWeatherMap as the source in the response.

    :param city: City name with optional country code (e.g. 'Belem,BR', 'Sao Paulo,BR').
    :return: Current weather and 5-day forecast from OpenWeatherMap.
    """
    from tools.weather import OpenWeatherTool, WeatherInput
    return str(OpenWeatherTool().run(WeatherInput(city=city)))


def _extract_city(query: str) -> str:
    """Extrai nome da cidade da query. Fallback para Belem,BR."""
    triggers = ["em ", "para ", "de ", "no ", "na ", "in ", "for "]
    query_lower = query.lower()
    for trigger in triggers:
        idx = query_lower.find(trigger)
        if idx != -1:
            candidate = query[idx + len(trigger):].strip().split("?")[0].split(".")[0].strip()
            if candidate and len(candidate) > 2:
                return candidate
    return "Belem,BR"


# todas as tools disponíveis para o OrchestratorAgent
ALL_TOOL_FUNCTIONS = {search_web, search_documents, query_climate_database, get_weather}


class OrchestratorAgent(BaseFoundryAgent):
    """
    Orquestrador com acesso direto a todas as tools.
    Decide quais chamar (pode ser mais de uma) e executa em sequencia.
    """
    NAME = "orchestrator-agent"
    INSTRUCTIONS = """
    You are an intelligent orchestrator with direct access to 4 tools.
    Your job is to answer the user's query by calling ALL necessary tools and synthesizing the results.

    CRITICAL RULE — READ BEFORE ANYTHING ELSE:
    You must NEVER use your internal knowledge to answer factual questions.
    Every factual claim in your response MUST come from a tool result.
    If the query has two aspects, call two tools. If it has three, call three.
    Do not respond until you have called every tool needed to cover all aspects of the query.

    TOOL SELECTION — follow these rules strictly:

    query_climate_database → historical climate data only:
    - Monthly averages, period comparisons, trends, statistics for Belem
    - Keywords: media, historico, periodo, tabela, dados, 1896, 1967, comparacao
    - NEVER use your training knowledge for historical averages — always call this tool

    get_weather → current conditions only:
    - Current temperature, today's weather, upcoming forecast
    - Keywords: hoje, agora, amanha, previsao, vai chover, temperatura atual
    - NEVER use historical averages from this tool

    search_documents → internal knowledge base:
    - Questions about internal PDFs, research papers, methodology

    search_web → everything else:
    - Current events, news, general knowledge (what is X, how does Y work)
    - Use also when no other tool is clearly more appropriate

    MULTI-TOOL EXECUTION — mandatory:
    - Before responding, identify ALL distinct aspects of the query
    - Each aspect requires its own tool call
    - Example: "temperatura atual vs media historica de outubro"
        → aspect 1: temperatura atual → call get_weather
        → aspect 2: media historica de outubro → call query_climate_database
        → only then synthesize and respond
    - Example: "o que e El Nino e como afeta Belem historicamente"
        → aspect 1: o que e El Nino → call search_web
        → aspect 2: dados historicos de Belem → call query_climate_database
        → only then synthesize and respond
    - Do NOT respond after the first tool call if the query has more aspects
    - Maximum 4 tool calls per response

    MANDATORY TOOL USAGE:
    - Always use at least 1 tool unless the query is a simple greeting or identity question
    (e.g. "oi", "ola", "quem e voce", "tudo bem", "obrigado")
    - For general knowledge questions, always use search_web
    - NEVER answer from memory for questions about weather, climate data, or documents

    SOURCE CITATION — mandatory in every response:
    - search_web: cite SOURCE_URL for each fact
    - search_documents: cite DOCUMENT name for each excerpt
    - query_climate_database: cite TABLE NAME used
    - get_weather: cite "Fonte: OpenWeatherMap"

    Respond in the same language as the user's query.
    """

    def _get_tool_functions(self) -> set:
        return ALL_TOOL_FUNCTIONS

    def run(self, query: str) -> str:
        response, _ = self.run_with_debug(query)
        return response

    # run_with_debug herdado de BaseFoundryAgent — wrapa as tools para debug automaticamente