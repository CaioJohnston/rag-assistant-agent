"""
agents/router_agent.py — Ponto de entrada do pipeline multi-agent (Foundry).

Pipeline com loop de refinamento e thread persistente:
  query -> UserAgent.run()
        -> OrchestratorAgent cria thread no Foundry
        -> loop (max 3x) na MESMA thread:
            OrchestratorAgent recebe feedback como mensagem de usuario
            Modelo ve historico completo e decide quais tools ainda faltam
            UserAgent.validate() -> "ok"          : finaliza
                                  -> "insufficient": injeta feedback na mesma thread
"""

import time
import logging
import json
import sys
from dotenv import load_dotenv

load_dotenv(override=True)

MAX_ITERATIONS = 3

# logger JSON estruturado para stdout 
# cada linha emitida e um JSON valido — compativel com Azure Monitor,

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.getMessage(),
        }
        for key in ("pipeline_step", "elapsed_s", "tool", "blocked", "attempt", "thread_id"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)


_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(_JsonFormatter())

logger = logging.getLogger("multi_agent.pipeline")
logger.setLevel(logging.INFO)
logger.addHandler(_handler)
logger.propagate = False   # evita duplicacao no logger raiz


# helpers 

def _jlog(step: str, message: str, elapsed: float = None, **extra):
    """Emite uma linha JSON para stdout com campos padronizados."""
    kwargs = {"extra": {"pipeline_step": step, **extra}}
    if elapsed is not None:
        kwargs["extra"]["elapsed_s"] = round(elapsed, 3)
    logger.info(message, **kwargs)


def _build_feedback_message(feedback: str, attempt: int) -> str:
    """
    Monta a mensagem de followup que sera adicionada na thread existente.

    O modelo ve o historico completo da thread e recebe uma instrucao
    clara sobre o que esta faltando, sem precisar recriar contexto.
    """
    return (
        f"Sua resposta anterior foi considerada INCOMPLETA pelo avaliador.\n\n"
        f"Feedback: {feedback}\n\n"
        f"Por favor, complemente sua resposta anterior chamando as tools necessarias "
        f"para cobrir todos os aspectos da pergunta original. "
        f"Esta e a tentativa {attempt} de {MAX_ITERATIONS}."
    )


#  pipeline 

def run_agent(user_input: str) -> str:
    response, _ = run_agent_with_debug(user_input)
    return response


def run_agent_with_debug(user_input: str) -> tuple[str, dict]:
    from agents.user_agent import user_agent
    from agents.orchestrator_agent import OrchestratorAgent

    pipeline_start = time.time()
    logs = []

    def log(step: str, detail: str, elapsed: float = None):
        entry = {"step": step, "detail": detail}
        if elapsed is not None:
            entry["elapsed"] = f"{elapsed:.2f}s"
        logs.append(entry)

    log("PIPELINE START", f"Input recebido: {user_input!r}")
    _jlog("PIPELINE START", f"Input recebido: {user_input!r}")

    # etapa 1 — UserAgent valida e reformula a query
    t0 = time.time()
    log("AGENTE", "user-agent recebeu a query")
    processed_query = user_agent.run(user_input)
    elapsed_user = time.time() - t0

    if processed_query.upper().startswith("BLOCKED:"):
        reason = processed_query.split(":", 1)[-1].strip()
        log("user-agent BLOCKED", f"Motivo: {reason}", elapsed_user)
        log("PIPELINE END", f"Tempo total: {time.time() - pipeline_start:.2f}s")
        _jlog("user-agent BLOCKED", f"Motivo: {reason}", elapsed_user, blocked=True)
        _jlog("PIPELINE END", "Pipeline encerrado", time.time() - pipeline_start)
        return f"Nao posso responder a essa pergunta: {reason}", {
            "logs": logs,
            "blocked": True,
        }

    if processed_query.strip() != user_input.strip():
        log("user-agent", f"Query reformulada: {processed_query!r}", elapsed_user)
        _jlog("user-agent", f"Query reformulada: {processed_query!r}", elapsed_user)
    else:
        log("user-agent", "Query aprovada sem alteracao", elapsed_user)
        _jlog("user-agent", "Query aprovada sem alteracao", elapsed_user)

    # etapa 2 - loop de refinamento com thread persistente
    orchestrator   = OrchestratorAgent()
    thread_id      = None
    last_debug     = {}
    final_response = None
    feedback       = ""

    for attempt in range(1, MAX_ITERATIONS + 1):
        log("LOOP", f"Iteracao {attempt}/{MAX_ITERATIONS}")
        _jlog("LOOP", f"Iteracao {attempt}/{MAX_ITERATIONS}", attempt=attempt)

        # primeira iteracao: envia a query processada e cria a thread
        # iteracoes seguintes: injeta o feedback na mesma thread
        # o modelo ve o historico completo e decide naturalmente quais tools faltam
        if attempt == 1:
            current_message = processed_query
        else:
            current_message = _build_feedback_message(feedback, attempt)

        t1 = time.time()
        draft, agent_debug, thread_id = orchestrator.run_with_debug(
            current_message,
            thread_id=thread_id,
        )
        elapsed_orch = time.time() - t1
        last_debug   = agent_debug

        tools_called = agent_debug.get("tools_called", [])

        log(
            "orchestrator-agent",
            f"{len(tools_called)} tool(s) executada(s) | thread: {thread_id} | tempo: {elapsed_orch:.2f}s",
            elapsed_orch,
        )
        _jlog(
            "orchestrator-agent",
            f"{len(tools_called)} tool(s) executada(s)",
            elapsed_orch,
            attempt=attempt,
            thread_id=thread_id,
        )

        for tool_call in tools_called:
            log(f"TOOL CALL: {tool_call['tool']}", f"Input: {tool_call['input']!r}")
            log(f"TOOL RESULT: {tool_call['tool']}", tool_call.get("output", ""))
            _jlog("TOOL CALL",   f"Input: {tool_call['input']!r}", tool=tool_call["tool"])
            _jlog("TOOL RESULT", tool_call.get("output", "")[:300],  tool=tool_call["tool"])

        # user-agent valida a resposta
        t2 = time.time()
        validation  = user_agent.validate(processed_query, draft)
        elapsed_val = time.time() - t2
        status      = validation.get("status", "ok")
        feedback    = validation.get("feedback", "")

        if status == "ok":
            log("user-agent", f"Resposta aprovada na tentativa {attempt}", elapsed_val)
            _jlog("user-agent", f"Resposta aprovada na tentativa {attempt}", elapsed_val, attempt=attempt)
            final_response = validation.get("response", draft)
            break

        log(
            "user-agent INSUFFICIENT",
            f"Feedback: {feedback!r} | Tentativa {attempt}/{MAX_ITERATIONS}",
            elapsed_val,
        )
        _jlog("user-agent INSUFFICIENT", f"Feedback: {feedback!r}", elapsed_val, attempt=attempt)

        if attempt == MAX_ITERATIONS:
            log("LOOP", f"Limite de {MAX_ITERATIONS} tentativas atingido")
            _jlog("LOOP", f"Limite de {MAX_ITERATIONS} tentativas atingido")
            final_response = validation.get("response", draft)

    total = time.time() - pipeline_start
    log("PIPELINE END", f"Tempo total: {total:.2f}s")
    _jlog("PIPELINE END", "Pipeline concluido", total)

    return final_response, {"logs": logs, **last_debug}
    