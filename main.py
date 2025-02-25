import asyncio
import datetime
import json
import os
import re
from random import randint
from time import sleep

import dotenv

from logic.forecase_single_question import forecast_single_binary_question, forecast_single_multiple_choice_question

dotenv.load_dotenv()

from openai import AsyncOpenAI
import numpy as np
import requests
from asknews_sdk import AskNewsSDK

######################### CONSTANTS #########################
# Constants
SUBMIT_PREDICTION = True  # set to True to publish your predictions to Metaculus
USE_EXAMPLE_QUESTIONS = False# set to True to forecast example questions rather than the tournament questions
FORECAST_BINARY = True  # set to True to forecast binary questions
FORECAST_MULTIPLE_CHOICE = False  # set to True to forecast multiple choice questions
NUM_RUNS_PER_QUESTION = 1  # The median forecast is taken between NUM_RUNS_PER_QUESTION runs
SKIP_PREVIOUSLY_FORECASTED_QUESTIONS = True
GET_NEWS = True  # set to True to enable the bot to do online research

# Environment variables

METACULUS_TOKEN = os.getenv("METACULUS_TOKEN")
ASKNEWS_CLIENT_ID = os.getenv("ASKNEWS_CLIENT_ID")
ASKNEWS_SECRET = os.getenv("ASKNEWS_SECRET")
OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY")

# The tournament IDs below can be used for testing your bot.
Q4_2024_AI_BENCHMARKING_ID = 32506
Q1_2025_AI_BENCHMARKING_ID = 32627
Q4_2024_QUARTERLY_CUP_ID = 3672
Q1_2025_QUARTERLY_CUP_ID = 32630
AXC_2025_TOURNAMENT_ID = 32564
GIVEWELL_ID = 3600
RESPIRATORY_OUTLOOK_ID = 3411

CACHE_SEED = 42

TOURNAMENT_ID = Q1_2025_AI_BENCHMARKING_ID

# The example questions can be used for testing your bot. (note that question and post id are not always the same)
EXAMPLE_QUESTIONS = [  # (question_id, post_id)
    # (578, 578),  # Human Extinction - Binary - https://www.metaculus.com/questions/578/human-extinction-by-2100/
    # (14333, 14333),  # Age of Oldest Human - Numeric - https://www.metaculus.com/questions/14333/age-of-oldest-human-as-of-2100/
    (22427, 22427),
    # Number of New Leading AI Labs - Multiple Choice - https://www.metaculus.com/questions/22427/number-of-new-leading-ai-labs/
]

######################### HELPER FUNCTIONS #########################

# @title Helper functions
AUTH_HEADERS = {"headers": {"Authorization": f"Token {METACULUS_TOKEN}"}}
API_BASE_URL = "https://www.metaculus.com/api"


def post_question_comment(post_id: int, comment_text: str) -> None:
    """
    Post a comment on the question page as the bot user.
    """

    response = requests.post(
        f"{API_BASE_URL}/comments/create/",
        json={
            "text": comment_text,
            "parent": None,
            "included_forecast": True,
            "is_private": True,
            "on_post": post_id,
        },
        **AUTH_HEADERS,  # type: ignore
    )
    if not response.ok:
        raise RuntimeError(response.text)


def post_question_prediction(question_id: int, forecast_payload: dict) -> None:
    """
    Post a forecast on a question.
    """
    url = f"{API_BASE_URL}/questions/forecast/"
    response = requests.post(
        url,
        json=[
            {
                "question": question_id,
                **forecast_payload,
            },
        ],
        **AUTH_HEADERS,  # type: ignore
    )
    print(f"Prediction Post status code: {response.status_code}")
    if not response.ok:
        raise RuntimeError(response.text)


def create_forecast_payload(
        forecast: float | dict[str, float] | list[float],
        question_type: str,
) -> dict:
    """
    Accepts a forecast and generates the api payload in the correct format.

    If the question is binary, forecast must be a float.
    If the question is multiple choice, forecast must be a dictionary that
      maps question.options labels to floats.
    If the question is numeric, forecast must be a dictionary that maps
      quartiles or percentiles to datetimes, or a 201 value cdf.
    """
    if question_type == "binary":
        return {
            "probability_yes": forecast,
            "probability_yes_per_category": None,
            "continuous_cdf": None,
        }
    if question_type == "multiple_choice":
        return {
            "probability_yes": None,
            "probability_yes_per_category": forecast,
            "continuous_cdf": None,
        }
    # numeric or date
    return {
        "probability_yes": None,
        "probability_yes_per_category": None,
        "continuous_cdf": forecast,
    }


