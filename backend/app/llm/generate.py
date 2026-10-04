"""What the app asks Gemma to do: make cards, explain a concept."""
import json
import re

from . import client, prompts
from .client import LLMUnavailable

_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f]")


def clean_text(s: str) -> str:
    """Undo LaTeX habits: Gemma sometimes writes \\times inside JSON, which decodes to TAB + 'imes'."""
    s = s.replace("\t" + "imes", "×").replace("\t", " ")
    s = s.replace("$", "")
    s = _CONTROL.sub("", s)
    return re.sub(r" {2,}", " ", s).strip()


async def make_cards(notes: str, count: int, language: str) -> list[dict]:
    messages = prompts.cards_messages(notes, count, language)
    last_err: Exception | None = None
    for _ in range(2):  # one retry if the model returns malformed JSON
        raw = await client.chat(messages, prompts.CARDS_SCHEMA)
        try:
            cards = json.loads(raw)["cards"]
            cleaned = [
                {"q": clean_text(str(c["q"])), "a": clean_text(str(c["a"]))}
                for c in cards
                if clean_text(str(c.get("q", ""))) and clean_text(str(c.get("a", "")))
            ]
            if cleaned:
                return cleaned[:count]
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
            last_err = e
    raise LLMUnavailable(f"model returned no usable cards: {last_err}")


async def explain(concept: str, notes: str, language: str) -> str:
    raw = await client.chat(prompts.explain_messages(concept, notes, language))
    return "\n".join(clean_text(line) for line in raw.splitlines()).strip()
