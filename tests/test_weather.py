"""
tests/test_weather.py — Testes unitários da tool OpenWeatherMap.
"""

from unittest.mock import patch, MagicMock
from tools.weather import OpenWeatherTool
from graph.nodes import _extract_city


# testes de extração de cidade — sem I/O

def test_extract_city_com_em():
    assert _extract_city("Como está o tempo em São Paulo?") == "São Paulo"

def test_extract_city_com_para():
    assert _extract_city("previsão para Londres") == "Londres"

def test_extract_city_fallback():
    assert _extract_city("como está o tempo?") == "Belém,BR"


# testes da tool com mock da API

def _mock_geocode_response():
    mock = MagicMock()
    mock.json.return_value = [{"lat": -1.45, "lon": -48.5, "name": "Belém"}]
    mock.raise_for_status = MagicMock()
    return mock

def _mock_current_response():
    mock = MagicMock()
    mock.json.return_value = {
        "main": {"temp": 30.5, "feels_like": 35.0, "humidity": 85},
        "wind": {"speed": 1.5},
        "weather": [{"description": "chuva leve"}],
    }
    mock.raise_for_status = MagicMock()
    return mock

def _mock_forecast_response():
    mock = MagicMock()
    mock.json.return_value = {
        "list": [
            {
                "dt_txt": "2026-03-05 12:00:00",
                "main": {"temp": 29.0},
                "weather": [{"description": "nublado"}],
            },
            {
                "dt_txt": "2026-03-06 12:00:00",
                "main": {"temp": 31.0},
                "weather": [{"description": "céu limpo"}],
            },
        ]
    }
    mock.raise_for_status = MagicMock()
    return mock


def test_weather_retorna_resumo():
    tool = OpenWeatherTool()
    tool.api_key = "fake-key"

    with patch("tools.weather.requests.get", side_effect=[
        _mock_geocode_response(),
        _mock_current_response(),
        _mock_forecast_response(),
    ]):
        result = tool.run("Belém")

    assert "Belém" in result
    assert "30.5" in result
    assert "85%" in result
    assert "Previsão" in result


def test_weather_sem_api_key():
    tool = OpenWeatherTool()
    tool.api_key = ""
    result = tool.run("Belém")
    assert "OPENWEATHER_API_KEY" in result


def test_weather_cidade_invalida():
    tool = OpenWeatherTool()
    tool.api_key = "fake-key"

    mock_empty = MagicMock()
    mock_empty.json.return_value = []
    mock_empty.raise_for_status = MagicMock()

    with patch("tools.weather.requests.get", return_value=mock_empty):
        result = tool.run("CidadeQueNaoExiste")

    assert "não encontrada" in result
