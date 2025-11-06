import logging
import os
from typing import List, Tuple, Optional

import dotenv
import requests

from main import forecast_individual_question


dotenv.load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MetaculusClient:
    """Minimal client for interacting with the Metaculus API."""

    API_BASE_URL = "https://www.metaculus.com/api"

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("METACULUS_TOKEN")
        if not self.token:
            raise ValueError("METACULUS_TOKEN environment variable not set")
        self._auth = {"headers": {"Authorization": f"Token {self.token}"}}

    def list_posts(self, tournament_id: int, offset: int = 0, count: int = 50) -> dict:
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
        resp = requests.get(url, **self._auth, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_post_details(self, post_id: int) -> dict:
        url = f"{self.API_BASE_URL}/posts/{post_id}/"
        resp = requests.get(url, **self._auth)
        resp.raise_for_status()
        return resp.json()

    def get_open_questions(self, tournament_id: int) -> List[Tuple[int, int]]:
        posts = self.list_posts(tournament_id)
        post_dict = {}
        for post in posts.get("results", []):
            if question := post.get("question"):
                post_dict[post["id"]] = [question]

        open_questions: List[Tuple[int, int]] = []
        for post_id, questions in post_dict.items():
            for q in questions:
                if q.get("status") == "open":
                    open_questions.append((q["id"], post_id))
        return open_questions


class Forecaster:
    """Wrapper around forecast_individual_question from main.py."""

    def __init__(
        self,
        submit_prediction: bool = False,
        skip_previously_forecasted: bool = True,
        cache_seed: int = 42,
        use_hyde: bool = True,
    ):
        self.submit_prediction = submit_prediction
        self.skip_previously_forecasted = skip_previously_forecasted
        self.cache_seed = cache_seed
        self.use_hyde = use_hyde

    async def forecast(self, question_id: int, post_id: int) -> str:
        return await forecast_individual_question(
            question_id=question_id,
            post_id=post_id,
            submit_prediction=self.submit_prediction,
            skip_previously_forecasted_questions=self.skip_previously_forecasted,
            cache_seed=self.cache_seed,
            use_hyde=self.use_hyde,
        )


class ForecastBot:
    """High level orchestration of the forecasting process."""

    def __init__(
        self,
        tournament_id: int,
        submit_prediction: bool = False,
        skip_previously_forecasted: bool = True,
        cache_seed: int = 42,
        use_hyde: bool = True,
    ):
        self.tournament_id = tournament_id
        self.client = MetaculusClient()
        self.forecaster = Forecaster(
            submit_prediction=submit_prediction,
            skip_previously_forecasted=skip_previously_forecasted,
            cache_seed=cache_seed,
            use_hyde=use_hyde,
        )

    async def run(self) -> None:
        logger.info("Retrieving open questions for tournament %s", self.tournament_id)
        questions = self.client.get_open_questions(self.tournament_id)
        logger.info("%d open questions found", len(questions))
        for question_id, post_id in questions:
            try:
                summary = await self.forecaster.forecast(question_id, post_id)
                logger.info(summary)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Error forecasting question %s: %s", question_id, exc)


