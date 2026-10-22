from __future__ import annotations

import re

_EVENT_WORD_RE = re.compile(r"\bevents?\b", re.I)

_APEX_DOMAIN_RE = re.compile(
    r"\b("
    r"client[- ]?venues?|organizations?|marketing|inventory|"
    r"ticket|apex|zones?|publish|admin|search[- ]?api|"
    r"event[- ]?id|organization[- ]?id|client[- ]?id"
    r")\b",
    re.I,
)

_OFF_TOPIC_HINTS = (
    "weather",
    "forecast",
    "temperature",
    "raining",
    "rain today",
    "sunny",
    "snow",
    "humidity",
    "tell me a joke",
    "write a poem",
    "who is the president",
    "recipe for",
    "translate this",
    "what time is it",
)

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
)


def mentions_event_keyword(text: str) -> bool:
    """Whole-word 'event' / 'events' — avoids matching 'weather'."""
    return bool(_EVENT_WORD_RE.search(text))


def has_apex_domain_signal(text: str) -> bool:
    return bool(_APEX_DOMAIN_RE.search(text)) or bool(_UUID_RE.search(text))


def is_off_topic(bare_question: str) -> bool:
    b = bare_question.lower().strip()
    if not b:
        return False
    if has_apex_domain_signal(b):
        return False
    if any(hint in b for hint in _OFF_TOPIC_HINTS):
        return True
    if mentions_event_keyword(b):
        return False
    if any(
        w in b
        for w in (
            "list client",
            "client venue",
            "create org",
            "marketing event",
            "inventory zone",
            "search event",
            "find event",
        )
    ):
        return False
    return False


def guard_api_intent(intent: str, question: str) -> str:
    """Reconcile classifier output with message content."""
    bare = strip_typos(question)
    if intent in ("get_event", "inventory_zones") and not _UUID_RE.search(question):
        if looks_like_named_event_search(bare):
            return "search_events"
        if looks_like_list_events(bare):
            return "marketing_events"
        return "explain"
    if intent == "list_client_venues":
        if wants_list_client_venues(bare):
            return intent
        if looks_like_list_events(bare) or is_events_not_venues_request(bare):
            return "marketing_events"
        if looks_like_named_event_search(bare):
            return "search_events"
    if intent == "search_events" and looks_like_list_events(bare):
        return "marketing_events"
    return intent


_GREETING_RE = re.compile(
    r"^(hi|hello|hey|howdy|yo|greetings|good\s+(morning|afternoon|evening))[\s,!?.]*$",
    re.I,
)

_SEARCH_VERB_EVENT_RE = re.compile(
    r"\b(seach|search|find|show|list|lookup)\s+events?\b",
    re.I,
)

_EVENT_WHEN_WHERE_RE = re.compile(
    r"\bevents?\b.*\b("
    r"in|this|next|tonight|today|tomorrow|month|week|year|"
    r"january|february|march|april|may|june|july|august|september|october|november|december"
    r")\b",
    re.I,
)


def strip_typos(text: str) -> str:
    return re.sub(r"\bseach\b", "search", text, flags=re.I)


def is_greeting(bare_question: str) -> bool:
    return bool(_GREETING_RE.match(bare_question.strip()))


_ASSISTANT_META_RE = re.compile(
    r"("
    r"what('s| is)\s+your\s+name|who\s+are\s+you|what\s+are\s+you|"
    r"what\s+do\s+you\s+call\s+yourself|your\s+name\??"
    r")",
    re.I,
)

_BARE_LIST_EVENTS = frozenset(
    {
        "all events",
        "all event",
        "events",
        "event",
        "list events",
        "list all events",
        "show events",
        "show all events",
        "every event",
        "every events",
    },
)

_LIST_EVENTS_RE = re.compile(
    r"("
    r"\blist\s+(of\s+)?events\b|\blist\s+all\s+events\b|"
    r"\bshow\s+(me\s+)?(all\s+)?events\b|\bshow\s+(me\s+)?events\s+this\b|"
    r"\bevents\s+this\s+(week|month|year)\b|"
    r"\ball\s+events\b|\ball\s+event\b|"
    r"\b(all\s+)?events\s+(are\s+)?(published|live)\b|"
    r"\bwhat\s+(\w+\s+)?events\b|\bwhich\s+events\b|"
    r"\bpublished\s+events\b|\bevents\s+(are\s+)?published\b"
    r")",
    re.I,
)

_CLIENT_VENUE_LIST_RE = re.compile(
    r"(\blist\s+(all\s+)?client[- ]?venues\b|\bclient[- ]?venues\b.*\b(list|show|all)\b)",
    re.I,
)

_FILLER_PREFIX_RE = re.compile(
    r"^(please\s+)?((can you|could you)\s+)?(show me|show|give me|tell me|i want( to see)?)\s+",
    re.I,
)

