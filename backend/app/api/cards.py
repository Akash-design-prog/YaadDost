from fastapi import APIRouter, Depends, HTTPException

from app.core import config
from app.core.ratelimit import rate_limit
from app.agents import pipeline
from app.llm.client import LLMUnavailable
from app.services import fallback

from .schemas import CardsIn

router = APIRouter()


@router.post("/cards", dependencies=[Depends(rate_limit)])
async def cards(body: CardsIn):
    try:
        out = await pipeline.make_verified_cards(body.notes, body.count, body.language)
        source = "gemma"
    except LLMUnavailable:
        out = {"cards": fallback.make_cards(body.notes, body.count), "dropped": [], "verified": False, "trace": []}
        source = "fallback"
    if not out["cards"]:
        raise HTTPException(422, "Couldn't find anything to turn into cards. Try longer, fuller notes.")
    return {**out, "source": source, "model": config.MODEL if source == "gemma" else None}
