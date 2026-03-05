"""
tools/weather.py — Previsão do tempo via OpenWeatherMap API.

Fluxo:
  cidade (str) → geocoding API → lat/lon → forecast API → resumo formatado

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
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv(override=True)

BASE_URL     = "https://api.openweathermap.org"
DEFAULT_CITY = "Belém,BR"   # cidade padrão — coerente com o domínio do projeto
TIMEOUT      = 10


class OpenWeatherTool:
    """
    Consulta condições atuais e previsão de 5 dias para uma cidade.
    Entrada : nome da cidade (str), ex: "Belém", "São Paulo", "London"
    Saída   : resumo formatado (str)
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

    def run(self, city: str = DEFAULT_CITY) -> str:
        if not self.api_key:
            return "OPENWEATHER_API_KEY não configurada."

        try:
            lat, lon, city_name = self._geocode(city)
            current  = self._current(lat, lon)
            forecast = self._forecast(lat, lon)
        except ValueError as e:
            return str(e)
        except requests.exceptions.RequestException as e:
            return f"Erro ao consultar OpenWeatherMap: {e}"

        # formata condições atuais
        c     = current["main"]
        wind  = current["wind"]
        desc  = current["weather"][0]["description"].capitalize()
        lines = [
            f"**{city_name}** — condições atuais",
            f"Temperatura: {c['temp']:.1f}°C (sensação {c['feels_like']:.1f}°C)",
            f"Umidade: {c['humidity']}%",
            f"Vento: {wind['speed']} m/s",
            f"{desc}",
            "",
            "**Previsão dos próximos dias:**",
        ]

        for day in forecast:
            date  = day["dt_txt"][:10]
            temp  = day["main"]["temp"]
            descr = day["weather"][0]["description"].capitalize()
            lines.append(f"  • {date}: {temp:.1f}°C — {descr}")

        return "\n".join(lines)


# instância global
weather_tool = OpenWeatherTool()


@tool
def get_weather(city: str = DEFAULT_CITY) -> str:
    """
    Retorna condições climáticas atuais e previsão de 5 dias para uma cidade.
    Use quando o usuário perguntar sobre clima atual, temperatura, chuva ou previsão do tempo.
    Exemplos: "Como está o tempo em Belém?", "Vai chover em São Paulo?"
    """
    return weather_tool.run(city)
