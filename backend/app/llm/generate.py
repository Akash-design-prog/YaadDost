"""What the app asks Gemma to do: make cards, explain a concept."""
import json

from . import client, prompts
from .client import LLMUnavailable


async def make_cards(notes: str, count: int, language: str) -> list[dict]:
    messages = prompts.cards_messages(notes, count, language)
    last_err: Exception | None = None
    for _ in range(2):  # one retry if the model returns malformed JSON
        raw = await client.chat(messages, prompts.CARDS_SCHEMA)
        try:
            cards = json.loads(raw)["cards"]
            cleaned = [
                {"q": str(c["q"]).strip(), "a": str(c["a"]).strip()}
                for c in cards
                if str(c.get("q", "")).strip() and str(c.get("a", "")).strip()
            ]
            if cleaned:
                return cleaned[:count]
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
            last_err = e
    raise LLMUnavailable(f"model returned no usable cards: {last_err}")


async def explain(concept: str, notes: str, language: str) -> str:
    return (await client.chat(prompts.explain_messages(concept, notes, language))).strip()
