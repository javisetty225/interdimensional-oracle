"""
Code-level query classifier — first guardrail layer.

Classifies queries into four categories before any LLM call:
  - greeting:  instant welcome response, zero API cost
  - help:      instant help response, zero API cost
  - allowed:   passes through to retriever and LLM
  - off_topic: blocked with explanation, zero API cost

Design decisions:
  - RM_SIGNALS contains only terms specific to Rick & Morty.
    Generic words like "smith" and "species" were excluded
    to avoid false positives on everyday queries.
  - R&M signals are checked BEFORE blocked patterns so that
    queries like "Rick writes a poem" are correctly allowed
    even though "write" is a blocked word.
  - The classifier is intentionally permissive for ambiguous
    queries — the prompt-level guardrail in rag.py handles
    anything that slips through.
"""
import logging
import re

logger = logging.getLogger(__name__)

# Fixed responses for simple interactions — no LLM needed
GREETING_RESPONSE = (
    "Greetings. I am the Interdimensional Oracle — keeper of all "
    "knowledge across the Rick & Morty universe.\n\n"
    "Ask me about any character, episode, or location from the show. "
    "For example:\n"
    "• Who is Rick Sanchez?\n"
    "• What dimension is Earth C-137 in?\n"
    "• Which episodes feature Birdperson?\n"
    "• Show me all dead characters"
)

HELP_RESPONSE = (
    "The Oracle can answer questions about the Rick & Morty universe:\n\n"
    "• Characters — species, status, origin, location, episode appearances\n"
    "• Episodes — air dates, season and episode codes, featured characters\n"
    "• Locations — dimension, type, known residents\n\n"
    "All answers come exclusively from retrieved data — "
    "never from LLM memory. Sources are always cited."
)

# Patterns that trigger an instant greeting response
# Uses ^ and $ anchors to match the full query only
GREETING_PATTERNS = [
    r"^hi$",
    r"^hey$",
    r"^hello$",
    r"^howdy$",
    r"^greetings$",
    r"^good\s(morning|afternoon|evening|day)$",
    r"^hi\s(there|oracle)$",
    r"^hey\s(there|oracle)$",
    r"^hello\s(there|oracle)$",
    r"^sup$",
    r"^yo$",
]

# Patterns that trigger an instant help response
# Uses ^ anchor so only queries that START with these phrases match
HELP_PATTERNS = [
    r"^help$",
    r"^help me$",
    r"^how does this work",
    r"^what can you do",
    r"^what can (you|the oracle) (do|help|answer)",
    r"^(what are your|your) capabilities",
    r"^(how do i|how to) use",
    r"^instructions$",
    r"^guide$",
    r"^commands$",
]

# Terms genuinely specific to the Rick & Morty universe
# Generic words excluded: "smith", "species", "what is", "list",
# "show", "find", "alive", "dead", "character", "location", "origin"
# These caused false positives on everyday non-R&M queries
RM_SIGNALS = [
    r"\brick\b",
    r"\bmorty\b",
    r"\bsanchez\b",
    r"\bsummer\b",
    r"\bbeth\b",
    r"\bjerry\b",
    r"\bbird.?person\b",
    r"\bpickle.?rick\b",
    r"\bportal\b",
    r"\bdimension\b",
    r"\bepisode\b",
    r"\bseason\b",
    r"\bcitadel\b",
    r"\bcouncil\b",
    r"\bmeseeks\b",
    r"\bschwifty\b",
    r"\bgalactic\b",
    r"\bwubba\b",
    r"\bsquanch\b",
    r"\bhumanoid\b",
    r"\binterdimensional\b",
    r"\bcronenberg\b",
    r"\bgazorpazorp\b",
]

