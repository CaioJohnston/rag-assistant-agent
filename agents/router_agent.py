"""
router_agent.py — Ponto de entrada do agente para a UI e os testes.

Importa o grafo compilado de my_agent.agent e expõe:
  - run_agent(user_input)   : invocação simples, retorna string
  - stream_agent(user_input): gerador para streaming na UI  [TODO fase 5]
"""

"""
agents/router_agent.py — Ponto de entrada do agente para a UI e os testes.

Importa o grafo compilado de graph/workflow e expõe:
  - run_agent(user_input)    : invocação simples, retorna string
  - stream_agent(user_input) : gerador para streaming na UI  [TODO fase 5]
"""

from graph.workflow import graph


def run_agent(user_input: str) -> str:
    """
    Invoca o grafo com o input do usuário e retorna a resposta final.
    """
    result = graph.invoke({
        "messages": [{"role": "user", "content": user_input}]
    })
    return result.get("output", "Não foi possível gerar uma resposta.")