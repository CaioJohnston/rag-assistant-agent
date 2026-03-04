"""
agent.py — Constrói e compila o grafo LangGraph principal.

Fluxo atual:
  [START] → router_node → tool_node → response_node → [END]

Fluxo planejado (fase 4):
  [START] → memory_node → router_node → executor_node → response_node → [END]
                                              ↑ fallback edge → web_search
"""

from langgraph.graph import StateGraph, START, END

from my_agent.utils.state import AgentState
from my_agent.utils.nodes import router_node, tool_node, response_node


def build_graph():
    """
    Constrói e compila o StateGraph do agente.
    Retorna um CompiledGraph pronto para .invoke() ou .stream().
    """
    builder = StateGraph(AgentState)

    # ── Nós ──────────────────────────────────
    builder.add_node("router", router_node)
    builder.add_node("tool", tool_node)
    builder.add_node("response", response_node)

    # ── Edges ─────────────────────────────────
    builder.add_edge(START, "router")
    builder.add_edge("router", "tool")
    builder.add_edge("tool", "response")
    builder.add_edge("response", END)

    return builder.compile()


# Instância global — importada pelo router_agent e pela UI
graph = build_graph()
