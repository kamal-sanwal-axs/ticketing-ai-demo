import unittest
from unittest.mock import patch

from apex_rag_demo.agent_classify import classify_intent
from apex_rag_demo.intent_helpers import guard_api_intent, is_greeting
from apex_rag_demo.intent_semantic import reconcile_classified_intent


class ConversationalTests(unittest.TestCase):
    def test_is_greeting_hello(self) -> None:
        self.assertTrue(is_greeting("hello"))

    def test_guard_hello_explain(self) -> None:
        self.assertEqual(guard_api_intent("marketing_events", "hello"), "explain")

    def test_reconcile_marketing_to_explain_for_hello(self) -> None:
        self.assertEqual(reconcile_classified_intent("marketing_events", "hello"), "explain")

    @patch("apex_rag_demo.agent_classify.chat_completion")
    def test_classify_hello_skips_llm(self, mock_chat) -> None:
        self.assertEqual(classify_intent("hello"), "explain")
        mock_chat.assert_not_called()


if __name__ == "__main__":
    unittest.main()
