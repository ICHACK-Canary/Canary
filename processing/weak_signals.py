import re

QUESTION_WORDS = ["anyone", "why", "how", "what", "else"]
HEDGING = ["might", "seems", "just in case", "should I"]
INTENT = ["stock up", "buy extra", "grabbed more"]

def weak_signal_score(text: str) -> float:
    score = 0.0
    t = text.lower()

    if "?" in t:
        score += 0.3

    if any(w in t for w in QUESTION_WORDS):
        score += 0.3

    if any(w in t for w in HEDGING):
        score += 0.2

    if any(w in t for w in INTENT):
        score += 0.4

    return min(score, 1.0)
