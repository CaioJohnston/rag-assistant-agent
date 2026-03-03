import os
from typing import List, Dict
from dotenv import load_dotenv
import requests

load_dotenv()

class SerpAPIETool:
    def __init__(self, k: int = 5):
        self.k = k
        self.api_key = os.getenv("SERPAPI_API_KEY")

        if not self.api_key:
            raise ValueError("SERPAPI_API_KEY not found in .env")

        self.url = "https://google.serper.dev/search"

    def search_web(self, query: str) -> List[Dict]:
        payload = {"q": query}

        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

        response = requests.post(
            self.url,
            json=payload,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        organic = data.get("organic", [])[: self.k]

        normalized = [
            {
                "title": r.get("title"),
                "link": r.get("link"),
                "snippet": r.get("snippet"),
            }
            for r in organic
        ]

        return normalized