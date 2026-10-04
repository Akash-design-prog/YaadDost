from fastapi import APIRouter, HTTPException

from app.core import config
from app.llm import generate
from app.llm.client import LLMUnavailable
from app.services import fallback

from .schemas import CardsIn

router = APIRouter()


@router.post("/cards")
async def cards(body: CardsIn):
    try:
        result, source = await generate.make_cards(body.notes, body.count, body.language), "gemma"
    except LLMUnavailable:
        result, source = fallback.make_cards(body.notes, body.count), "fallback"
    if not result:
        raise HTTPException(422, "Couldn't find anything to turn into cards. Try longer, fuller notes.")
    return {"cards": result, "source": source, "model": config.MODEL if source == "gemma" else None}
