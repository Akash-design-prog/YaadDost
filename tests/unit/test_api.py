import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.agents import pipeline
from app.llm import generate
from app.llm.client import LLMUnavailable
from app.main import app

client = TestClient(app)

NOTES = (
    "Deadlock: a situation where processes wait forever for resources held by each other.\n"
    "Paging divides memory into fixed-size blocks, which removes external fragmentation.\n"
)


def gemma_down(monkeypatch, name):
    async def boom(*a, **k):
        raise LLMUnavailable("down")

    monkeypatch.setattr(generate, name, boom)


def test_review_endpoint():
    r = client.post("/api/review", json={"ease": 2.5, "interval": 0, "reps": 0, "grade": "easy"})
    assert r.status_code == 200 and r.json()["interval"] == 1


def test_review_rejects_bad_grade():
    assert client.post("/api/review", json={"grade": "meh"}).status_code == 422


def test_cards_validation():
    assert client.post("/api/cards", json={"notes": "too short"}).status_code == 422


def test_cards_falls_back_when_gemma_down(monkeypatch):
    gemma_down(monkeypatch, "make_cards")
    r = client.post("/api/cards", json={"notes": NOTES, "count": 5})
    body = r.json()
    assert r.status_code == 200 and body["source"] == "fallback" and body["cards"]
    assert body["verified"] is False and body["dropped"] == []


def test_cards_returns_verified_cards_and_what_was_dropped(monkeypatch):
    async def ok(notes, count, language):
        return {"cards": [{"q": "Q?", "a": "A", "checked": True}],
                "dropped": [{"q": "Bad?", "a": "X", "reason": "not in notes"}],
                "verified": True, "trace": [{"step": "generate"}]}

    monkeypatch.setattr(pipeline, "make_verified_cards", ok)
    body = client.post("/api/cards", json={"notes": NOTES}).json()
    assert body["source"] == "gemma" and body["verified"] is True
    assert body["cards"][0]["q"] == "Q?" and body["dropped"][0]["reason"] == "not in notes"


def test_explain_503_when_gemma_down(monkeypatch):
    gemma_down(monkeypatch, "explain")
    assert client.post("/api/explain", json={"concept": "deadlock"}).status_code == 503


def test_status_reports_unavailable_when_unreachable(monkeypatch):
    # nothing listens on this port, so status must degrade rather than error
    monkeypatch.setattr(config, "OLLAMA_URL", "http://127.0.0.1:9")
    r = client.get("/api/status")
    assert r.status_code == 200 and r.json()["available"] is False


def test_healthz_does_not_need_gemma(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_URL", "http://127.0.0.1:9")
    assert client.get("/healthz").json() == {"ok": True}


def test_frontend_files_served():
    assert "YaadDost" in client.get("/").text
    for path in ("css/styles.css", "js/api.js", "js/deck.js", "js/ui.js"):
        assert client.get(f"/static/{path}").status_code == 200, path
