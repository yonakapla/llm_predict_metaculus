from dataclasses import dataclass
import os

@dataclass
class BotConfig:
    submit_prediction: bool
    use_example_questions: bool
    skip_previously_forecasted_questions: bool
    metaculus_token: str | None
    asknews_client_id: str | None
    asknews_secret: str | None
    openai_api_key: str | None

    @classmethod
    def from_env(cls) -> "BotConfig":
        return cls(
            submit_prediction=os.getenv("SUBMIT_PREDICTION", "false").lower() == "true",
            use_example_questions=os.getenv("USE_EXAMPLE_QUESTIONS", "false").lower() == "true",
            skip_previously_forecasted_questions=os.getenv("SKIP_PREVIOUSLY_FORECASTED_QUESTIONS", "false").lower() == "true",
            metaculus_token=os.getenv("METACULUS_TOKEN"),
            asknews_client_id=os.getenv("ASKNEWS_CLIENT_ID"),
            asknews_secret=os.getenv("ASKNEWS_SECRET"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
        )
