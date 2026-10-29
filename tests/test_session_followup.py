from __future__ import annotations

import unittest
from unittest.mock import patch

from apex_rag_demo.planning import classify_intent, plan_for_intent


@patch("apex_rag_demo.agent_classify.chat_completion")
class SessionFollowupTests(unittest.TestCase):
    def test_inventory_phrase_routes_to_get_event_not_venues(self, mock_chat) -> None:
        mock_chat.return_value = '{"intent": "get_event", "need_kb_retrieval": false}'
        q = "show me price code price levels sections and venue details"
        self.assertEqual(classify_intent(q), "get_event")

    def test_plan_uses_session_focus_event_id(self, mock_chat) -> None:
        mock_chat.return_value = '{"intent": "get_event", "need_kb_retrieval": false}'
        q = "show me price levels and sections"
        focus = {"eventId": "2fb50812-71b8-4393-b412-39b4c6fa52d7"}
        plan = plan_for_intent("get_event", q, focus)
        self.assertEqual(plan["eventId"], focus["eventId"])
        self.assertTrue(plan["includeInventory"])


if __name__ == "__main__":
    unittest.main()