def list_posts_from_tournament(
        tournament_id: int = TOURNAMENT_ID, offset: int = 0, count: int = 50
) -> list[dict]:
    """
    List (all details) {count} posts from the {tournament_id}
    """
    url_qparams = {
        "limit": count,
        "offset": offset,
        "order_by": "-hotness",
        "forecast_type": ",".join(
            [
                "binary",
                "multiple_choice",
                "numeric",
            ]
        ),
        "tournaments": [tournament_id],
        "statuses": "open",
        "include_description": "true",
    }
    url = f"{API_BASE_URL}/posts/"
    response = requests.get(url, **AUTH_HEADERS, params=url_qparams)  # type: ignore
    if not response.ok:
        raise Exception(response.text)
    data = json.loads(response.content)
    return data


def get_open_question_ids_from_tournament() -> list[tuple[int, int]]:
    posts = list_posts_from_tournament()

    post_dict = dict()
    for post in posts["results"]:
        if question := post.get("question"):
            # single question post
            post_dict[post["id"]] = [question]

    open_question_id_post_id = []  # [(question_id, post_id)]
    for post_id, questions in post_dict.items():
        for question in questions:
            if question.get("status") == "open":
                print(
                    f"ID: {question['id']}\nQ: {question['title']}\nCloses: "
                    f"{question['scheduled_close_time']}"
                )
                open_question_id_post_id.append((question["id"], post_id))

    return open_question_id_post_id


def get_post_details(post_id: int) -> dict:
    """
    Get all details about a post from the Metaculus API.
    """
    url = f"{API_BASE_URL}/posts/{post_id}/"
    print(f"Getting details for {url}")
    response = requests.get(
        url,
        **AUTH_HEADERS,  # type: ignore
    )
    if not response.ok:
        raise Exception(response.text)
    details = json.loads(response.content)
    return details


CONCURRENT_REQUESTS_LIMIT = 5
llm_rate_limiter = asyncio.Semaphore(CONCURRENT_REQUESTS_LIMIT)


async def call_llm(prompt: str, model: str = "gpt-4o", temperature: float = 0.3) -> str:
    """
    Makes a streaming completion request to OpenAI's API with concurrent request limiting.
    """

    # Remove the base_url parameter to call the OpenAI API directly
    # Also checkout the package 'litellm' for one function that can call any model from any provider
    # Email support@metaculus.com if you need credit for the Metaculus OpenAI/Anthropic proxy
    client = AsyncOpenAI(
        base_url="https://llm-proxy.metaculus.com/proxy/openai/v1",
        default_headers={
            "Content-Type": "application/json",
            "Authorization": f"Token {METACULUS_TOKEN}",
        },
        api_key=os.environ.get("OPENAI_API_KEY"),
        max_retries=2,
    )

    async with llm_rate_limiter:
        collected_content = []
        stream = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                collected_content.append(chunk.choices[0].delta.content)

    return "".join(collected_content)


def run_research(question: str) -> str:
    research = ""
    if GET_NEWS == True:
        if ASKNEWS_CLIENT_ID and ASKNEWS_SECRET:
            print("Running research...")
            research = call_asknews(question)
        else:
            raise ValueError("No API key provided")
    else:
        research = "No research done"

    print(f"########################\nResearch Found:\n{research}\n########################")

    return research


def call_asknews(question: str) -> str:
    """
    Use the AskNews `news` endpoint to get news context for your query.
    The full API reference can be found here: https://docs.asknews.app/en/reference#get-/v1/news/search
    """
    ask = AskNewsSDK(
        client_id=ASKNEWS_CLIENT_ID, client_secret=ASKNEWS_SECRET, scopes=set(["news"])
    )

    # get the latest news related to the query (within the past 48 hours)
    hot_response = ask.news.search_news(
        query=question,  # your natural language query
        n_articles=10,  # control the number of articles to include in the context, originally 5
        return_type="both",
        strategy="latest news",  # enforces looking at the latest news only
    )

    # get context from the "historical" database that contains a news archive going back to 2023
    historical_response = ask.news.search_news(
        query=question,
        n_articles=15,
        return_type="both",
        strategy="news knowledge",  # looks for relevant news within the past 60 days
    )

    hot_articles = hot_response.as_dicts
    historical_articles = historical_response.as_dicts
    formatted_articles = "Here are the relevant news articles:\n\n"

    if hot_articles:
        hot_articles = [article.__dict__ for article in hot_articles]
        hot_articles = sorted(hot_articles, key=lambda x: x["pub_date"], reverse=True)

        for article in hot_articles:
            pub_date = article["pub_date"].strftime("%B %d, %Y %I:%M %p")
            formatted_articles += f"**{article['eng_title']}**\n{article['summary']}\nOriginal language: {article['language']}\nPublish date: {pub_date}\nSource:[{article['source_id']}]({article['article_url']})\n\n"

    if historical_articles:
        historical_articles = [article.__dict__ for article in historical_articles]
        historical_articles = sorted(
            historical_articles, key=lambda x: x["pub_date"], reverse=True
        )

        for article in historical_articles:
            pub_date = article["pub_date"].strftime("%B %d, %Y %I:%M %p")
            formatted_articles += f"**{article['eng_title']}**\n{article['summary']}\nOriginal language: {article['language']}\nPublish date: {pub_date}\nSource:[{article['source_id']}]({article['article_url']})\n\n"

    if not hot_articles and not historical_articles:
        formatted_articles += "No articles were found.\n\n"
        return formatted_articles

    return formatted_articles


