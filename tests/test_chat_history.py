import unittest

from apex_rag_demo.rag.chat_history import append_chat_turn, load_chat_messages, normalize_chat_history


class ChatHistoryTests(unittest.TestCase):
    def test_normalize_roles(self) -> None:
        raw = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {
                "role": "tool",
                "name": "apex_api",
                "content": "intent: get_event",
            },
            {"role": "system", "content": "ignored"},
        ]
        out = normalize_chat_history(raw)
        self.assertEqual(len(out), 3)
        self.assertEqual(out[2]["role"], "tool")
        self.assertEqual(out[2]["name"], "apex_api")

    def test_append_and_load_roundtrip(self) -> None:
        uid = "test-user-chat-history"
        sid = "sess-1"
        append_chat_turn(uid, sid, "list events", "Here are events", tool_content="intent: marketing_events")
        msgs = load_chat_messages(uid, sid)
        self.assertGreaterEqual(len(msgs), 2)
        roles = [m["role"] for m in msgs]
        self.assertIn("user", roles)
        self.assertIn("tool", roles)


if __name__ == "__main__":
    unittest.main()
