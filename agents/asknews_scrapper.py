from typing import List, Literal

from config import BotConfig

from asknews_sdk import AskNewsSDK



class AskNewsScrapper:
    def __init__(self, bot_config: BotConfig, scopes: List[Literal["news"]] = ["news"]):
        self._ask_news_engine = AskNewsSDK(
            client_id=bot_config.asknews_client_id,
            client_secret=bot_config.asknews_secret,
            scopes=scopes,
        )

    def get_latest_news(self, query: str, n_articles: int):
        return self._ask_news_engine.news.search_news(
            query=query,  # your natural language query
            n_articles=n_articles,  # control the number of articles to include in the context, originally 5
            return_type="both",
            strategy="latest news"  # enforces looking at the latest news only
        )

    def get_historical_news(self, query: str, n_articles: int):
        return self._ask_news_engine.news.search_news(
            query=query,
            n_articles=n_articles,
            return_type="both",
            strategy="news knowledge"  # looks for relevant news within the past 60 days
        )
