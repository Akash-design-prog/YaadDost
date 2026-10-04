from fastapi import APIRouter

from app.services import srs

from .schemas import ReviewIn

router = APIRouter()


@router.post("/review")
def review(body: ReviewIn):
    return srs.review(body.ease, body.interval, body.reps, body.grade)
