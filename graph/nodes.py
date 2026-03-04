"""
graph/nodes.py — Funções de nó do grafo LangGraph.

Lazy imports nas tools que dependem de serviços externos (Azure Search, Postgres)
evitam falhas de conexão no momento do import durante testes locais.
"""

import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from graph.state import AgentState

load_dotenv(override=True)


def _get_llm(temperature: float = 0):
    return AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_KEY"),
        api_version="2024-05-01-preview",
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
        temperature=temperature,
    )


def _extract_content(message) -> str:
    """
    Extrai o texto de uma mensagem independente do formato.
    LangGraph converte dicts em HumanMessage/AIMessage automaticamente,
    então precisamos lidar com ambos os casos.
    """
    if isinstance(message, dict):
        return message.get("content", "")
    return getattr(message, "content", str(message))


# router node

ROUTER_PROMPT = """
You are a routing agent. Decide which tool should handle the user query.

Available tools:
- web_search : current events, news, people, anything requiring internet search
- rag        : internal documents, FAQs, knowledge base, PDF content
- sql        : structured data, statistics, monthly averages, historical comparisons, climate numbers
- weather    : weather forecasts or current conditions

Rules:
- Return ONLY the tool name (one of: web_search, rag, sql, weather)
- If no tool is needed, return: none
- Do not explain. Do not add punctuation.
"""

def router_node(state: AgentState) -> dict:
    last_message = _extract_content(state["messages"][-1])

    decision = _get_llm().invoke([
        {"role": "system", "content": ROUTER_PROMPT},
        {"role": "user",   "content": last_message},
    ]).content.strip().lower()

    valid_tools = {"web_search", "rag", "sql", "weather"}
    chosen = decision if decision in valid_tools else None

    return {"tool": chosen}


# tool node

def tool_node(state: AgentState) -> dict:
    tool  = state.get("tool")
    query = _extract_content(state["messages"][-1])

    if tool == "web_search":
        from tools.web_search import web_search_tool
        return {"tool_result": web_search_tool.run(query)}

    if tool == "rag":
        from tools.rag_search import rag_tool
        return {"tool_result": rag_tool.run(query)}

    if tool == "sql":
        from tools.sql_query import sql_tool
        return {"tool_result": sql_tool.run(query)}

    if tool == "weather":
        return {"tool_result": "[Weather] Ferramenta ainda não implementada."}

    return {"tool_result": None}


# response node

RESPONDER_PROMPT = """
You are a helpful assistant. Use the tool result below to answer the user's question
in a clear, concise and friendly way. Always respond in the same language as the user.

Tool result:
{tool_result}
"""

def response_node(state: AgentState) -> dict:
    tool_result  = state.get("tool_result")
    last_message = _extract_content(state["messages"][-1])

    if not tool_result:
        output = "Não encontrei informações relevantes para sua pergunta."
    else:
        prompt = RESPONDER_PROMPT.format(tool_result=str(tool_result))
        output = _get_llm(temperature=0.3).invoke([
            {"role": "system", "content": prompt},
            {"role": "user",   "content": last_message},
        ]).content.strip()

    return {
        "output":   output,
        "messages": [{"role": "assistant", "content": output}],
    }
