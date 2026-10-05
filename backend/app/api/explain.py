from fastapi import APIRouter, Depends, HTTPException

from app.core import config
from app.core.ratelimit import rate_limit
from app.llm import generate
from app.llm.client import LLMUnavailable

from .schemas import ExplainIn

router = APIRouter()


@router.post("/explain", dependencies=[Depends(rate_limit)])
async def explain(body: ExplainIn):
    try:
        text = await generate.explain(body.concept, body.notes, body.language)
    except LLMUnavailable:
        raise HTTPException(503, "Gemma isn't connected right now, so explanations are unavailable.")
    return {"text": text, "model": config.MODEL}
