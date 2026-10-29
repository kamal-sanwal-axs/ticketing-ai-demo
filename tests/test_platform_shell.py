from apex_rag_demo.intent_helpers import guard_api_intent
from apex_rag_demo.platform_shell import looks_like_platform_shell_question
from apex_rag_demo.response_formatters import format_explain


def test_platform_question():
    assert looks_like_platform_shell_question("what MFEs are in the APEX v2 stack?")


def test_customers_intent():
    assert guard_api_intent("explain", "search customers for fan@example.com") == "search_customers"


def test_explain_no_platform_trivia():
    text = format_explain([], "how does axs-b2b-platform load remotes?")
    assert "single-spa host" not in text.lower()