############### BINARY ###############
# @title Binary prompt & functions

# This section includes functionality for binary questions.

BINARY_PROMPT_TEMPLATE = """
You are a professional forecaster interviewing for a job.

Your interview question is:
{title}

Question background:
{background}


This question's outcome will be determined by the specific criteria below. These criteria have not yet been satisfied:
{resolution_criteria}

{fine_print}


Your research assistant says:
{summary_report}

Today is {today}.

Before answering you write:
(a) The time left until the outcome to the question is known.
(b) The status quo outcome if nothing changed.
(c) A brief description of a scenario that results in a No outcome.
(d) A brief description of a scenario that results in a Yes outcome.

You write your rationale remembering that good forecasters put extra weight on the status quo outcome since the world changes slowly most of the time.

The last thing you write is your final answer as: "Probability: ZZ%", 0-100
"""


def extract_probability_from_response_as_percentage_not_decimal(
        forecast_text: str,
) -> float:
    matches = re.findall(r"(\d+)%", forecast_text)
    if matches:
        # Return the last number found before a '%'
        number = int(matches[-1])
        number = min(99, max(1, number))  # clamp the number between 1 and 99
        return number
    else:
        raise ValueError(f"Could not extract prediction from response: {forecast_text}")


async def get_binary_gpt_prediction(
        question_details: dict, num_runs: int,
        cache_seed: int = 42
) -> tuple[float, str]:
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    title = question_details["title"]
    resolution_criteria = question_details["resolution_criteria"]
    background = question_details["description"]
    fine_print = question_details["fine_print"]
    question_type = question_details["type"]
    question_input_to_prompt = f"Question title: {title}\n\nQuestion description: {background}\n\nResolution criteria: {resolution_criteria}\n\n Fine print: {fine_print}\n\n The Date is: {today}\n\n"

    summary_report = run_research(title)

    probability_and_comment_pairs = await asyncio.gather(
        *[forecast_single_binary_question(question_input_to_prompt, summary_report, cache_seed=cache_seed) for _ in
          range(num_runs)]
    )
    comments = [pair[1] for pair in probability_and_comment_pairs]
    final_comment_sections = [
        f"## Rationale {i + 1}\n{comment}" for i, comment in enumerate(comments)
    ]
    probabilities = [pair[0] for pair in probability_and_comment_pairs]
    median_probability = float(np.median(probabilities)) / 100

    final_comment = f"Median Probability: {median_probability}\n\n" + "\n\n".join(
        final_comment_sections
    )
    return median_probability, final_comment



########################## MULTIPLE CHOICE ###############
# @title Multiple Choice prompt & functions


def extract_option_probabilities_from_response(forecast_text: str, options) -> float:
    # Helper function that returns a list of tuples with numbers for all lines with Percentile
    def extract_option_probabilities(text):

        # Number extraction pattern
        number_pattern = r"-?\d+(?:,\d{3})*(?:\.\d+)?"

        results = []

        # Iterate through each line in the text
        for line in text.split("\n"):
            # Extract all numbers from the line
            numbers = re.findall(number_pattern, line)
            numbers_no_commas = [num.replace(",", "") for num in numbers]
            # Convert strings to float or int
            numbers = [
                float(num) if "." in num else int(num) for num in numbers_no_commas
            ]
            # Add the tuple of numbers to results
            if len(numbers) >= 1:
                last_number = numbers[-1]
                results.append(last_number)

        return results

    option_probabilities = extract_option_probabilities(forecast_text)

    NUM_OPTIONS = len(options)

    if len(option_probabilities) > 0:
        # return the last NUM_OPTIONS items
        return option_probabilities[-NUM_OPTIONS:]
    else:
        raise ValueError(f"Could not extract prediction from response: {forecast_text}")


