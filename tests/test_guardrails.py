import pytest
from backend.core.guardrails import classify_query


@pytest.mark.parametrize("q", ["hi", "hello", "Hey there", "good morning"])
def test_greetings(q):
    r = classify_query(q)
    assert r["reason"] == "greeting" and r["instant_response"] is not None


@pytest.mark.parametrize("q", ["help", "what can you do", "how does this work"])
def test_help(q):
    assert classify_query(q)["reason"] == "help"


@pytest.mark.parametrize("q", [
    "Who is Rick Sanchez?", "What dimension is Earth C-137?",
    "Which episodes feature Birdperson?",
])
def test_rm_allowed(q):
    assert classify_query(q)["allowed"] is True


@pytest.mark.parametrize("q", [
    "what's the weather today", "give me a recipe for pasta",
    "who won the football game",
])
def test_off_topic_blocked(q):
    r = classify_query(q)
    assert r["allowed"] is False and r["reason"] == "off_topic"


def test_rm_signal_overrides_blocked_word():
    assert classify_query("Does Rick write anything in an episode?")["allowed"] is True


def test_empty_blocked():
    assert classify_query("   ")["allowed"] is False