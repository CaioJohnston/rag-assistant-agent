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


# teste de execução com mock

def test_sql_tool_retorna_resultado():
    with patch("tools.sql_query.SQLDatabase"), \
         patch("tools.sql_query.AzureChatOpenAI") as mock_llm_cls, \
         patch("tools.sql_query.SQLDatabaseToolkit") as mock_toolkit_cls:

        # mock do LLM gerando SQL válido
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="SELECT nome_mes, temp_media FROM clima_mensal LIMIT 3"
        )
        mock_llm_cls.return_value = mock_llm

        # mock do toolkit retornando resultado
        mock_query_tool = MagicMock()
        mock_query_tool.name = "sql_db_query"
        mock_query_tool.invoke.return_value = "[('Janeiro', 26.0), ('Fevereiro', 25.8)]"

        mock_info_tool = MagicMock()
        mock_info_tool.name = "sql_db_schema"
        mock_info_tool.invoke.return_value = "CREATE TABLE clima_mensal ..."

        mock_toolkit = MagicMock()
        mock_toolkit.get_tools.return_value = [mock_query_tool, mock_info_tool]
        mock_toolkit_cls.return_value = mock_toolkit

        from tools.sql_query import SQLQueryTool
        tool = SQLQueryTool()
        result = tool.run("Qual a temperatura média em janeiro?")

        assert "SELECT" in result
        assert "Resultado" in result
