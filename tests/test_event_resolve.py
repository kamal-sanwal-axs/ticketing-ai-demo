from __future__ import annotations

import unittest
from unittest.mock import patch

import httpx

from apex_rag_demo.event_context_display import build_resolved_id_display
from apex_rag_demo.event_resolve import get_event_with_context


class EventResolveTests(unittest.TestCase):
    @patch("apex_rag_demo.event_resolve.apex_search.get_client_venue")
    @patch("apex_rag_demo.event_resolve.apex_search.search_events")
    @patch("apex_rag_demo.event_resolve.apex_events.get_event")
    def test_404_falls_back_to_client_venue(
        self,
        mock_get_event,
        mock_search_events,
        mock_get_client_venue,
    ) -> None:
        rid = "019fcc21-907e-79cf-aae2-287a7d7b26dc"
        resp = httpx.Response(404, request=httpx.Request("GET", f"https://x/{rid}"))
        mock_get_event.side_effect = httpx.HTTPStatusError("404", request=resp.request, response=resp)
        mock_search_events.return_value = {"events": []}
        mock_get_client_venue.return_value = {
            "clientVenue": {
                "venue": {"name": "Quicken Loans Arena"},
                "client": {"name": "Test Client"},
            },
        }
        mock_search_events.side_effect = [
            {"events": []},
            {"events": [{"eventId": "ev-1", "name": "Show A"}]},
        ]

        payload, err = get_event_with_context(rid)

        self.assertIsNone(err)
        self.assertEqual(payload.get("_resolution"), "client_venue_context")
        self.assertEqual(payload.get("_requested_id"), rid)

        ui = build_resolved_id_display(payload, {"eventId": rid}, None)
        self.assertIsNotNone(ui)
        self.assertEqual(ui["title"], "Event id lookup")
        self.assertTrue(any(s.get("title") == "Client venue (search-api)" for s in ui["sections"]))


if __name__ == "__main__":
    unittest.main()
