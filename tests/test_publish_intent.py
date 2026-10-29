from __future__ import annotations

import unittest
from unittest.mock import patch

from apex_rag_demo.crud_planners import plan_for_crud_intent
from apex_rag_demo.crud_registry import match_mutation_intent
from apex_rag_demo.mutation_intent_helpers import looks_like_publish_event_request
from apex_rag_demo.planning import classify_intent


@patch("apex_rag_demo.agent_classify.chat_completion")
class PublishIntentTests(unittest.TestCase):
    def test_publish_with_uuid(self, mock_chat) -> None:
        mock_chat.return_value = '{"intent": "publish_event", "need_kb_retrieval": false}'
        eid = "defa7917-1a3f-4717-8328-3278cfa7449b"
        q = f"for event id {eid} publish it"
        self.assertEqual(classify_intent(q), "publish_event")

    def test_publish_event_followup_uses_session_focus(self, mock_chat) -> None:
        mock_chat.return_value = '{"intent": "publish_event", "need_kb_retrieval": false}'
        eid = "defa7917-1a3f-4717-8328-3278cfa7449b"
        self.assertEqual(classify_intent("publish event"), "publish_event")
        plan = plan_for_crud_intent("publish_event", "publish event", {"eventId": eid})
        self.assertEqual(plan["eventId"], eid)

    def test_publish_event_phrase_classified_by_llm(self, mock_chat) -> None:
        mock_chat.return_value = '{"intent": "publish_event", "need_kb_retrieval": false}'
        intent = classify_intent(
            "publish event",
            session_focus={"eventId": "defa7917-1a3f-4717-8328-3278cfa7449b"},
        )
        self.assertEqual(intent, "publish_event")
        mock_chat.assert_called()

    def test_publish_ainv_catalog_match_is_not_routing(self, mock_chat) -> None:
        """Regex catalog may suggest publish_event; graph still requires LLM classify."""
        q = "publish AINV-2422 ed043ece"
        self.assertTrue(looks_like_publish_event_request(q))
        self.assertEqual(match_mutation_intent(q), "publish_event")
        mock_chat.return_value = '{"intent": "publish_event", "need_kb_retrieval": false}'
        self.assertEqual(classify_intent(q), "publish_event")
        mock_chat.assert_called()


if __name__ == "__main__":
    unittest.main()
