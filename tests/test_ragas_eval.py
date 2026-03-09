"""
tests/test_ragas_eval.py — Avaliacao automatizada do pipeline via RAGAS.

RAGAS (Retrieval Augmented Generation Assessment) avalia respostas do pipeline
em metricas estabelecidas para sistemas RAG e multi-agent:

  - answer_relevancy    : a resposta e relevante para a pergunta?
  - faithfulness        : a resposta e fiel aos contextos recuperados?
  - context_recall      : os contextos recuperados cobrem a resposta esperada?
  - context_precision   : os contextos recuperados sao precisos?

Setup:
    pip install ragas>=0.2.0

Rodar:
    pytest tests/test_ragas_eval.py -v -s
    pytest tests/test_ragas_eval.py -v -s --eval-real   # pipeline real (lento, caro)

Sem --eval-real, as respostas e contextos sao simulados — so o avaliador RAGAS
consome tokens. Com --eval-real, o pipeline completo e executado.

Requisitos no .env:
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_DEPLOYMENT
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock
from azure.ai.agents.models import RunStatus


# ── dataset de avaliacao ───────────────────────────────────────────────────────
# cada entrada segue o schema esperado pelo RAGAS:
#   question          : pergunta enviada ao pipeline
#   ground_truth      : resposta correta de referencia
#   simulated_answer  : resposta simulada do pipeline (usada sem --eval-real)
#   simulated_contexts: trechos de contexto simulados retornados pelas tools
#   tool              : tool esperada (para identificacao do caso)

EVAL_DATASET = [
    {
        "id":       "weather-01",
        "tool":     "get_weather",
        "question": "Qual a temperatura atual em Belem?",
        "ground_truth": (
            "A temperatura atual em Belem e aproximadamente 28C com chuva leve "
            "e umidade em torno de 83%. Fonte: OpenWeatherMap."
        ),
        "simulated_answer": (
            "A temperatura atual em Belem e de 28.0C com sensacao termica de 32C. "
            "Umidade relativa: 83%. Condicoes: chuva leve. Fonte: OpenWeatherMap."
        ),
        "simulated_contexts": [
            "Belem — condicoes atuais: Temperatura 28.0C | Sensacao 32C | "
            "Umidade 83% | Vento 3.6 m/s | Chuva leve. Fonte: OpenWeatherMap."
        ],
    },
    {
        "id":       "sql-01",
        "tool":     "query_climate_database",
        "question": "Qual a precipitacao media em marco em Belem historicamente?",
        "ground_truth": (
            "A precipitacao media em marco em Belem e de 441.2 mm no periodo 1967-1996, "
            "sendo o mes mais chuvoso do ano. Fonte: tabela clima_mensal."
        ),
        "simulated_answer": (
            "Segundo a tabela clima_mensal, a precipitacao media em marco em Belem "
            "e de 441.2 mm no periodo 1967-1996, o mes com maior indice pluviometrico do ano."
        ),
        "simulated_contexts": [
            "tabela: clima_mensal | periodo: 1967-1996\n"
            "mes: 3 | nome_mes: Marco | chuva_total: 441.2 mm | chuva_max_24h: 136 mm\n"
            "Marco e o mes com maior precipitacao media anual em Belem no periodo 1967-1996.",
            "tabela: clima_mensal | comparativo mensal (1967-1996)\n"
            "Janeiro: 378.1 mm | Fevereiro: 426.6 mm | Marco: 441.2 mm | "
            "Abril: 381.5 mm | Maio: 299.8 mm\n"
            "Marco representa o pico da estacao chuvosa. "
            "Sendo o mes mais chuvoso do ano com 441.2 mm de precipitacao media.",
        ],
    },
    {
        "id":       "web-01",
        "tool":     "search_web",
        "question": "O que e Retrieval-Augmented Generation (RAG)?",
        "ground_truth": (
            "RAG e uma tecnica que combina recuperacao de documentos com geracao "
            "de texto por LLMs para produzir respostas mais precisas e fundamentadas."
        ),
        "simulated_answer": (
            "RAG (Retrieval-Augmented Generation) e uma tecnica que combina recuperacao "
            "de documentos relevantes com geracao de texto por modelos de linguagem. "
            "O modelo consulta uma base de conhecimento antes de gerar a resposta, "
            "reduzindo alucinacoes. Fonte: https://arxiv.org/abs/2005.11401"
        ),
        "simulated_contexts": [
            "TITLE: Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks\n"
            "SNIPPET: RAG is a technique that combines retrieval of relevant documents "
            "with text generation by large language models (LLMs). "
            "The model retrieves documents from a knowledge base before generating a response, "
            "reducing hallucinations and improving factual accuracy.\n"
            "SOURCE_URL: https://arxiv.org/abs/2005.11401",
            "TITLE: RAG explained - IBM Research\n"
            "SNIPPET: Retrieval-Augmented Generation (RAG) improves LLM accuracy by grounding "
            "responses in retrieved documents from an external knowledge base. "
            "It combines parametric memory (model weights) with non-parametric memory (retrieved docs) "
            "to produce more precise and well-founded answers.\n"
            "SOURCE_URL: https://research.ibm.com/blog/retrieval-augmented-generation-RAG",
        ],
    },
    {
        "id":       "sql-02",
        "tool":     "query_climate_database",
        "question": "Como variou a temperatura media anual de Belem ao longo dos seculos?",
        "ground_truth": (
            "A temperatura media anual de Belem aumentou de 25.6C (1896-1922) "
            "para 25.9C (1930-1960) e 26.4C (1967-1996), segundo a tabela resumo_anual."
        ),
        "simulated_answer": (
            "Com base na tabela resumo_anual, a temperatura media anual de Belem "
            "aumentou progressivamente: 25.6C no periodo 1896-1922, "
            "25.9C em 1930-1960 e 26.4C em 1967-1996. "
            "Aumento total de 0.8C em um seculo. Fonte: tabela resumo_anual."
        ),
        "simulated_contexts": [
            "tabela: resumo_anual | periodo: 1896-1922 | temp_media_anual: 25.6C | "
            "chuva_total_anual: 2538.1 mm | fonte: Cunha & Bastos (1973)",
            "tabela: resumo_anual | periodo: 1930-1960 | temp_media_anual: 25.9C | "
            "chuva_total_anual: 2752.0 mm | fonte: Brasil (1968) / INMET",
            "tabela: resumo_anual | periodo: 1967-1996 | temp_media_anual: 26.4C | "
            "chuva_total_anual: 3001.3 mm | fonte: Embrapa Amazonia Oriental",
        ],
    },
    {
        "id":       "multi-tool-01",
        "tool":     "multi",
        "question": "Compare a temperatura atual de Belem com a media historica de outubro.",
        "ground_truth": (
            "A temperatura atual em Belem e de 28C (OpenWeatherMap). "
            "A media historica de outubro e 26.8C (tabela clima_mensal, 1967-1996). "
            "Belem esta 1.2C acima da media historica."
        ),
        "simulated_answer": (
            "Temperatura atual em Belem: 28.0C (Fonte: OpenWeatherMap). "
            "Media historica de outubro no periodo 1967-1996: 26.8C "
            "(Fonte: tabela clima_mensal). "
            "Belem esta 1.2C acima da media historica para este mes."
        ),
        "simulated_contexts": [
            "Belem — condicoes atuais: Temperatura 28.0C | Fonte: OpenWeatherMap.",
            "tabela: clima_mensal | mes: Outubro | temp_media: 26.8C | periodo: 1967-1996",
        ],
    },
]


# ── configuracao do LLM e embeddings para o RAGAS ─────────────────────────────

def _get_ragas_llm():
    """Instancia o LLM Azure OpenAI no formato esperado pelo RAGAS."""
    # LangchainLLMWrapper e o unico wrapper com suporte estavel ao Azure OpenAI no RAGAS.
    # llm_factory retorna tipo incompativel com evaluate() quando usado com AzureOpenAI.
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from ragas.llms import LangchainLLMWrapper
        from langchain_openai import AzureChatOpenAI

    llm = AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        api_key=os.getenv("AZURE_OPENAI_KEY", ""),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
        api_version="2024-02-01",
        temperature=0,
    )
    return LangchainLLMWrapper(llm)


def _get_ragas_embeddings():
    """Instancia os embeddings Azure OpenAI no formato esperado pelo RAGAS."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from ragas.embeddings.base import LangchainEmbeddingsWrapper
        from langchain_openai import AzureOpenAIEmbeddings

    embeddings = AzureOpenAIEmbeddings(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        api_key=os.getenv("AZURE_OPENAI_KEY", ""),
        azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002"),
        api_version="2024-02-01",
    )
    return LangchainEmbeddingsWrapper(embeddings)


