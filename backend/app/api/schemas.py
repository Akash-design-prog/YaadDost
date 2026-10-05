from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import MAX_NOTES

Language = Literal["english", "hinglish"]


class CardsIn(BaseModel):
    notes: str = Field(min_length=20, max_length=MAX_NOTES)
    language: Language = "hinglish"
    count: int = Field(default=10, ge=1, le=25)


class ExplainIn(BaseModel):
    concept: str = Field(min_length=2, max_length=200)
    notes: str = Field(default="", max_length=MAX_NOTES)
    language: Language = "hinglish"


class ReviewIn(BaseModel):
    # Bounds keep nonsense (NaN, negative or astronomically large values) out of the scheduler.
    ease: float = Field(default=2.5, ge=1.3, le=10)
    interval: int = Field(default=0, ge=0, le=36500)
    reps: int = Field(default=0, ge=0, le=1000)
    grade: Literal["again", "hard", "good", "easy"]
