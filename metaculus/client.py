import aiohttp
from typing import Any, Dict, List, Optional

class MetaculusClient:
    """Asynchronous client for the Metaculus API."""

    API_BASE_URL = "https://www.metaculus.com/api"

    def __init__(self, token: str, session: Optional[aiohttp.ClientSession] = None) -> None:
        self.token = token
        if session is None:
            headers = {"Authorization": f"Token {token}"}
            self.session = aiohttp.ClientSession(headers=headers)
            self._owns_session = True
        else:
            self.session = session
            self._owns_session = False

    async def close(self) -> None:
        if self._owns_session:
            await self.session.close()

    async def list_posts_from_tournament(
        self,
        tournament_id: int,
        offset: int = 0,
        count: int = 50,
    ) -> Dict[str, Any]:
        params = {
            "limit": count,
            "offset": offset,
            "order_by": "-hotness",
            "forecast_type": ",".join(["binary", "multiple_choice", "numeric"]),
            "tournaments": [tournament_id],
            "statuses": "open",
            "include_description": "true",
        }
        url = f"{self.API_BASE_URL}/posts/"
        async with self.session.get(url, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_post_details(self, post_id: int) -> Dict[str, Any]:
        url = f"{self.API_BASE_URL}/posts/{post_id}/"
        async with self.session.get(url) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def post_question_comment(self, post_id: int, comment_text: str) -> None:
        url = f"{self.API_BASE_URL}/comments/create/"
        payload = {
            "text": comment_text,
            "parent": None,
            "included_forecast": True,
            "is_private": True,
            "on_post": post_id,
        }
        async with self.session.post(url, json=payload) as resp:
            if resp.status >= 400:
                raise RuntimeError(await resp.text())

    async def post_question_prediction(self, question_id: int, forecast_payload: Dict[str, Any]) -> None:
        url = f"{self.API_BASE_URL}/questions/forecast/"
        data = [{"question": question_id, **forecast_payload}]
        async with self.session.post(url, json=data) as resp:
            print(f"Prediction Post status code: {resp.status}")
            if resp.status >= 400:
                raise RuntimeError(await resp.text())