# ── metricas RAGAS ─────────────────────────────────────────────────────────────

def _get_metrics():
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        # ragas.metrics (nao .collections) e compativel com LangchainLLMWrapper/Azure OpenAI.
        # ragas.metrics.collections exige llm_factory (InstructorLLM) que nao suporta Azure.
        from ragas.metrics import (
            AnswerRelevancy,
            Faithfulness,
            ContextRecall,
            ContextPrecision,
        )
    ragas_llm        = _get_ragas_llm()
    ragas_embeddings = _get_ragas_embeddings()

    return [
        AnswerRelevancy(llm=ragas_llm, embeddings=ragas_embeddings),
        Faithfulness(llm=ragas_llm),
        ContextRecall(llm=ragas_llm),
        ContextPrecision(llm=ragas_llm),
    ]


# ── thresholds minimos por metrica ─────────────────────────────────────────────
# scores RAGAS vao de 0 a 1

THRESHOLDS = {
    "answer_relevancy": 0.7,   # a resposta responde a pergunta
    "faithfulness":     0.7,   # a resposta e fiel aos contextos
    "context_recall":   0.5,   # contextos cobrem o ground_truth (mais tolerante em modo simulado)
    "context_precision":0.5,   # contextos sao precisos para a pergunta
}


# ── fixture: opcao --eval-real ─────────────────────────────────────────────────

