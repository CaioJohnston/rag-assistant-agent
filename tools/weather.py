"""
tools/weather.py — Previsão do tempo via OpenWeatherMap API.

Fluxo:
  WeatherInput(city) → geocoding API → lat/lon → forecast API → WeatherResult

Endpoints usados (ambos free tier):
  - api.openweathermap.org/geo/1.0/direct   → resolve cidade para lat/lon
  - api.openweathermap.org/data/2.5/weather → condições atuais
  - api.openweathermap.org/data/2.5/forecast → previsão 5 dias (blocos de 3h)

Segurança:
  - timeout de 10s por request
  - rate limit: free tier suporta 60 calls/min — sem necessidade de throttle aqui
"""

import os
import requests
from dataclasses import dataclass, field
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv(override=True)

BASE_URL     = "https://api.openweathermap.org"
DEFAULT_CITY = "Belém,BR"   # cidade padrão — coerente com o domínio do projeto
TIMEOUT      = 10


# ── dataclasses de entrada e saída ────────────────────────────────────────────

@dataclass
class WeatherInput:
    """Entrada tipada para a tool de previsão do tempo."""
    city: str = DEFAULT_CITY


@dataclass
class ForecastDay:
    """Previsão para um dia específico."""
    date: str = ""
    temp: float = 0.0
    description: str = ""


@dataclass
class WeatherResult:
    """Saída tipada da tool de previsão do tempo."""
    city_name: str = ""
    temp: float = 0.0
    feels_like: float = 0.0
    humidity: int = 0
    wind_speed: float = 0.0
    description: str = ""
    forecast: list[ForecastDay] = field(default_factory=list)
    error: str | None = None

    def __str__(self) -> str:
        if self.error:
            return self.error
        lines = [
            f"**{self.city_name}** — condições atuais",
            f"Temperatura: {self.temp:.1f}°C (sensação {self.feels_like:.1f}°C)",
            f"Umidade: {self.humidity}%",
            f"Vento: {self.wind_speed} m/s",
            f"{self.description}",
            "",
            "**Previsão dos próximos dias:**",
        ]
        for day in self.forecast:
            lines.append(f"  • {day.date}: {day.temp:.1f}°C — {day.description}")
        return "\n".join(lines)


# ── tool class ────────────────────────────────────────────────────────────────

class OpenWeatherTool:
    """
    Consulta condições atuais e previsão de 5 dias para uma cidade.
    Entrada : WeatherInput (dataclass com campo city)
    Saída   : WeatherResult (dataclass tipada)
    """

    def __init__(self):
        self.api_key = os.getenv("OPENWEATHER_API_KEY", "")

    def _geocode(self, city: str) -> tuple[float, float, str]:
        """Converte nome de cidade em lat/lon via Geocoding API."""
        resp = requests.get(
            f"{BASE_URL}/geo/1.0/direct",
            params={"q": city, "limit": 1, "appid": self.api_key},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data:
            raise ValueError(f"Cidade '{city}' não encontrada.")

        return data[0]["lat"], data[0]["lon"], data[0].get("name", city)

    def _current(self, lat: float, lon: float) -> dict:
        """Busca condições climáticas atuais."""
        resp = requests.get(
            f"{BASE_URL}/data/2.5/weather",
            params={
                "lat": lat, "lon": lon,
                "appid": self.api_key,
                "units": "metric",
                "lang": "pt_br",
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def _forecast(self, lat: float, lon: float) -> list[dict]:
        """Busca previsão dos próximos 5 dias (blocos de 3h) e retorna 1 por dia."""
        resp = requests.get(
            f"{BASE_URL}/data/2.5/forecast",
            params={
                "lat": lat, "lon": lon,
                "appid": self.api_key,
                "units": "metric",
                "lang": "pt_br",
                "cnt": 40,   # 5 dias × 8 blocos de 3h
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        items = resp.json().get("list", [])

        # pega um bloco por dia (ao meio-dia) para resumir a previsão
        seen_days = set()
        daily = []
        for item in items:
            day = item["dt_txt"][:10]
            hour = item["dt_txt"][11:13]
            if day not in seen_days and hour in ("12", "11", "13"):
                seen_days.add(day)
                daily.append(item)

        return daily[:5]

    def run(self, input: WeatherInput) -> WeatherResult:
        """Executa a consulta e retorna WeatherResult tipado."""
        if not self.api_key:
            return WeatherResult(error="OPENWEATHER_API_KEY não configurada.")

        try:
            lat, lon, city_name = self._geocode(input.city)
            current  = self._current(lat, lon)
            forecast = self._forecast(lat, lon)
        except ValueError as e:
            return WeatherResult(error=str(e))
        except requests.exceptions.RequestException as e:
            return WeatherResult(error=f"Erro ao consultar OpenWeatherMap: {e}")

        c    = current["main"]
        wind = current["wind"]
        desc = current["weather"][0]["description"].capitalize()

        return WeatherResult(
            city_name=city_name,
            temp=c["temp"],
            feels_like=c["feels_like"],
            humidity=c["humidity"],
            wind_speed=wind["speed"],
            description=desc,
            forecast=[
                ForecastDay(
                    date=d["dt_txt"][:10],
                    temp=d["main"]["temp"],
                    description=d["weather"][0]["description"].capitalize(),
                )
                for d in forecast
            ],
        )


# instância global
weather_tool = OpenWeatherTool()


@tool
def get_weather(city: str = DEFAULT_CITY) -> str:
    """
    Retorna condições climáticas atuais e previsão de 5 dias para uma cidade.
    Use quando o usuário perguntar sobre clima atual, temperatura, chuva ou previsão do tempo.
    Exemplos: "Como está o tempo em Belém?", "Vai chover em São Paulo?"
    """
    return str(weather_tool.run(WeatherInput(city=city)))
