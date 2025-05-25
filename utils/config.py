from typing import Dict, Any

from config import BotConfig



def get_gpt_config(cache_seed: int, temperature: float, model: str, timeout: int,
                   bot_config: BotConfig) -> Dict[str, Any]:
    """Build an LLM config using the API key from ``bot_config``."""

    return {
        "cache_seed": cache_seed,
        "temperature": temperature,
        "config_list": [
            {
                "model": model,
                "api_key": bot_config.openai_api_key,
                "response_format": {"type": "json_object"},
            }
        ],
        "timeout": timeout,
    }
