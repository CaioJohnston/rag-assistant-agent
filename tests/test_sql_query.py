"""
tests/test_sql_query.py — Testes unitários da tool PostgreSQL.
"""

from unittest.mock import patch, MagicMock
from tools.sql_query import _is_safe


# testes de sanitização — não precisam de banco real

def test_select_permitido():
    assert _is_safe("SELECT * FROM clima_mensal") is True

def test_select_com_where_permitido():
    assert _is_safe("SELECT temp_media FROM clima_mensal WHERE mes = 3") is True

def test_insert_bloqueado():
    assert _is_safe("INSERT INTO clima_mensal VALUES (1, 2)") is False

def test_delete_bloqueado():
    assert _is_safe("DELETE FROM clima_mensal") is False

def test_drop_bloqueado():
    assert _is_safe("DROP TABLE clima_mensal") is False

def test_update_bloqueado():
    assert _is_safe("UPDATE clima_mensal SET temp_media = 30") is False


# teste de execução com mock — patcha os imports dentro do método _init()

def test_sql_tool_retorna_resultado():
    from tools.sql_query import SQLQueryTool

    tool = SQLQueryTool()

    # mock do LLM
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(
        content="SELECT nome_mes, temp_media FROM clima_mensal LIMIT 3"
    )

    # mock das tools do toolkit
    mock_query_tool = MagicMock()
    mock_query_tool.name = "sql_db_query"
    mock_query_tool.invoke.return_value = "[('Janeiro', 26.0), ('Fevereiro', 25.8)]"

    mock_info_tool = MagicMock()
    mock_info_tool.name = "sql_db_schema"
    mock_info_tool.invoke.return_value = "CREATE TABLE clima_mensal ..."

    mock_toolkit = MagicMock()
    mock_toolkit.get_tools.return_value = [mock_query_tool, mock_info_tool]

    # injeta mocks diretamente no objeto (bypass do _init)
    tool._db          = MagicMock()
    tool._llm         = mock_llm
    tool._toolkit     = mock_toolkit
    tool._query_tool  = mock_query_tool
    tool._info_tool   = mock_info_tool

    result = tool.run("Qual a temperatura média em janeiro?")

    assert "SELECT" in result
    assert "Resultado" in result
