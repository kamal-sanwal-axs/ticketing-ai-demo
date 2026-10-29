from __future__ import annotations

import unittest

from apex_rag_demo.http_errors import (
    classify_publish_conflict,
    format_publish_event_failure,
)


class PublishErrorTests(unittest.TestCase):
    def test_exact_api_message_missing_images(self) -> None:
        ctx = classify_publish_conflict(
            http_status=409,
            api_detail="Cannot publish an event without all required images.",
            event_state="Draft",
        )
        self.assertEqual(ctx.reason_code, "missing_required_images")
        self.assertIn("image", ctx.meaning.lower())
        self.assertTrue(len(ctx.next_steps) >= 1)

    def test_exact_api_message_already_published(self) -> None:
        ctx = classify_publish_conflict(
            http_status=409,
            api_detail="Cannot publish an event that is already published.",
            event_state="Published",
        )
        self.assertEqual(ctx.reason_code, "already_published")

    def test_draft_state_infers_images_from_detail(self) -> None:
        ctx = classify_publish_conflict(
            http_status=409,
            api_detail="Cannot publish an event without all required images.",
            event_state="Draft",
        )
        self.assertEqual(ctx.reason_code, "missing_required_images")

    def test_published_state_without_detail(self) -> None:
        ctx = classify_publish_conflict(http_status=409, api_detail="", event_state="Published")
        self.assertEqual(ctx.reason_code, "already_published")

    def test_format_uses_publish_context(self) -> None:
        payload = {
            "plan": {"eventId": "defa7917-1a3f-4717-8328-3278cfa7449b"},
            "publishContext": {
                "headline": "Publish not applied — Missing required images",
                "meaning": "Draft events must have all required image types before publish.",
                "apiDetail": "Cannot publish an event without all required images.",
                "eventState": "Draft",
                "nextSteps": ["Upload images in Events UI."],
            },
        }
        text = format_publish_event_failure(payload, None)
        self.assertIn("Missing required images", text)
        self.assertIn("What to do", text)
        self.assertIn("Upload images", text)


if __name__ == "__main__":
    unittest.main()
