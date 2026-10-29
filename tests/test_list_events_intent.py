import unittest
from unittest.mock import patch

from apex_rag_demo.intent_helpers import (
    guard_api_intent,
    looks_like_list_events,
    looks_like_onsale_or_event_count_question,
)
from apex_rag_demo.planning import classify_intent


class ListEventsIntentTests(unittest.TestCase):
    def test_looks_like_list_events_show_me(self) -> None:
        self.assertTrue(looks_like_list_events("show me events"))

    def test_onsale_count_routes_marketing(self) -> None:
        self.assertTrue(looks_like_onsale_or_event_count_question("how many events are on sale"))
        self.assertEqual(
            guard_api_intent("explain", "how many events are on sale"),
            "marketing_events",
        )

    def test_guard_explain_to_marketing(self) -> None:
        self.assertEqual(guard_api_intent("explain", "show me events"), "marketing_events")

    def test_guard_create_event_to_marketing_for_list(self) -> None:
        self.assertEqual(guard_api_intent("create_event", "show all events"), "marketing_events")

    def test_explicit_create_not_list(self) -> None:
        from apex_rag_demo.intent_helpers import looks_like_explicit_create_event

        self.assertTrue(looks_like_explicit_create_event("create a new event at venue X"))
        self.assertFalse(looks_like_explicit_create_event("show all events"))

    @patch("apex_rag_demo.agent_classify.chat_completion")
    def test_classify_show_me_events_when_llm_says_explain(self, mock_chat) -> None:
        mock_chat.return_value = '{"intent": "explain", "need_kb_retrieval": false}'
        self.assertEqual(classify_intent("show me events"), "marketing_events")


if __name__ == "__main__":
    unittest.main()