def generate_multiple_choice_forecast(options, option_probabilities) -> dict:
    """
    Returns: dict corresponding to the probabilities of each option.
    """

    # confirm that there is a probability for each option
    if len(options) != len(option_probabilities):
        raise ValueError(
            f"Number of options ({len(options)}) does not match number of probabilities ({len(option_probabilities)})"
        )

    # Ensure we are using decimals
    total_sum = sum(option_probabilities)
    decimal_list = [x / total_sum for x in option_probabilities]

    def normalize_list(float_list):
        # Step 1: Clamp values
        clamped_list = [max(min(x, 0.99), 0.01) for x in float_list]

        # Step 2: Calculate the sum of all elements
        total_sum = sum(clamped_list)

        # Step 3: Normalize the list so that all elements add up to 1
        normalized_list = [x / total_sum for x in clamped_list]

        # Step 4: Adjust for any small floating-point errors
        adjustment = 1.0 - sum(normalized_list)
        normalized_list[-1] += adjustment

        return normalized_list

    normalized_option_probabilities = normalize_list(decimal_list)

    probability_yes_per_category = {}
    for i in range(len(options)):
        probability_yes_per_category[options[i]] = normalized_option_probabilities[i]

    return probability_yes_per_category


async def get_multiple_choice_gpt_prediction(
        question_details: dict,
        num_runs: int,
        cache_seed: int = 42
) -> tuple[dict[str, float], str]:
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    title = question_details["title"]
    resolution_criteria = question_details["resolution_criteria"]
    background = question_details["description"]
    fine_print = question_details["fine_print"]
    question_type = question_details["type"]
    options = question_details["options"]
    question_input_to_prompt = f"Question title: {title}\n\nQuestion description: {background}\n\nResolution criteria: {resolution_criteria}\n\n Fine print: {fine_print}\n\n The Date is: {today}\n\n"

    summary_report = run_research(title)


    probability_yes_per_category_and_comment_pairs = await asyncio.gather(
        *[forecast_single_multiple_choice_question(question_details, options=options, news=summary_report,
                                                   cache_seed=cache_seed)
          for _ in range(num_runs)]
    )
    comments = [pair[1] for pair in probability_yes_per_category_and_comment_pairs]
    final_comment_sections = [
        f"## Rationale {i + 1}\n{comment}" for i, comment in enumerate(comments)
    ]
    probability_yes_per_category = [pair[0] for pair in probability_yes_per_category_and_comment_pairs]

    final_comment = (
            f"Average Probability Yes Per Category: `{probability_yes_per_category}`\n\n"
            + "\n\n".join(final_comment_sections)
    )
    return probability_yes_per_category[0], final_comment


################### FORECASTING ###################
def forecast_is_already_made(post_details: dict) -> bool:
    """
    Check if a forecast has already been made by looking at my_forecasts in the question data.

    question.my_forecasts.latest.forecast_values has the following values for each question type:
    Binary: [probability for no, probability for yes]
    Numeric: [cdf value 1, cdf value 2, ..., cdf value 201]
    Multiple Choice: [probability for option 1, probability for option 2, ...]
    """
    try:
        forecast_values = post_details["question"]["my_forecasts"]["latest"][
            "forecast_values"
        ]
        return forecast_values is not None
    except Exception:
        return False


async def question_answer_decider(question_type: str, question_details: dict, summary_report: str, cache_seed: int = 42,summary_of_forecast: str = "")\
        -> tuple[float | dict[str, float] | list[float], str, str]:


    # Now decide which forecast function to use
    if question_type == "binary" and FORECAST_BINARY:
        # Call the new forecast_single_binary_question
        final_proba, summarization = await forecast_single_binary_question(
            question_details,  # a dict
            news=summary_report,
            cache_seed=cache_seed
        )
        # Metaculus API expects a decimal 0..1, so we convert int% => float
        forecast = final_proba / 100.0
        comment = summarization

    elif question_type == "multiple_choice" and FORECAST_MULTIPLE_CHOICE:
        # call the new forecast_single_multiple_choice_question
        final_dist, summarization = await forecast_single_multiple_choice_question(
            question_details,
            options=question_details["options"],
            news=summary_report,
            cache_seed=cache_seed
        )
        forecast = final_dist  # e.g. {"Option A":0.2,"Option B":0.8}
        comment = summarization

    elif question_type == "numeric":
        summary_of_forecast += "Skipped numeric forecast for now.\n"
        forecast = None
        comment = None

    else:
        summary_of_forecast += f"Skipping unknown question type: {question_type}\n"
        forecast = None
        comment = None

    return forecast, comment, summary_of_forecast


