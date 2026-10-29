import unittest
from unittest.mock import patch

from apex_rag_demo.semantic_turn import prepare_semantic_turn


class SemanticTurnTests(unittest.TestCase):
    @patch("apex_rag_demo.semantic_turn.INTENT_SEMANTIC_ENABLED", True)
    @patch("apex_rag_demo.semantic_turn.TOPIC_SHIFT_MAX_SIMILARITY", 0.55)
    @patch("apex_rag_demo.semantic_turn.semantic_intent_hint", return_value="marketing_events")
    @patch("apex_rag_demo.semantic_turn.semantic_closest_exemplar", return_value=("marketing_events", "show all events", 0.9))
    @patch("apex_rag_demo.semantic_turn.semantic_intent_scores", return_value={"marketing_events": 0.85})
    @patch("apex_rag_demo.semantic_turn._embed_intent_texts")
    def test_topic_shift_clears_history(self, mock_embed, *_mocks) -> None:
        mock_embed.side_effect = [
            [[1.0, 0.0], [0.0, 1.0]],
            [[1.0, 0.0]],
        ]
        history = [
            {"role": "user", "content": "create a new event"},
            {"role": "assistant", "content": "create failed 400"},
        ]
        ctx = prepare_semantic_turn("show all events", history)
        self.assertTrue(ctx.topic_shift)
        self.assertEqual(ctx.chat_messages, [])
        self.assertIn("Topic shift: YES", ctx.context_block)


if __name__ == "__main__":
    unittest.main()
