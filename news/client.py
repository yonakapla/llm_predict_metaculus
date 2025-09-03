import aiohttp
from typing import Any, Dict, List, Optional


class AskNewsClient:
    """Simple aiohttp based client for the AskNews API."""

    API_BASE_URL = "https://api.asknews.app/v1"

    def __init__(self, client_id: str, client_secret: str, session: Optional[aiohttp.ClientSession] = None) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        if session is None:
            self.session = aiohttp.ClientSession()
            self._owns_session = True
        else:
            self.session = session
            self._owns_session = False
        self._token: Optional[str] = None

    async def close(self) -> None:
        if self._owns_session:
            await self.session.close()

    async def _ensure_token(self) -> str:
        if self._token:
            return self._token
        token_url = f"{self.API_BASE_URL}/oauth/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        async with self.session.post(token_url, data=data) as resp:
            resp.raise_for_status()
            body = await resp.json()
            self._token = body.get("access_token")
            return self._token

    async def search_news(self, query: str, *, n_articles: int = 5, return_type: str = "both", strategy: str = "latest news") -> Dict[str, Any]:
        token = await self._ensure_token()
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "query": query,
            "n_articles": n_articles,
            "return_type": return_type,
            "strategy": strategy,
        }
        url = f"{self.API_BASE_URL}/news/search"
        async with self.session.get(url, params=params, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()