# Patterns that clearly indicate off-topic queries
# "\bwrite\b" used instead of "\bwrite (me |a |an )" to avoid gaps
# e.g. "write something", "write code" were previously not caught
BLOCKED_PATTERNS = [
    r"\bweather\b",
    r"\bforecast\b",
    r"\btemperature\b",
    r"\bstock\b",
    r"\bbitcoin\b",
    r"\bcrypto\b",
    r"\belection\b",
    r"\bpolitics\b",
    r"\brecipe\b",
    r"\bcooking\b",
    r"\bsport\b",
    r"\bfootball\b",
    r"\bbasketball\b",
    r"\bsoccer\b",
    r"\bnews\b",
    r"\bwrite\b",
    r"\bessay\b",
    r"\bpoem\b",
    r"\btranslate\b",
    r"\btranslation\b",
    r"\bcalculat\b",
    r"\bmath\b",
]


def _is_greeting(query_lower: str) -> bool:
    """Check if the query is a simple greeting."""
    return any(
        re.search(pattern, query_lower)
        for pattern in GREETING_PATTERNS
    )


def _is_help_request(query_lower: str) -> bool:
    """Check if the query is a help or capability request."""
    return any(
        re.search(pattern, query_lower)
        for pattern in HELP_PATTERNS
    )


def _has_rm_signals(query_lower: str) -> bool:
    """
    Check if the query contains terms specific to Rick & Morty.
    If true, the query is allowed even if blocked patterns also match.
    """
    return any(
        re.search(pattern, query_lower)
        for pattern in RM_SIGNALS
    )


def _has_blocked_pattern(query_lower: str) -> bool:
    """Check if the query matches any clearly off-topic patterns."""
    return any(
        re.search(pattern, query_lower)
        for pattern in BLOCKED_PATTERNS
    )


def classify_query(query: str) -> dict:
    """
    Classify a query into one of four categories.

    Decision flow:
    1. Empty query      → blocked, ask user to type something
    2. Greeting         → instant welcome response, no LLM
    3. Help request     → instant help response, no LLM
    4. R&M signals      → allowed, pass to retriever and LLM
    5. Blocked pattern  → blocked, explain off-topic
    6. Everything else  → allowed, LLM handles edge cases

    Note: R&M signals are checked BEFORE blocked patterns.
    This means "Rick writes a poem in this episode" is correctly
    allowed through even though "write" is a blocked word.

    Args:
        query: The raw user query string

    Returns:
        Dict containing:
          - allowed:          bool — whether to pass to retriever and LLM
          - reason:           str  — category: empty, greeting, help,
                                     allowed, off_topic
          - detail:           str  — human readable explanation or None
          - instant_response: str  — pre-built response or None
    """
    query = query.strip()
    query_lower = query.lower()

    # 1. Block completely empty queries
    if not query:
        logger.debug("Query blocked — empty")
        return {
            "allowed": False,
            "reason": "empty",
            "detail": "Please type a question.",
            "instant_response": None,
        }

    # 2. Greeting — instant response, no LLM, no retrieval
    if _is_greeting(query_lower):
        logger.debug("Query is greeting: '%s'", query)
        return {
            "allowed": False,
            "reason": "greeting",
            "detail": None,
            "instant_response": GREETING_RESPONSE,
        }

    # 3. Help request — instant response, no LLM, no retrieval
    if _is_help_request(query_lower):
        logger.debug("Query is help request: '%s'", query)
        return {
            "allowed": False,
            "reason": "help",
            "detail": None,
            "instant_response": HELP_RESPONSE,
        }

    # 4. Rick & Morty signals — allow immediately
    if _has_rm_signals(query_lower):
        logger.debug("Query allowed — R&M signals detected: '%s'", query)
        return {
            "allowed": True,
            "reason": "allowed",
            "detail": None,
            "instant_response": None,
        }

    # 5. Off-topic patterns — block with explanation
    if _has_blocked_pattern(query_lower):
        logger.debug("Query blocked — off-topic: '%s'", query)
        return {
            "allowed": False,
            "reason": "off_topic",
            "detail": (
                "This question appears to be outside the Rick & Morty "
                "universe. Ask me about characters, episodes, or "
                "locations from the show."
            ),
            "instant_response": None,
        }

    # 6. Everything else — allow, LLM handles remaining edge cases
    logger.debug("Query allowed — passing to LLM: '%s'", query)
    return {
        "allowed": True,
        "reason": "allowed",
        "detail": None,
        "instant_response": None,
    }