def pytest_addoption(parser):
    try:
        parser.addoption(
            "--eval-real",
            action="store_true",
            default=False,
            help="Executa o pipeline real em vez de usar respostas simuladas.",
        )
    except ValueError:
        pass   # opcao ja registrada por outro modulo de teste


@pytest.fixture
def use_real_pipeline(request):
    return request.config.getoption("--eval-real", default=False)


# ── fixture: cache de agent_id ─────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def patch_agent_id_cache(request):
    """
    Pre-popula o cache de IDs com valores falsos no modo simulado.
    No modo real (--eval-real) o cache e limpo para forcao resolucao real via list_agents().
    """
    use_real = request.config.getoption("--eval-real", default=False)
    import agents.base_agent_class as base
    base._agent_id_cache.clear()
    if not use_real:
        base._agent_id_cache.update({
            "user-agent":         "fake-user-agent-id",
            "orchestrator-agent": "fake-orchestrator-agent-id",
        })
    yield
    base._agent_id_cache.clear()


# ── helpers de mock do pipeline ────────────────────────────────────────────────

def _make_text_block(text: str):
    block = MagicMock()
    block.text.value = text
    return block


def _make_assistant_message(text: str):
    msg = MagicMock()
    msg.role = "assistant"
    msg.content = [_make_text_block(text)]
    return msg


def _make_foundry_client(responses: list[str]):
    client = MagicMock()

    thread_stub = MagicMock()
    thread_stub.id = "thread-id-eval"
    client.threads.create.return_value = thread_stub

    run_stub = MagicMock()
    run_stub.status = RunStatus.COMPLETED
    client.runs.create_and_process.return_value = run_stub

    it = iter(responses)
    client.messages.list.side_effect = lambda **kw: [
        _make_assistant_message(next(it, "resposta padrao"))
    ]
    return client


def _get_pipeline_response(case: dict, use_real: bool) -> tuple[str, list[str]]:
    """
    Retorna (answer, contexts) para um caso de avaliacao.
    Se use_real=False, usa dados simulados do dataset.
    Se use_real=True, executa o pipeline real.
    """
    if use_real:
        from agents.router_agent import run_agent_with_debug
        response, debug = run_agent_with_debug(case["question"])
        # extrai contextos reais dos tool results no debug
        contexts = [
            entry["detail"]
            for entry in debug.get("logs", [])
            if entry["step"].startswith("TOOL RESULT")
        ]
        return response, contexts or ["sem contexto recuperado"]

    # modo simulado
    simulated_answer = case["simulated_answer"]
    ok_json = json.dumps({"status": "ok", "response": simulated_answer}, ensure_ascii=False)

    foundry_responses = [
        case["question"],    # user-agent: aprova
        simulated_answer,    # orchestrator: draft
        ok_json,             # user-agent: valida
    ]

    client = _make_foundry_client(foundry_responses)

    with patch("agents.base_agent_class.AgentsClient", return_value=client):
        from agents.router_agent import run_agent
        answer = run_agent(case["question"])

    return answer, case["simulated_contexts"]


