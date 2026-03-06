"""
agents/router_agent.py — Ponto de entrada do pipeline multi-agent (Foundry).

Pipeline com loop de refinamento:
  query → UserAgent.run() → loop (max 3x):
  OrchestratorAgent.run_with_debug()
  UserAgent.validate()  → "ok": finaliza
                        → "insufficient": reinjeta feedback e repete
"""

import time
from dotenv import load_dotenv

load_dotenv(override=True)

MAX_ITERATIONS = 3


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

    # etapa 1 — UserAgent valida e reformula a query
    t0 = time.time()
    log("AGENTE", "user-agent recebeu a query")
    processed_query = user_agent.run(user_input)
    elapsed_user = time.time() - t0

    if processed_query.upper().startswith("BLOCKED:"):
        reason = processed_query.split(":", 1)[-1].strip()
        log("user-agent BLOCKED", f"Motivo: {reason}", elapsed_user)
        log("PIPELINE END", f"Tempo total: {time.time() - pipeline_start:.2f}s")
        return f"Nao posso responder a essa pergunta: {reason}", {
            "logs": logs,
            "blocked": True,
        }

    if processed_query.strip() != user_input.strip():
        log("user-agent", f"Query reformulada: {processed_query!r}", elapsed_user)
    else:
        log("user-agent", "Query aprovada sem alteracao", elapsed_user)

    # etapa 2 — loop de refinamento (max MAX_ITERATIONS voltas)
    current_query  = processed_query
    last_debug     = {}
    final_response = None

    for attempt in range(1, MAX_ITERATIONS + 1):
        log("LOOP", f"Iteracao {attempt}/{MAX_ITERATIONS}")

        # orchestrator executa tools e gera draft
        t1 = time.time()
        log("AGENTE", f"orchestrator-agent recebeu a query (tentativa {attempt})")
        draft, agent_debug = OrchestratorAgent().run_with_debug(current_query)
        elapsed_orch = time.time() - t1
        last_debug = agent_debug

        tools_called = agent_debug.get("tools_called", [])
        log(
            "orchestrator-agent",
            f"{len(tools_called)} tool(s) executada(s) | tempo: {elapsed_orch:.2f}s",
            elapsed_orch,
        )

        for tool_call in tools_called:
            log(
                f"TOOL CALL: {tool_call['tool']}",
                f"Input: {tool_call['input']!r}",
            )
            log(
                f"TOOL RESULT: {tool_call['tool']}",
                tool_call.get("output", ""),
            )

        log("orchestrator-agent", "Draft gerado — enviando para validacao")

        # user-agent valida a resposta
        t2 = time.time()
        log("AGENTE", f"user-agent validando resposta (tentativa {attempt})")
        validation = user_agent.validate(processed_query, draft)
        elapsed_val = time.time() - t2

        status   = validation.get("status", "ok")
        feedback = validation.get("feedback", "")

        if status == "ok":
            log("user-agent", f"Resposta aprovada na tentativa {attempt}", elapsed_val)
            final_response = validation.get("response", draft)
            break

        # insufficient — injeta feedback e tenta novamente
        log(
            "user-agent INSUFFICIENT",
            f"Feedback: {feedback!r} | Tentativa {attempt}/{MAX_ITERATIONS}",
            elapsed_val,
        )

        if attempt < MAX_ITERATIONS:
            current_query = (
                f"{processed_query}\n\n"
                f"FEEDBACK DA TENTATIVA ANTERIOR: {feedback}"
            )
        else:
            # esgotou as tentativas — usa a melhor resposta disponivel
            log("LOOP", f"Limite de {MAX_ITERATIONS} tentativas atingido — usando ultima resposta")
            final_response = validation.get("response", draft)

    log("PIPELINE END", f"Tempo total: {time.time() - pipeline_start:.2f}s")

    return final_response, {"logs": logs, **last_debug}