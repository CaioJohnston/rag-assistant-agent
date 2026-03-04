"""
nodes.py — Funções de nó do grafo LangGraph.

Cada função recebe o AgentState atual e retorna um dict
com as chaves a serem atualizadas no estado.

Nós implementados:
  - router_node   : decide qual tool usar com base no input do usuário
  - tool_node     : executa a tool escolhida pelo router
  - response_node : formata a resposta final para o usuário

Nós planejados (próximas fases):
  - memory_node   : injeta histórico relevante no contexto [TODO fase 4.4]
"""

from langchain_openai import ChatOpenAI
from my_agent.utils.state import AgentState
from my_agent.utils.tools import web_search_tool

# ─────────────────────────────────────────────
# LLM do router (leve e rápido)
# ─────────────────────────────────────────────

llm_router = ChatOpenAI(model="gpt-4o-mini", temperature=0)


# ─────────────────────────────────────────────
# ROUTER NODE
# ─────────────────────────────────────────────

ROUTER_PROMPT = """
You are a routing agent. Your job is to decide which tool should handle the user query.

Available tools:
- web_search : use for questions about current events, news, people, or anything requiring internet search.
- rag        : use for questions about internal documents, FAQs, or knowledge base content.
- sql        : use for questions about structured data, reports, or database queries.
- weather    : use for questions about weather forecasts or current conditions.

Rules:
- Return ONLY the tool name (one of: web_search, rag, sql, weather).
- If no tool is needed, return: none
- Do not explain. Do not add punctuation.
"""


def router_node(state: AgentState) -> dict:
    """
    Analisa o último input do usuário e decide qual tool acionar.
    Atualiza o campo `tool` no estado.
    """
    last_message = state["messages"][-1]["content"]

    decision = llm_router.invoke([
        {"role": "system", "content": ROUTER_PROMPT},
        {"role": "user", "content": last_message},
    ]).content.strip().lower()

    valid_tools = {"web_search", "rag", "sql", "weather"}
    chosen = decision if decision in valid_tools else None

    return {"tool": chosen}


# ─────────────────────────────────────────────
# TOOL NODE
# ─────────────────────────────────────────────

def tool_node(state: AgentState) -> dict:
    """
    Executa a tool escolhida pelo router_node.
    Atualiza o campo `tool_result` no estado.
    """
    tool = state.get("tool")
    query = state["messages"][-1]["content"]

    if tool == "web_search":
        result = web_search_tool.run(query)
        return {"tool_result": result}

    # Placeholders — serão implementados nas fases 2.2, 2.3 e 2.4
    if tool == "rag":
        return {"tool_result": "[RAG] Ferramenta ainda não implementada."}

    if tool == "sql":
        return {"tool_result": "[SQL] Ferramenta ainda não implementada."}

    if tool == "weather":
        return {"tool_result": "[Weather] Ferramenta ainda não implementada."}

    return {"tool_result": None}


# ─────────────────────────────────────────────
# RESPONSE NODE
# ─────────────────────────────────────────────

llm_responder = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

RESPONDER_PROMPT = """
You are a helpful assistant. Use the tool result below to answer the user's question
in a clear, concise, and friendly way. Always respond in the same language as the user.

Tool result:
{tool_result}
"""


def response_node(state: AgentState) -> dict:
    """
    Usa o tool_result para gerar uma resposta em linguagem natural.
    Atualiza os campos `output` e `messages` no estado.
    """
    tool_result = state.get("tool_result")
    last_message = state["messages"][-1]["content"]

    if not tool_result:
        output = "Não encontrei informações relevantes para sua pergunta."
    else:
        prompt = RESPONDER_PROMPT.format(tool_result=str(tool_result))
        output = llm_responder.invoke([
            {"role": "system", "content": prompt},
            {"role": "user", "content": last_message},
        ]).content.strip()

    return {
        "output": output,
        "messages": [{"role": "assistant", "content": output}],
    }
