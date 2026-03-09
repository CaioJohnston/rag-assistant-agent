"""
tools/sql_query.py — Queries no PostgreSQL via SQLDatabaseToolkit do LangChain.

Fluxo:
  SQLQueryInput(question) → LLM gera SQL → executa no Postgres → SQLQueryResult

Segurança:
  - apenas SELECT permitido (whitelist via sqlglot)
  - máximo de 50 linhas retornadas

Lazy init: db e llm são criados apenas na primeira chamada a run()
evitando conexão ao banco no momento do import (quebra testes locais)
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv(override=True)

MAX_ROWS = 50


# ── dataclasses de entrada e saída ────────────────────────────────────────────

@dataclass
class SQLQueryInput:
    """Entrada tipada para a tool de consulta SQL."""
    question: str


@dataclass
class SQLQueryResult:
    """Saída tipada da tool de consulta SQL."""
    sql: str = ""
    rows: str = ""
    blocked: bool = False
    error: str | None = None

    def __str__(self) -> str:
        if self.error:
            return self.error
        if self.blocked:
            return "Query bloqueada por segurança: apenas SELECT é permitido."
        if not self.rows or self.rows == "[]":
            return "Nenhum resultado encontrado para essa consulta."
        return f"**Query executada:**\n```sql\n{self.sql}\n```\n\n**Resultado:**\n{self.rows}"


# ── validação de SQL ──────────────────────────────────────────────────────────

def _is_safe(sql: str) -> bool:
    """Permite apenas SELECT — bloqueia INSERT, UPDATE, DELETE, DROP, etc."""
    try:
        import sqlglot
        statements = sqlglot.parse(sql)
        return all(
            type(stmt).__name__ == "Select"
            for stmt in statements
            if stmt is not None
        )
    except Exception:
        clean = sql.strip().upper()
        return clean.startswith("SELECT") and not any(
            kw in clean for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE"]
        )


# ── tool class ────────────────────────────────────────────────────────────────

class SQLQueryTool:
    """
    Executa queries em linguagem natural no PostgreSQL usando SQLDatabaseToolkit.
    Entrada : SQLQueryInput (dataclass com campo question)
    Saída   : SQLQueryResult (dataclass tipada)

    Lazy init — db e llm só são criados na primeira chamada a run()
    """

    def __init__(self):
        self._db      = None
        self._llm     = None
        self._toolkit = None
        self._query_tool = None
        self._info_tool  = None

    def _init(self):
        """Inicializa conexões apenas quando necessário."""
        if self._db is not None:
            return

        from langchain_community.utilities import SQLDatabase
        from langchain_community.agent_toolkits import SQLDatabaseToolkit
        from langchain_openai import AzureChatOpenAI

        uri = (
            f"postgresql+psycopg2://"
            f"{os.getenv('POSTGRES_USER', 'postgres')}:"
            f"{os.getenv('POSTGRES_PASSWORD', 'postgres')}@"
            f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
            f"{os.getenv('POSTGRES_PORT', '5432')}/"
            f"{os.getenv('POSTGRES_DB', 'ragdb')}"
        )

        self._db = SQLDatabase.from_uri(
            uri,
            include_tables=["clima_mensal", "series_historicas", "resumo_anual"],
            sample_rows_in_table_info=2,
        )

        self._llm = AzureChatOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            api_version="2024-05-01-preview",
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
            temperature=0,
        )

        self._toolkit    = SQLDatabaseToolkit(db=self._db, llm=self._llm)
        tools            = self._toolkit.get_tools()
        self._query_tool = next(t for t in tools if t.name == "sql_db_query")
        self._info_tool  = next(t for t in tools if t.name == "sql_db_schema")

    def run(self, input: SQLQueryInput) -> SQLQueryResult:
        """Executa a consulta e retorna SQLQueryResult tipado."""
        self._init()

        schema = self._info_tool.invoke("clima_mensal, series_historicas, resumo_anual")

        prompt = f"""
Você é um especialista em SQL PostgreSQL.
Dado o schema abaixo e a pergunta do usuário, gere APENAS o SQL (sem explicações).
Regras:
- Apenas SELECT é permitido
- Máximo de {MAX_ROWS} linhas (use LIMIT {MAX_ROWS})
- Use nomes de colunas exatos do schema
- Não use markdown, não use ```sql

Schema:
{schema}

Pergunta: {input.question}

SQL:"""

        sql = self._llm.invoke(prompt).content.strip()
        sql = sql.replace("```sql", "").replace("```", "").strip()

        if not _is_safe(sql):
            return SQLQueryResult(sql=sql, blocked=True)

        result = self._query_tool.invoke(sql)

        return SQLQueryResult(sql=sql, rows=str(result))


# instância global — lazy, não conecta ao banco no import
sql_tool = SQLQueryTool()


@tool
def sql_query(question: str) -> str:
    """
    Consulta dados climáticos de Belém no PostgreSQL a partir de linguagem natural.
    Use para perguntas sobre médias mensais, comparações históricas entre períodos,
    temperatura, chuva, umidade ou tendências climáticas ao longo do tempo.
    """
    return str(sql_tool.run(SQLQueryInput(question=question)))
