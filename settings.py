from dataclasses import dataclass
import os

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - fallback if dotenv isn't installed
    def load_dotenv() -> None:  # type: ignore
        return None


def _get_bool(name: str) -> bool:
    return os.getenv(name, "false").lower() == "true"


@dataclass
class Settings:
    submit_prediction: bool
    use_example_questions: bool
    skip_previously_forecasted_questions: bool
    metaculus_token: str | None
    asknews_client_id: str | None
    asknews_secret: str | None
    openai_api_key: str | None


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        submit_prediction=_get_bool("SUBMIT_PREDICTION"),
        use_example_questions=_get_bool("USE_EXAMPLE_QUESTIONS"),
        skip_previously_forecasted_questions=_get_bool("SKIP_PREVIOUSLY_FORECASTED_QUESTIONS"),
        metaculus_token=os.getenv("METACULUS_TOKEN"),
        asknews_client_id=os.getenv("ASKNEWS_CLIENT_ID"),
        asknews_secret=os.getenv("ASKNEWS_SECRET"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )

settings = load_settings()

