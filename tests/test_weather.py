"""
tests/test_weather.py — Testes unitários da tool OpenWeatherMap.
"""

from unittest.mock import patch, MagicMock
from tools.weather import OpenWeatherTool, WeatherInput, WeatherResult, ForecastDay
from agents.orchestrator_agent import _extract_city


# testes de extração de cidade — sem I/O

def test_extract_city_com_em():
    assert _extract_city("Como está o tempo em São Paulo?") == "São Paulo"

def test_extract_city_com_para():
    assert _extract_city("previsão para Londres") == "Londres"

def test_extract_city_fallback():
    assert _extract_city("como está o tempo?") == "Belem,BR"


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


def test_weather_retorna_resultado_tipado():
    tool = OpenWeatherTool()
    tool.api_key = "fake-key"

    with patch("tools.weather.requests.get", side_effect=[
        _mock_geocode_response(),
        _mock_current_response(),
        _mock_forecast_response(),
    ]):
        result = tool.run(WeatherInput(city="Belém"))

    assert isinstance(result, WeatherResult)
    assert result.city_name == "Belém"
    assert result.temp == 30.5
    assert result.feels_like == 35.0
    assert result.humidity == 85
    assert result.wind_speed == 1.5
    assert result.error is None
    assert len(result.forecast) == 2
    assert isinstance(result.forecast[0], ForecastDay)
    assert result.forecast[0].temp == 29.0

    # __str__ preserva o formato legível
    text = str(result)
    assert "Belém" in text
    assert "30.5" in text
    assert "85%" in text
    assert "Previsão" in text


def test_weather_sem_api_key():
    tool = OpenWeatherTool()
    tool.api_key = ""
    result = tool.run(WeatherInput(city="Belém"))

    assert isinstance(result, WeatherResult)
    assert result.error is not None
    assert "OPENWEATHER_API_KEY" in result.error


def test_weather_cidade_invalida():
    tool = OpenWeatherTool()
    tool.api_key = "fake-key"

    mock_empty = MagicMock()
    mock_empty.json.return_value = []
    mock_empty.raise_for_status = MagicMock()

    with patch("tools.weather.requests.get", return_value=mock_empty):
        result = tool.run(WeatherInput(city="CidadeQueNaoExiste"))

    assert isinstance(result, WeatherResult)
    assert result.error is not None
    assert "não encontrada" in result.error
