from __future__ import annotations

import unittest
from unittest.mock import patch

from apex_rag_demo.planning import classify_intent


@patch("apex_rag_demo.agent_classify.chat_completion")
class ListUsersIntentTests(unittest.TestCase):
    def test_show_me_users_not_explain(self, mock_chat) -> None:
        mock_chat.return_value = '{"intent": "list_users", "need_kb_retrieval": false}'
        self.assertEqual(classify_intent("show me users"), "list_users")


if __name__ == "__main__":
    unittest.main()
