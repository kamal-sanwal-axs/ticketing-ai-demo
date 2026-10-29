import unittest

from apex_rag_demo.prompt_budget import estimate_message_tokens, fit_messages_to_context


class PromptBudgetTests(unittest.TestCase):
    def test_fits_under_token_budget(self) -> None:
        huge = "word " * 2000
        messages = [
            {"role": "system", "content": huge},
            {"role": "user", "content": "old"},
            {"role": "assistant", "content": "old reply"},
            {"role": "user", "content": "current question"},
        ]
        fitted, _trimmed = fit_messages_to_context(
            messages,
            max_tokens=400,
            max_chars_per_message=200,
            routing=True,
        )
        self.assertLessEqual(estimate_message_tokens(fitted), 400)
        self.assertEqual(fitted[-1]["content"], "current question")


if __name__ == "__main__":
    unittest.main()
