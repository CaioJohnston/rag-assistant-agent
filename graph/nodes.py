"""
graph/nodes.py — Funções de nó do grafo LangGraph.

Cada função recebe o AgentState atual e retorna um dict
com as chaves a serem atualizadas no estado.

Nós implementados:
  - router_node   : decide qual tool usar com base no input do usuário
  - tool_node     : executa a tool escolhida pelo router
  - response_node : formata a resposta final para o usuário

Nós planejados:
  - memory_node   : injeta histórico relevante no contexto [TODO fase 4.4]
"""

from langchain_openai import AzureChatOpenAI
from graph.state import AgentState
from tools.web_search import web_search_tool
from tools.rag_search import rag_tool
from tools.sql_query import sql_tool
import os

# LLMs
llm_router = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2024-05-01-preview",
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
    temperature=0,
)

llm_responder = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2024-05-01-preview",
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
    temperature=0.3,
)


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
    last_message = state["messages"][-1]["content"]

    decision = llm_router.invoke([
        {"role": "system", "content": ROUTER_PROMPT},
        {"role": "user",   "content": last_message},
    ]).content.strip().lower()

    valid_tools = {"web_search", "rag", "sql", "weather"}
    chosen = decision if decision in valid_tools else None

    return {"tool": chosen}


# tool node

def tool_node(state: AgentState) -> dict:
    tool    = state.get("tool")
    query   = state["messages"][-1]["content"]

    if tool == "web_search":
        return {"tool_result": web_search_tool.run(query)}

    if tool == "rag":
        return {"tool_result": rag_tool.run(query)}

    if tool == "sql":
        return {"tool_result": sql_tool.run(query)}

    # placeholder — implementado na fase 2.4
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
    last_message = state["messages"][-1]["content"]

    if not tool_result:
        output = "Não encontrei informações relevantes para sua pergunta."
    else:
        prompt = RESPONDER_PROMPT.format(tool_result=str(tool_result))
        output = llm_responder.invoke([
            {"role": "system", "content": prompt},
            {"role": "user",   "content": last_message},
        ]).content.strip()

    return {
        "output":   output,
        "messages": [{"role": "assistant", "content": output}],
    }
