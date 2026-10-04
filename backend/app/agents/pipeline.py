"""The card agent: Generator (Gemma) -> Verifier (Gemma) -> only supported cards survive."""
import time

from app.llm import generate
from app.llm.client import LLMUnavailable

from . import verifier


async def make_verified_cards(notes: str, count: int, language: str) -> dict:
    """Returns {"cards", "dropped", "verified", "trace"}.

    Raises LLMUnavailable only if the generator step fails. If the verifier step fails, the cards
    are still returned, marked verified=False, so a flaky second call never loses the user's cards.
    """
    trace = []

    t0 = time.time()
    cards = await generate.make_cards(notes, count, language)
    trace.append({"step": "generate", "seconds": round(time.time() - t0, 1), "cards": len(cards)})

    t0 = time.time()
    try:
        verdicts = await verifier.check(notes, cards)
    except LLMUnavailable as e:
        trace.append({"step": "verify", "seconds": round(time.time() - t0, 1), "error": str(e)})
        return {"cards": cards, "dropped": [], "verified": False, "trace": trace}

    kept, dropped = [], []
    for i, card in enumerate(cards):
        v = verdicts.get(i)
        if v is None:
            kept.append({**card, "checked": False})        # no verdict: keep, but don't claim it was checked
        elif v["supported"]:
            kept.append({**card, "checked": True})
        else:
            dropped.append({**card, "reason": v["reason"]})
    trace.append({"step": "verify", "seconds": round(time.time() - t0, 1), "kept": len(kept), "dropped": len(dropped)})

    if not kept:
        # Every card rejected: more likely a confused verifier than a hopeless generator. Keep the
        # originals unchecked rather than hand the student nothing.
        return {"cards": cards, "dropped": [], "verified": False, "trace": trace}
    return {"cards": kept, "dropped": dropped, "verified": True, "trace": trace}
