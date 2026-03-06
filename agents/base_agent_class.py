"""
agents/base_agent_class.py — Classe base para agentes com Function Calling via Azure AI Foundry.

Fluxo com Function Calling:
  1. query chega ao Foundry
  2. Foundry decide chamar a tool (emite tool_call)
  3. SDK executa automaticamente a função Python (enable_auto_function_calls)
  4. resultado volta para o Foundry
  5. Foundry formula a resposta final

Os agentes são criados uma única vez via:
    python agents/init_agents.py

Em runtime, _get_agent_id() resolve o ID em 2 etapas:
  1. cache em memória  — instantâneo
  2. list_agents()     — fallback na primeira chamada após restart
"""

import os
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import FunctionTool, ToolSet, RunStatus
from azure.identity import ClientSecretCredential
from dotenv import load_dotenv

load_dotenv(override=True)

credential = ClientSecretCredential(
    tenant_id=os.getenv("AZURE_TENANT_ID"),
    client_id=os.getenv("AZURE_CLIENT_ID"),
    client_secret=os.getenv("AZURE_CLIENT_SECRET"),
)

DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
ENDPOINT   = os.getenv("AZURE_AI_PROJECT_ENDPOINT", "")

# cache em memória — populado na primeira chamada após restart
_agent_id_cache: dict[str, str] = {}


class BaseFoundryAgent:
    NAME         = "base-agent"
    INSTRUCTIONS = "You are a helpful assistant."

    def _get_tool_functions(self) -> set:
        """
        Retorna o set de funções Python que o Foundry pode chamar via Function Calling.
        Override nas subclasses para registrar as tools corretas.
        """
        return set()

    def _get_client(self) -> AgentsClient:
        return AgentsClient(
            endpoint=ENDPOINT,
            credential=credential,
        )

    def _get_agent_id(self, client: AgentsClient) -> str:
        """
        Resolve o ID do agente em 2 etapas:
          1. cache em memória  → instantâneo
          2. list_agents()     → só na primeira chamada após restart

        Nunca cria agentes — responsabilidade do init_agents.py.
        """
        if self.NAME in _agent_id_cache:
            return _agent_id_cache[self.NAME]

        for agent in client.list_agents():
            if agent.name == self.NAME:
                _agent_id_cache[self.NAME] = agent.id
                return agent.id

        raise RuntimeError(
            f"Agente '{self.NAME}' não encontrado no Foundry. "
            f"Execute: python agents/init_agents.py"
        )

    def run(self, query: str) -> str:
        """
        Executa o ciclo completo com Function Calling:
          query → Foundry → tool_call → Python executa → Foundry responde
        """
        client   = self._get_client()
        agent_id = self._get_agent_id(client)

        # registra as funções Python que o Foundry pode chamar
        tool_functions = self._get_tool_functions()

        if tool_functions:
            toolset = ToolSet()
            toolset.add(FunctionTool(tool_functions))
            # SDK executa os tool_calls automaticamente durante runs.create_and_process
            client.enable_auto_function_calls(toolset)

        thread = client.threads.create()
        client.messages.create(
            thread_id=thread.id,
            role="user",
            content=query,
        )

        run = client.runs.create_and_process(
            thread_id=thread.id,
            agent_id=agent_id,
        )

        if run.status != RunStatus.COMPLETED:
            return f"[{self.NAME}] Run finalizado com status inesperado: {run.status}"

        messages       = list(client.messages.list(thread_id=thread.id))
        assistant_msgs = [m for m in messages if m.role == "assistant"]

        if not assistant_msgs:
            return "Não foi possível gerar uma resposta."

        return "".join(
            block.text.value
            for block in assistant_msgs[-1].content
            if hasattr(block, "text")
        )
