import unittest
from datetime import date
from unittest.mock import patch

from apex_rag_demo.event_date_filters import (
    apply_date_filter_to_payload,
    parse_event_date_filter,
    plan_marketing_date_filter,
    question_has_date_constraint,
)


class EventDateFilterTests(unittest.TestCase):
    def test_after_this_month(self) -> None:
        ref = date(2026, 10, 25)
        filt = parse_event_date_filter("show me events after this month", reference=ref)
        self.assertIsNotNone(filt)
        self.assertEqual(filt.start_after, date(2026, 11, 1))

    def test_after_named_month_year(self) -> None:
        ref = date(2026, 10, 25)
        q = "show event name only for those whose event start date is after october 2026"
        filt = parse_event_date_filter(q, reference=ref)
        self.assertIsNotNone(filt)
        self.assertEqual(filt.start_after, date(2026, 11, 1))
        self.assertIn("October 2026", filt.description)

    @patch("apex_rag_demo.clients.llama.chat_completion")
    def test_plan_after_october_uses_llm(self, mock_chat) -> None:
        mock_chat.return_value = (
            '{"startAfter": "2026-11-01", "startBefore": null, '
            '"description": "Events starting after October 2026"}'
        )
        plan = plan_marketing_date_filter(
            "show event name only for those whose event start date is after october 2026",
            reference=date(2026, 10, 25),
        )
        self.assertEqual(plan.get("_dateFilterSource"), "llm")
        self.assertEqual(plan["dateFilter"]["startAfter"], "2026-11-01")
        mock_chat.assert_called_once()

    def test_has_date_constraint(self) -> None:
        self.assertTrue(question_has_date_constraint("events after this month"))
        self.assertFalse(question_has_date_constraint("list client venues"))

    def test_apply_filter(self) -> None:
        payload = {
            "events": [
                {"id": "a", "dates": {"start": {"on": "2026-09-15T19:00:00"}}},
                {"id": "b", "dates": {"start": {"on": "2026-11-05T19:00:00"}}},
            ],
        }
        plan = parse_event_date_filter("after this month", reference=date(2026, 10, 25))
        out = apply_date_filter_to_payload(payload, plan.to_plan() if plan else None)
        self.assertEqual(len(out["events"]), 1)
        self.assertEqual(out["events"][0]["id"], "b")

    @patch("apex_rag_demo.clients.llama.chat_completion")
    def test_plan_after_this_month_uses_llm(self, mock_chat) -> None:
        mock_chat.return_value = (
            '{"startAfter": "2026-11-01", "startBefore": null, '
            '"description": "After this month"}'
        )
        plan = plan_marketing_date_filter(
            "show me events after this month",
            reference=date(2026, 10, 25),
        )
        self.assertEqual(plan.get("_dateFilterSource"), "llm")
        self.assertEqual(plan["dateFilter"]["startAfter"], "2026-11-01")
        mock_chat.assert_called_once()


if __name__ == "__main__":
    unittest.main()
