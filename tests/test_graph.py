from graph.workflow import build_graph


def test_graph_runs():
    graph = build_graph()

    result = graph.invoke(
        {
            "messages": [
                {"role": "user", "content": "latest LangChain news"}
            ]
        }
    )

    assert "messages" in result
    print(result)