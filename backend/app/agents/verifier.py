"""Agent step 2: a second Gemma pass that checks every card's answer against the notes."""
import json

from app.llm import client, prompts
from app.llm.client import LLMUnavailable
from app.llm.generate import clean_text


async def check(notes: str, cards: list[dict]) -> dict[int, dict]:
    """Return {card index (0-based): {"supported": bool, "reason": str}}.

    Cards the model gave no usable verdict for are simply absent from the result.
    Raises LLMUnavailable if the server is down or the reply is not usable JSON.
    """
    raw = await client.chat(prompts.verify_messages(notes, cards), prompts.VERDICTS_SCHEMA)
    try:
        items = json.loads(raw)["verdicts"]
        out: dict[int, dict] = {}
        for v in items:
            i = int(v["id"]) - 1
            if 0 <= i < len(cards) and isinstance(v["supported"], bool):
                out[i] = {"supported": v["supported"], "reason": clean_text(str(v.get("reason", "")))}
        return out
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, AttributeError) as e:
        raise LLMUnavailable(f"verifier returned unusable output: {e}") from e
