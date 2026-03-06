"""
agents/user_agent.py — UserAgent persistente via Azure AI Foundry.

Não usa Function Calling — apenas processa e valida o input do usuário.
Posição no pipeline: Streamlit → UserAgent → OrchestratorAgent → Especialista
"""

from agents.base_agent_class import BaseFoundryAgent


class UserAgent(BaseFoundryAgent):
    NAME = "user-agent"
    INSTRUCTIONS = """
You are a user input validator and query reformulator.

Steps:
1. Check if the query is intelligible and in scope (climate data, web search, weather, documents)
2. If offensive, harmful or completely off-topic, respond with exactly:
   BLOCKED: <brief reason>
3. If vague or ambiguous, reformulate into a clear, specific question
4. If already clear, return as-is (possibly with minor improvements)

Rules:
- Respond with ONLY the reformulated query (or BLOCKED: reason)
- Do not explain your reformulation
- Preserve the original language of the user
"""

    def _get_tool_functions(self) -> set:
        return set()   # sem tools — só processa texto


# instância global
user_agent = UserAgent()
