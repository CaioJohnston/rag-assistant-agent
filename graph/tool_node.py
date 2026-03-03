from typing import Dict, Any

from tools.web_search import SerpAPIETool

search_tool = SerpAPIETool(k=5)


def tool_router(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node responsável por decidir e executar tools.
    (versão inicial determinística — depois vira LLM-driven)
    """

    last_message = state["messages"][-1]["content"]

    # heurística simples inicial
    if any(word in last_message.lower() for word in ["search", "latest", "news"]):
        results = search_tool.search_web(last_message)

        state["messages"].append(
            {
                "role": "tool",
                "content": str(results),
                "name": "web_search",
            }
        )

    return state