import unittest
from unittest.mock import patch

from apex_rag_demo.intent_semantic import reconcile_classified_intent, semantic_intent_hint


class IntentSemanticTests(unittest.TestCase):
    @patch("apex_rag_demo.intent_semantic.INTENT_SEMANTIC_ENABLED", True)
    @patch("apex_rag_demo.intent_semantic.INTENT_SEMANTIC_MIN_SCORE", 0.3)
    @patch("apex_rag_demo.intent_semantic.INTENT_SEMANTIC_MARGIN", 0.05)
    @patch(
        "apex_rag_demo.intent_semantic.semantic_intent_scores",
        return_value={"marketing_events": 0.82, "create_event": 0.21},
    )
    def test_semantic_hint_picks_top_intent(self, _mock_scores) -> None:
        self.assertEqual(semantic_intent_hint("display every event in catalog"), "marketing_events")

    def test_reconcile_list_events_regex(self) -> None:
        self.assertEqual(
            reconcile_classified_intent("create_event", "show all events"),
            "marketing_events",
        )

    @patch("apex_rag_demo.intent_semantic.semantic_intent_hint", return_value="marketing_events")
    def test_reconcile_llm_explain_with_semantic(self, _mock_hint) -> None:
        self.assertEqual(
            reconcile_classified_intent("explain", "browse ticketed events published live"),
            "marketing_events",
        )


if __name__ == "__main__":
    unittest.main()