_DATE_ONLY_QUERY_RE = re.compile(
    r"^(this|next)\s+(week|month|year|weekend)(\s+|$)|^events?\s+(this|next)\s+(week|month)",
    re.I,
)

_ARTIST_QUERY_RE = re.compile(r"\bartist(s)?\s+(names?|list)?\b|\bshow\s+artist", re.I)


def is_assistant_meta_question(bare_question: str) -> bool:
    return bool(_ASSISTANT_META_RE.search(bare_question.strip()))


def is_events_not_venues_request(bare_question: str) -> bool:
    """Ticketed events — not client-venue registry."""
    b = bare_question.lower()
    if "client venue" in b or "client-venue" in b:
        return False
    return mentions_event_keyword(b)


def looks_like_list_events(bare_question: str) -> bool:
    b = strip_typos(bare_question).lower().strip().rstrip(".!?")
    if not mentions_event_keyword(b):
        return False
    if wants_list_client_venues(bare_question):
        return False
    if b in _BARE_LIST_EVENTS:
        return True
    if _LIST_EVENTS_RE.search(b):
        return True
    if re.search(r"\bvenue\s+is\s+not\s+event\b", b) and re.search(r"\blist\s+(of\s+)?events\b", b):
        return True
    return False


def wants_list_client_venues(bare_question: str) -> bool:
    b = bare_question.lower().strip().rstrip(".!?")
    if b in _BARE_LIST_EVENTS:
        return False
    if _LIST_EVENTS_RE.search(b):
        return False
    if is_events_not_venues_request(bare_question) and "client venue" not in b:
        if re.search(r"\bevents?\b", b) and not re.search(r"\bclient[- ]?venues?\b", b):
            return False
    if re.search(r"\blist\s+(of\s+)?events\b", b) or re.search(
        r"\bshow\s+.*\bevents\b",
        b,
    ):
        return False
    if "venue is not event" in b or "client venue is not" in b:
        return False
    if _CLIENT_VENUE_LIST_RE.search(bare_question):
        return True
    stripped = b.strip().rstrip(".!?")
    return stripped in ("list client venues", "list all client venues")


def is_weak_suggest_query(query: str) -> bool:
    q = query.lower().strip()
    if len(q) < 3:
        return True
    if _DATE_ONLY_QUERY_RE.search(q):
        return True
    if q.startswith("show me ") or q.startswith("show "):
        return True
    if re.fullmatch(r"(live|published)\s+events?", q):
        return True
    if re.search(r"\bthis\s+(week|month|year)\b", q) and "event" in q:
        return True
    return False


def looks_like_named_event_search(bare_question: str) -> bool:
    """Name/keyword event lookup (search-api suggest), not bulk listing."""
    if looks_like_list_events(bare_question):
        return False
    if _ARTIST_QUERY_RE.search(bare_question):
        return True
    if not looks_like_event_search(bare_question):
        return False
    query = extract_event_search_query(bare_question)
    return not is_weak_suggest_query(query)


def looks_like_event_search(bare_question: str) -> bool:
    b = strip_typos(bare_question).lower().strip()
    if not mentions_event_keyword(b):
        return False
    if looks_like_list_events(bare_question):
        return False
    if wants_list_client_venues(bare_question):
        return False
    if _UUID_RE.search(b):
        return False
    if "marketing" in b and "search" not in b and "find" not in b:
        return False
    if _ARTIST_QUERY_RE.search(bare_question):
        return True
    if _SEARCH_VERB_EVENT_RE.search(b):
        return True
    if re.search(r"\bevents?\s+in\s+\S", b):
        return True
    if _EVENT_WHEN_WHERE_RE.search(b):
        return True
    if re.match(r"^events?\b", b):
        return True
    return False


def extract_event_search_query(question: str) -> str:
    """Turn natural language into a short suggest-api query string."""
    q = _FILLER_PREFIX_RE.sub("", strip_typos(question).strip())
    lowered = q.lower()

    if _ARTIST_QUERY_RE.search(q):
        return "artist"

    for prefix in (
        "search events matching",
        "search events for",
        "search events in",
        "search events",
        "search event in",
        "search event",
        "search for events",
        "search for event",
        "find events in",
        "find events",
        "find event in",
        "find event",
        "show me events",
        "show events in",
        "show events",
        "list events in",
        "list events",
        "what events are",
        "events in",
        "event in",
    ):
        if prefix in lowered:
            idx = lowered.index(prefix)
            rest = q[idx + len(prefix) :].strip()
            if len(rest) >= 2:
                return rest[:100]

    match = re.match(r"^events?\s+(.+)$", q, re.I)
    if match:
        rest = match.group(1).strip()
        if len(rest) >= 2:
            return rest[:100]

    match = re.search(r"\b(?:are|is)\s+(live|published)\b", lowered)
    if match:
        return match.group(1)

    return q[:100]
