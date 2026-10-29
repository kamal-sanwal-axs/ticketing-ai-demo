import unittest

from apex_rag_demo.api_guidance import explain_need_api_prompt


class ApiGuidanceTests(unittest.TestCase):
    def test_publish_hint(self) -> None:
        line = explain_need_api_prompt("publish AINV-2422 ed043ece")
        self.assertIn("publish", line.lower())
        self.assertNotIn("Documentation", line)

    def test_search_hint(self) -> None:
        line = explain_need_api_prompt("find events like splash")
        self.assertIn("search", line.lower())

    def test_show_me_events_lists_marketing(self) -> None:
        line = explain_need_api_prompt("show me events")
        self.assertIn("marketing", line.lower())
        self.assertNotIn("get event <event-uuid>", line)


if __name__ == "__main__":
    unittest.main()
