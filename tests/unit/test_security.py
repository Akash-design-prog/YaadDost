import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agents import pipeline
from app.core import config
from app.main import app

client = TestClient(app)
FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
NOTES = "Deadlock: a situation where processes wait forever for resources held by each other."


# --- card text must never run as HTML --------------------------------------------------

def test_frontend_never_writes_model_output_as_html():
    # Gemma output is untrusted. The only safe sinks are textContent / createElement.
    banned = re.compile(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function")
    for js in (FRONTEND / "js").glob("*.js"):
        assert not banned.search(js.read_text(encoding="utf-8")), f"{js.name} uses an HTML sink"


def test_markup_in_cards_is_returned_as_plain_data(monkeypatch):
    evil = "<img src=x onerror=alert(1)><script>alert(2)</script>"

    async def fake(notes, count, language):
        return {"cards": [{"q": evil, "a": evil, "checked": True}], "dropped": [], "verified": True, "trace": []}

    monkeypatch.setattr(pipeline, "make_verified_cards", fake)
    r = client.post("/api/cards", json={"notes": NOTES})
    assert r.headers["content-type"].startswith("application/json")   # never rendered as a page
    assert r.json()["cards"][0]["q"] == evil


def test_security_headers_on_every_kind_of_response():
    for resp in (client.get("/"), client.get("/static/js/ui.js"), client.get("/healthz"), client.get("/nope")):
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert "default-src 'self'" in resp.headers["content-security-policy"]
        assert "frame-ancestors 'none'" in resp.headers["content-security-policy"]


def test_page_has_no_inline_script_or_style_that_the_csp_would_block():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"<script(?![^>]*\bsrc=)", html), "inline <script> would be blocked by the CSP"
    assert "<style" not in html and " style=" not in html
    assert not re.search(r"\son\w+\s*=", html), "inline event handler would be blocked by the CSP"


def test_swagger_pages_are_not_public():
    assert client.get("/docs").status_code == 404 and client.get("/redoc").status_code == 404


# --- input limits ----------------------------------------------------------------------

@pytest.mark.parametrize("body", [
    {"notes": "x" * (config.MAX_NOTES + 1)},
    {"notes": NOTES, "count": 26},
    {"notes": NOTES, "count": 0},
    {"notes": NOTES, "language": "klingon"},
    {"notes": 123},
    {},
])
def test_cards_rejects_bad_input(body):
    assert client.post("/api/cards", json=body).status_code == 422


def test_cards_accepts_notes_at_exactly_the_limit():
    assert client.post("/api/cards", json={"notes": ("Deadlock: waiting. " * 500)[: config.MAX_NOTES]}).status_code == 200


def test_explain_rejects_oversized_concept_and_notes():
    assert client.post("/api/explain", json={"concept": "x" * 201}).status_code == 422
    assert client.post("/api/explain", json={"concept": "ok", "notes": "x" * (config.MAX_NOTES + 1)}).status_code == 422


@pytest.mark.parametrize("body", [
    {"grade": "good", "ease": 0},
    {"grade": "good", "ease": 1e9},
    {"grade": "good", "interval": -1},
    {"grade": "good", "interval": 10**12},
    {"grade": "good", "reps": 10**6},
    {"grade": "good", "ease": "abc"},
])
def test_review_rejects_nonsense_state(body):
    assert client.post("/api/review", json=body).status_code == 422


def test_review_rejects_non_finite_numbers():
    for raw in (b'{"grade":"good","ease":NaN}', b'{"grade":"good","ease":Infinity}'):
        r = client.post("/api/review", content=raw, headers={"Content-Type": "application/json"})
        assert r.status_code == 422 and "ease" in r.json()["detail"], raw


def test_validation_errors_are_one_readable_sentence_that_never_echoes_the_input():
    secret = "my-private-notes-" * 3
    r = client.post("/api/cards", json={"notes": secret, "count": 999})
    detail = r.json()["detail"]
    assert r.status_code == 422 and isinstance(detail, str) and detail.startswith("Check ")
    assert secret not in detail
    banned = ("invalid", "please", "you entered")
    assert not any(word in detail.lower() for word in banned)   # the copy rules in docs/DESIGN.md


def test_malformed_json_is_a_client_error_not_a_crash():
    r = client.post("/api/cards", content=b"{not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422


# --- static file serving ---------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "/static/../backend/app/main.py",
    "/static/%2e%2e/backend/app/main.py",
    "/static/..%2fbackend%2fapp%2fmain.py",
    "/static/../../README.md",
])
def test_static_cannot_escape_the_frontend_folder(path):
    r = client.get(path)
    assert r.status_code in (404, 400) and "FastAPI(" not in r.text and "# YaadDost" not in r.text
