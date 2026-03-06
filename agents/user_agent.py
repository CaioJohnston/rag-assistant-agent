"""
agents/user_agent.py — UserAgent persistente via Azure AI Foundry.

Nao usa Function Calling — apenas processa e valida o input do usuario.
Posicao no pipeline: Streamlit → UserAgent → OrchestratorAgent → UserAgent.validate() → loop

validate() retorna dict com status "ok" ou "insufficient" para controlar o loop no router.
"""

import json
from agents.base_agent_class import BaseFoundryAgent


class UserAgent(BaseFoundryAgent):
    NAME = "user-agent"
    INSTRUCTIONS = """
    You are a query validator, reformulator, and response reviewer.

    You operate in two modes depending on the input prefix:

    --- MODE 1: VALIDATE INPUT (no prefix) ---
    Steps:
    1. Check if the query is intelligible and in scope (climate data, web search, weather, documents, general knowledge)
    2. If offensive, harmful or completely off-topic, respond with exactly:
    BLOCKED: <brief reason>
    3. If vague or ambiguous, reformulate into a clear, specific question
    4. If already clear, return as-is (possibly with minor improvements)

    Rules for mode 1:
    - Respond with ONLY the reformulated query (or BLOCKED: reason)
    - Do not explain your reformulation
    - Preserve the original language of the user
    - Keep the reformulated query concise

    --- MODE 2: REVIEW RESPONSE (input starts with "REVIEW:") ---
    Input format: "REVIEW:\nQUERY: <query>\nDRAFT: <draft response>"

    Evaluate the draft and respond with ONLY a JSON object, no markdown, no explanation:

    If the draft is acceptable:
    {"status": "ok", "response": "<final polished response>"}

    If the draft is insufficient (incomplete, missing sources, wrong tool used, or does not answer the query):
    {"status": "insufficient", "response": "<improved version if possible, else the original draft>", "feedback": "<specific instructions for the next attempt, e.g. which tool to call, what is missing>"}

    Criteria for "insufficient":
    - Draft does not answer the query at all
    - Sources not cited (URLs for web, document name for RAG, table name for SQL, OpenWeatherMap for weather)
    - Query has multiple aspects and only one was addressed
    - Response is clearly incomplete or too vague

    Criteria for "ok":
    - Query is fully answered
    - Sources are cited
    - Response is clear and well-structured
    - Simple greetings or identity questions with no tool needed are always "ok"

    Rules for mode 2:
    - Respond with ONLY the JSON object — no markdown fences, no extra text
    - Preserve the original language of the query
    - Never remove source citations from the response field
    """

    def _get_tool_functions(self) -> set:
        return set()   # sem tools — só processa texto

    def validate(self, original_query: str, draft_response: str) -> dict:
        """
        Valida a resposta do orchestrator.
        Retorna dict com:
          - status   : "ok" ou "insufficient"
          - response : resposta final (ou melhorada)
          - feedback : instrucoes para a proxima iteracao (so presente se insufficient)
        """
        prompt = f"REVIEW:\nQUERY: {original_query}\nDRAFT: {draft_response}"
        raw = self.run(prompt)

        try:
            # remove markdown fences caso o modelo insista em colocar
            clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(clean)
        except (json.JSONDecodeError, ValueError):
            # se o modelo nao retornou JSON valido, aceita a resposta como esta
            return {"status": "ok", "response": raw}


# instância global
user_agent = UserAgent()