# ── testes parametrizados ──────────────────────────────────────────────────────

@pytest.mark.parametrize("case", EVAL_DATASET, ids=[c["id"] for c in EVAL_DATASET])
def test_ragas_eval(case, use_real_pipeline):
    """
    Avalia a resposta do pipeline usando as metricas RAGAS.

    Para cada caso do dataset:
      1. Obtem answer e contexts (simulados ou reais)
      2. Monta o EvaluationDataset do RAGAS
      3. Executa evaluate() com as 4 metricas
      4. Verifica se cada metrica esta acima do threshold

    Output com -s:
      [weather-01] answer_relevancy=0.92 faithfulness=0.88
                   context_recall=0.75 context_precision=0.80
    """
    try:
        from ragas import evaluate, EvaluationDataset, SingleTurnSample
    except ImportError:
        pytest.skip("ragas nao instalado. Execute: pip install ragas>=0.2.0")

    answer, contexts = _get_pipeline_response(case, use_real_pipeline)

    assert answer, f"[{case['id']}] Pipeline retornou resposta vazia"

    # monta o sample no formato RAGAS
    sample = SingleTurnSample(
        user_input=case["question"],
        response=answer,
        retrieved_contexts=contexts,
        reference=case["ground_truth"],
    )
    dataset = EvaluationDataset(samples=[sample])

    try:
        import warnings
        metrics = _get_metrics()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            results = evaluate(dataset=dataset, metrics=metrics)
    except Exception as exc:
        pytest.skip(f"RAGAS avaliador indisponivel: {exc}")

    # extrai scores do resultado
    scores = results.to_pandas().iloc[0].to_dict()

    print(f"\n[{case['id']}]")
    failures = []

    for metric_name, threshold in THRESHOLDS.items():
        score = scores.get(metric_name, 0.0)
        status = "PASS" if score >= threshold else "FAIL"
        print(f"  {metric_name:<22} = {score:.3f}  (threshold: {threshold})  [{status}]")

        if score < threshold:
            failures.append(
                f"{metric_name}: {score:.3f} < {threshold}"
            )

    assert not failures, (
        f"[{case['id']}] Metricas abaixo do threshold:\n"
        + "\n".join(f"  {f}" for f in failures)
        + f"\n\nPergunta : {case['question']}"
        + f"\nResposta : {answer}"
    )


# ── teste de sumario do dataset completo ──────────────────────────────────────

def test_ragas_dataset_summary(use_real_pipeline):
    """
    Avalia o dataset completo de uma vez e imprime o sumario agregado.
    Nao falha por threshold individual — serve como relatorio geral.
    """
    try:
        from ragas import evaluate, EvaluationDataset, SingleTurnSample
    except ImportError:
        pytest.skip("ragas nao instalado. Execute: pip install ragas>=0.2.0")

    samples = []
    for case in EVAL_DATASET:
        answer, contexts = _get_pipeline_response(case, use_real_pipeline)
        samples.append(SingleTurnSample(
            user_input=case["question"],
            response=answer,
            retrieved_contexts=contexts,
            reference=case["ground_truth"],
        ))

    dataset = EvaluationDataset(samples=samples)

    try:
        import warnings
        metrics = _get_metrics()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            results = evaluate(dataset=dataset, metrics=metrics)
    except Exception as exc:
        pytest.skip(f"RAGAS avaliador indisponivel: {exc}")

    df = results.to_pandas()

    print("\n\n=== RAGAS EVALUATION SUMMARY ===")
    print(f"{'Metric':<25} {'Mean':>8} {'Min':>8} {'Max':>8}")
    print("-" * 52)

    for col in ["answer_relevancy", "faithfulness", "context_recall", "context_precision"]:
        if col in df.columns:
            print(
                f"{col:<25} "
                f"{df[col].mean():>8.3f} "
                f"{df[col].min():>8.3f} "
                f"{df[col].max():>8.3f}"
            )

    print("\nScores por caso:")
    for i, case in enumerate(EVAL_DATASET):
        row = df.iloc[i]
        scores_str = "  ".join(
            f"{col[:4]}={row[col]:.2f}"
            for col in ["answer_relevancy", "faithfulness", "context_recall", "context_precision"]
            if col in row
        )
        print(f"  [{case['id']:<18}] {scores_str}")
