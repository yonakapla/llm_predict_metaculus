import random
import unittest
import datetime

from main import forecast_questions

class TestEnd2End(unittest.IsolatedAsyncioTestCase):

    async def test_e2e_binary(self):
        open_question_id_post_id = [(578, 578)]
        now = datetime.datetime.now()
        await forecast_questions(
                open_question_id_post_id,
                submit_prediction=True,
                skip_previously_forecasted_questions=False,
                use_hyde=True,
                cache_seed=42
            )
        print(f"time taken to run: {datetime.datetime.now() - now}")


if __name__ == "__main__":
    unittest.main()