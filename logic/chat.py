import datetime
import json
import re
from typing import List, Dict

from autogen_agentchat.agents import AssistantAgent

from utils.PROMPTS import NEWS_STEP_INSTRUCTIONS


async def run_first_stage_forecasters(
    forecasters: List[AssistantAgent],
    prompt: str,
    system_message: str = "",
    options: List[str] = "",
) -> Dict[str, dict]:
    today_date = datetime.datetime.now().strftime("%Y-%m-%d")
    phase_one_introduction = f"'{prompt}'"

    if options:
        phase_one_introduction += f"\n\nOptions:\n\n{', '.join(options)}\n"

    analyses = await gather_forecasts(forecasters, system_message, phase_one_introduction)
    if len(forecasters) == 1:
        return analyses.get(forecasters[0].name, {})
    return analyses

async def run_revised_stage_forecasters(
    forecasters: List[AssistantAgent],
    prompt: str,
    system_message: str = "",
    options: List[str] = "",
) -> Dict[str, dict]:
    today_date = datetime.datetime.now().strftime("%Y-%m-%d")
    revision_phase_introduction = f"'{prompt}'"

    if options:
        revision_phase_introduction += f"\n\nOptions:\n\n{', '.join(options)}\n"

    analyses = await gather_forecasts(
        forecasters, system_message, revision_phase_introduction
    )
    if len(forecasters) == 1:
        return analyses.get(forecasters[0].name, {})
    return analyses


async def run_second_stage_forecasters(
    forecasters: List[AssistantAgent],
    prompt: str = NEWS_STEP_INSTRUCTIONS,
) -> Dict[str, dict]:
    phase_two_instruction_news_analysis = f"Please revise your answer based on previous steps."
    analyses = await gather_forecasts(
        forecasters, prompt, phase_two_instruction_news_analysis
    )
    if len(forecasters) == 1:
        return analyses.get(forecasters[0].name, {})
    return analyses


async def forecast(forecaster: AssistantAgent, phase_instructions: str, phase_introduction: str) -> Dict[str, dict]:
    result = await forecaster.run(task=f"{phase_instructions}\n \n{phase_introduction}"
    )
    if result:
        return validate_and_parse_response(result.messages[1].content)


async def gather_forecasts(
    forecasters: List[AssistantAgent],
    system_message: str,
    phase_introduction: str,
) -> Dict[str, dict]:
    results: Dict[str, dict] = {}
    for forecaster in forecasters:
        try:
            forecast_result = await forecast(
                forecaster, system_message, phase_introduction
            )
            if forecast_result is not None:
                results[forecaster.name] = forecast_result
        except Exception as e:
            print(f"Error with {forecaster.name}: {e}\n\n")
            print(f"Skipping forecaster:\n{forecaster.name}")
    return results


def validate_and_parse_response(response):
    try:
        response = response.replace("json", "").replace("```", "").replace("\n", "")
        if not response.endswith("}"):
            ind = find_last_curly_brace_position(response)
            response = response[:ind + 1]

        return json.loads(response)

    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON response: {response}")


def find_last_curly_brace_position(text):
    matches = list(re.finditer(r'}', text))  # Find all closing curly braces
    if matches:
        last_position = matches[-1].start()  # Get the start position of the last match
        return last_position
    else:
        return -1  # Return -1 if no curly brace is found
