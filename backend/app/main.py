from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api import cards, explain, review, status

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="YaadDost", docs_url=None, redoc_url=None)   # no public Swagger page

FRIENDLY_FIELDS = {"notes": "your notes", "count": "the card count", "language": "the language", "concept": "the concept"}


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    """A short, readable message. FastAPI's default echoes the rejected input back, and a NaN in that
    echo cannot be written as JSON, which turned a bad request into a server crash."""
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    field = FRIENDLY_FIELDS.get(field, field)
    reason = first.get("msg", "it could not be read")
    return JSONResponse({"detail": f"Check {field or 'the request'}: {reason}"}, status_code=422)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    # Our page loads only its own scripts and styles, so nothing injected can run or phone home.
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'")
    return response

for module in (status, cards, explain, review):
    app.include_router(module.router, prefix="/api")


@app.get("/healthz")
def healthz():
    # Cheap liveness check for Render; does not touch Gemma.
    return {"ok": True}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)   # no icon yet; answer quietly instead of a 404 in the console


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
