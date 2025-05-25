from typing import Tuple, Dict, List, Union

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - minimal fallback for tests
    import statistics as _stats

    class _NP:
        @staticmethod
        def mean(data):
            return _stats.mean(data)

        @staticmethod
        def std(data, ddof=0):
            if len(data) < 2:
                return 0.0
            return _stats.stdev(data)

    np = _NP()

from agents.agent_creator import (
    create_summarization_assistant,
)
from logic.call_asknews import run_research
from logic.summarization import run_summarization_phase
from logic.utils import build_and_write_json, extract_probabilities, perform_forecasting_phase, create_experts, \
    extract_question_details, identify_experts, strip_title_to_filename, get_all_experts
from utils.config import get_gpt_config
from config import BotConfig
from utils.utils import normalize_and_average


async def forecast_single_question(
        question_details: dict,
        bot_config: BotConfig,
        cache_seed: int = 42,
        is_multiple_choice: bool = False,
        options: List[str] = None,
        is_woc:bool=False,
        num_of_experts:str|None = None,
        news: str = None
) -> Tuple[Union[int, Dict[str, float]], str]:
    title, description, fine_print, resolution_criteria, forecast_date = extract_question_details(question_details)
    config = get_gpt_config(cache_seed, 0.7, "gpt-4o", 120, bot_config)

    if not is_woc:
        # Extract news
        news = await run_research(question_details, bot_config)

    # Identify and create experts
    all_experts = await get_all_experts(
        config,
        question_details,
        is_multiple_choice,
        options,
        is_woc,
        num_of_experts,
        bot_config,
    )


    # Forecasting
    results = await perform_forecasting_phase(all_experts, question_details, news=news,
                                              is_multiple_choice=is_multiple_choice, options=options)

    # Extract probabilities
    final_probability = [result['final_probability'] for result in results.values() if 'final_probability' in result]
    initial_probability = [result['initial_probability'] for result in results.values() if 'initial_probability' in result]

    # Summarization
    summarization_assistant = create_summarization_assistant(config, bot_config)
    summarization = await run_summarization_phase(results, question_details,
                                                  summarization_assistant,news)

    # Compute final probabilities
    final_result = int(round(np.mean(final_probability))) if not is_multiple_choice else {
        opt: val / 100.0 for opt, val in normalize_and_average(final_probability, options=options).items()
    }

    sd_first_step = np.std(initial_probability, ddof=1)
    sd_second_step = np.std(final_probability, ddof=1)
    mean_first_step = np.mean(initial_probability)
    mean_second_step = np.mean(final_probability)

    # Build final JSON
    final_json = {
        "question_details": question_details,
        "date": forecast_date, "news": news,
        "results": results,
        "summary": summarization,
        "statistics": {"mean_first_step": mean_first_step, "mean_second_step": mean_second_step,
                       "sd_first_step": sd_first_step, "sd_second_step": sd_second_step,
                       "final_result": final_result},
    }

    # Save JSON
    filename = strip_title_to_filename(title)
    await build_and_write_json(filename, final_json, is_woc)

    return final_result, summarization
