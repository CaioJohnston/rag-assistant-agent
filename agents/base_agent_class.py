"""
agents/base_agent_class.py — Classe base para agentes com Function Calling via Azure AI Foundry.

Fluxo com Function Calling:
1. query chega ao Foundry
2. Foundry decide chamar a tool (emite tool_call)
3. SDK executa automaticamente a função Python (enable_auto_function_calls)
4. resultado volta para o Foundry
5. Foundry formula a resposta final

Thread persistente:
  run_with_debug() aceita thread_id opcional.
  Se fornecido, continua na thread existente — o modelo ve o historico completo
  e decide naturalmente quais tools ainda precisam ser chamadas.
  Se None, cria uma thread nova (comportamento padrao).

Os agentes são criados uma única vez via: python agents/init_agents.py

Em runtime, _get_agent_id() resolve o ID em 2 etapas:
1. cache em memória  — instantâneo
2. list_agents()     — fallback na primeira chamada após restart
"""

import os
import functools
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
            f"Agente '{self.NAME}' nao encontrado no Foundry. "
            f"Execute: python agents/init_agents.py"
        )

    def _wrap_for_debug(self, fn, debug: dict):
        """
        Envolve uma tool function para capturar input/output no debug dict.
        Usa functools.wraps para preservar __name__ e __doc__ —
        obrigatório para o FunctionTool gerar o schema correto para o Foundry.
        """
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            entry = {
                "tool":  fn.__name__,
                "input": args[0] if args else str(kwargs),
            }
            result = fn(*args, **kwargs)
            entry["output"] = result[:800] if isinstance(result, str) else str(result)[:800]
            debug.setdefault("tools_called", []).append(entry)
            return result
        return wrapper

    def _execute(
        self,
        client: AgentsClient,
        agent_id: str,
        query: str,
        tool_functions: set,
        thread_id: str | None = None,
    ) -> tuple[str, str]:
        """
        Executa uma query no Foundry e retorna (resposta, thread_id).

        Se thread_id for fornecido, adiciona a mensagem na thread existente
        e continua o historico — o modelo ve todas as trocas anteriores.
        Se thread_id for None, cria uma thread nova.
        """
        if tool_functions:
            toolset = ToolSet()
            toolset.add(FunctionTool(tool_functions))
            client.enable_auto_function_calls(toolset)
        else:
            toolset = None

        if thread_id is None:
            thread_id = client.threads.create().id

        client.messages.create(thread_id=thread_id, role="user", content=query)

        kwargs = {"thread_id": thread_id, "agent_id": agent_id}
        if toolset:
            kwargs["toolset"] = toolset

        run = client.runs.create_and_process(**kwargs)

        if run.status != RunStatus.COMPLETED:
            return f"[{self.NAME}] Run finalizado com status inesperado: {run.status}", thread_id

        messages       = list(client.messages.list(thread_id=thread_id))
        assistant_msgs = [m for m in messages if m.role == "assistant"]

        if not assistant_msgs:
            return "Nao foi possivel gerar uma resposta.", thread_id

        response = "".join(
            block.text.value
            for block in assistant_msgs[-1].content
            if hasattr(block, "text")
        )
        return response, thread_id

    def run(self, query: str, thread_id: str | None = None) -> str:
        client   = self._get_client()
        agent_id = self._get_agent_id(client)
        response, _ = self._execute(client, agent_id, query, self._get_tool_functions(), thread_id)
        return response

    def run_with_debug(
        self,
        query: str,
        thread_id: str | None = None,
    ) -> tuple[str, dict, str]:
        """
        Executa a query e retorna (resposta, debug, thread_id).

        O thread_id retornado pode ser passado de volta em chamadas
        subsequentes para continuar na mesma thread.
        """
        debug    = {"agent": self.NAME}
        client   = self._get_client()
        agent_id = self._get_agent_id(client)
        wrapped  = {self._wrap_for_debug(fn, debug) for fn in self._get_tool_functions()}
        response, used_thread_id = self._execute(client, agent_id, query, wrapped, thread_id)
        return response, debug, used_thread_id
