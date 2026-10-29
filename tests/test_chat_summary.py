import unittest

from apex_rag_demo.rag.chat_summary import _rule_rollup_messages


class ChatSummaryTests(unittest.TestCase):
    def test_rule_rollup_keeps_roles(self) -> None:
        messages = [
            {"role": "user", "content": "list events"},
            {"role": "tool", "name": "apex_api", "content": "intent: marketing_events"},
            {"role": "assistant", "content": "ten events"},
            {"role": "user", "content": "publish AINV-1"},
            {"role": "tool", "name": "apex_api", "content": "intent: publish_event"},
            {"role": "assistant", "content": "confirm publish"},
        ]
        out = _rule_rollup_messages(messages)
        roles = [m["role"] for m in out]
        self.assertIn("user", roles)
        self.assertIn("assistant", roles)
        self.assertIn("tool", roles)


if __name__ == "__main__":
    unittest.main()
