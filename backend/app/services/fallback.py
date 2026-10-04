"""Rule-based card maker used when no Gemma server is reachable.

It is deliberately simple: definitions ("X: Y", "X - Y", "X is Y") become Q/A cards,
other sentences become fill-in-the-blank cards. It keeps the app usable offline, but the
cards are much weaker than Gemma's, and the UI says so.
"""
import re

_DEF_PATTERNS = [
    re.compile(r"^\s*[-*\d.)]*\s*([^:]{2,60}):\s+(.{8,})$"),
    re.compile(r"^\s*[-*\d.)]*\s*([^-–—]{2,60})\s+[-–—]\s+(.{8,})$"),
    re.compile(r"^\s*([A-Z][^.]{1,50}?)\s+(?:is|are|means|refers to)\s+(.{8,})$"),
]
_STOP = {"the", "and", "that", "this", "with", "from", "have", "which", "their", "there", "about"}


def _blank_card(sentence: str) -> dict | None:
    words = re.findall(r"[A-Za-z][A-Za-z\-]{4,}", sentence)
    words = [w for w in words if w.lower() not in _STOP]
    if not words:
        return None
    target = max(words, key=len)
    return {"q": "Fill in the blank: " + sentence.replace(target, "_____", 1), "a": target}


def make_cards(notes: str, count: int) -> list[dict]:
    cards: list[dict] = []
    seen: set[str] = set()
    for line in re.split(r"\n+", notes):
        line = line.strip()
        if len(line) < 12:
            continue
        card = None
        for pat in _DEF_PATTERNS:
            m = pat.match(line)
            if m:
                term, definition = m.group(1).strip(), m.group(2).strip()
                card = {"q": f"What is {term}?", "a": definition}
                break
        if card is None:
            sentences = re.split(r"(?<=[.!?])\s+", line)
            for s in sentences:
                if len(s) >= 25 and (card := _blank_card(s)):
                    break
        if card and card["q"] not in seen:
            seen.add(card["q"])
            cards.append(card)
        if len(cards) >= count:
            break
    return cards
