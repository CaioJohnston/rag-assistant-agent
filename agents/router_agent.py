from graph.workflow import build_graph

graph = build_graph()


def run_agent(user_input: str) -> str:
    result = graph.invoke({"input": user_input})
    return result["output"]