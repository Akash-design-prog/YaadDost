from fastapi import APIRouter

from app.llm import client

router = APIRouter()


@router.get("/status")
async def status():
    return await client.status()
