from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import cards, explain, review, status

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="YaadDost")

for module in (status, cards, explain, review):
    app.include_router(module.router, prefix="/api")


@app.get("/healthz")
def healthz():
    # Cheap liveness check for Render; does not touch Gemma.
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