def print_for_debugging(post_id: int, question_id: int, forecast: float | dict[str, float] | list[float], comment: str, question_type: str,
                        summary_of_forecast:str) -> None:

    # Print to console for debugging
    print(f"-----------------------------------------------\nPost {post_id} (Q {question_id}):\n")
    print(f"Forecast for post {post_id}: {forecast}")
    print(f"Comment for post {post_id}: {comment}")

    # Build the summary
    summary_of_forecast += f"Forecast: {str(forecast)[:200]}...\n"
    if comment:
        short_comment = comment[:200] + "..." if len(comment) > 200 else comment
        summary_of_forecast += f"Comment:\n```\n{short_comment}\n```\n\n"


async def forecast_individual_question(
    question_id: int,
    post_id: int,
    submit_prediction: bool,
    skip_previously_forecasted_questions: bool,
    cache_seed: int = 42
) -> str:
    post_details = get_post_details(post_id)
    question_details = post_details["question"]
    title = question_details["title"]
    question_type = question_details["type"]

    summary_of_forecast = (
        f"-----------------------------------------------\n"
        f"Question: {title}\n"
        f"URL: https://www.metaculus.com/questions/{post_id}/\n"
    )
    if question_type == "multiple_choice":
        summary_of_forecast += f"options: {question_details['options']}\n"

    # Check if we already forecasted, skip if so:
    if (
        forecast_is_already_made(post_details)
        and skip_previously_forecasted_questions
    ):
        summary_of_forecast += "Skipped: Forecast already made\n"
        return summary_of_forecast

    # GET "NEWS" or "RESEARCH" from question.title
    summary_report = run_research(title)

    forecast, comment, summary_of_forecast = await question_answer_decider(question_type, question_details, summary_report, cache_seed, summary_of_forecast)

    # In case forecast is None from skipping
    if forecast is None:
        return summary_of_forecast

    print_for_debugging(post_id, question_id, forecast, comment, question_type, summary_of_forecast)

    # Optionally submit forecast to Metaculus
    if submit_prediction and forecast is not None and question_type in ("binary","multiple_choice"):
        forecast_payload = create_forecast_payload(forecast, question_type)
        post_question_prediction(question_id, forecast_payload)
        if comment:
            post_question_comment(post_id, comment)
        summary_of_forecast += "Posted: Forecast was posted to Metaculus.\n"


    return summary_of_forecast

async def forecast_questions(
        open_question_id_post_id: list[tuple[int, int]],
        submit_prediction: bool,
        skip_previously_forecasted_questions: bool,
        cache_seed: int = 42
) -> None:
    forecast_tasks = [
        forecast_individual_question(
            question_id,
            post_id,
            submit_prediction,
            skip_previously_forecasted_questions,
            cache_seed
        )
        for question_id, post_id in open_question_id_post_id
    ]
    forecast_summaries = await asyncio.gather(*forecast_tasks, return_exceptions=True)
    print("\n", "#" * 100, "\nForecast Summaries\n", "#" * 100)

    errors = []
    for question_id_post_id, forecast_summary in zip(
            open_question_id_post_id, forecast_summaries
    ):
        question_id, post_id = question_id_post_id
        if isinstance(forecast_summary, Exception):
            print(
                f"-----------------------------------------------\nPost {post_id} Question {question_id}:\nError: {forecast_summary.__class__.__name__} {forecast_summary}\nURL: https://www.metaculus.com/questions/{post_id}/\n"
            )
            errors.append(forecast_summary)
        else:
            print(forecast_summary)

    if errors:
        print("-----------------------------------------------\nErrors:\n")
        error_message = f"Errors were encountered: {errors}"
        print(error_message)
        raise Exception(error_message)


######################## FINAL RUN #########################
if __name__ == "__main__":
    if USE_EXAMPLE_QUESTIONS:
        open_question_id_post_id = EXAMPLE_QUESTIONS
    else:
        open_question_id_post_id = get_open_question_ids_from_tournament()
    now = datetime.datetime.now()
    asyncio.run(
        forecast_questions(
            open_question_id_post_id,
            SUBMIT_PREDICTION,
            SKIP_PREVIOUSLY_FORECASTED_QUESTIONS,
            cache_seed=33
        )
    )
    print(f"time taken to run: {datetime.datetime.now() - now}")