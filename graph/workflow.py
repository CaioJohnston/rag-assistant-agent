from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from graph.state import AgentState
from tools.web_search import SerpAPIETool


web_tool = SerpAPIETool()

llm_router = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0
)

# -----------------------------
# ROUTER NODE
# -----------------------------
def router_node(state: AgentState):
    ROUTER_SYSTEM_PROMPT = """
    You are a routing agent.

    Your job is to decide which tool should handle the user query.

    Available tools:
    - web_search: use for questions about current events, facts, people, or anything that requires internet search.

    Rules:
    - Return ONLY the tool name.
    - If no tool is needed, return: none
    - Do not explain.
    """

    user_input = state["input"]

    messages = [
        {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]

    decision = llm_router.invoke(messages).content.strip().lower()

    if decision == "web_search":
        return {"tool": "web_search"}

    return {"tool": None}


# -----------------------------
# TOOL NODE
# -----------------------------
def tool_node(state: AgentState):
    if state.get("tool") == "web_search":
        results = web_tool.search_web(state["input"])
        return {"tool_result": results}

    return {"tool_result": None}


# -----------------------------
# RESPONSE NODE
# -----------------------------
def response_node(state: AgentState):
    results = state.get("tool_result")

    if results:
        text = "\n\n".join(
            f"{r['title']}\n{r['snippet']}\n{r['link']}"
            for r in results[:3]
        )
        return {"output": text}

    return {"output": "Não encontrei resultados relevantes."}


# -----------------------------
# BUILD GRAPH
# -----------------------------
def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("router", router_node)
    builder.add_node("tool", tool_node)
    builder.add_node("response", response_node)

    builder.set_entry_point("router")

    builder.add_edge("router", "tool")
    builder.add_edge("tool", "response")
    builder.add_edge("response", END)

    return builder.compile()