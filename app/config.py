"""
config.py — Carrega e valida todas as variáveis de ambiente do projeto.

Usar sempre: from app.config import settings
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ── OpenAI ───────────────────────────────
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # ── Serper (Google Search) ────────────────
    SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY", "")

    # ── Azure AI Search ───────────────────────
    AZURE_SEARCH_ENDPOINT: str = os.getenv("AZURE_SEARCH_ENDPOINT", "")
    AZURE_SEARCH_KEY: str = os.getenv("AZURE_SEARCH_KEY", "")
    AZURE_SEARCH_INDEX: str = os.getenv("AZURE_SEARCH_INDEX", "rag-index")

    # ── Azure OpenAI (Foundry) ────────────────
    AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_KEY: str = os.getenv("AZURE_OPENAI_KEY", "")
    AZURE_OPENAI_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    # ── PostgreSQL ────────────────────────────
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "ragdb")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "postgres")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")

    @property
    def POSTGRES_URI(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── OpenWeatherMap ────────────────────────
    OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")

    # ── LangSmith ────────────────────────────
    LANGCHAIN_API_KEY: str = os.getenv("LANGCHAIN_API_KEY", "")
    LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "rag-assistant")
    LANGCHAIN_TRACING_V2: str = os.getenv("LANGCHAIN_TRACING_V2", "true")

    # ── Streamlit ────────────────────────────
    STREAMLIT_PORT: str = os.getenv("STREAMLIT_PORT", "8501")

    def validate(self):
        """Lança erro se alguma variável obrigatória estiver faltando."""
        required = {
            "OPENAI_API_KEY": self.OPENAI_API_KEY,
            "SERPAPI_API_KEY": self.SERPAPI_API_KEY,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise EnvironmentError(
                f"Variáveis de ambiente obrigatórias não encontradas: {missing}"
            )


settings = Settings()
