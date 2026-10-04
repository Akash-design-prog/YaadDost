import pytest
from fastapi.testclient import TestClient

from app.core import config
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
    assert r.status_code == 200 and r.json()["source"] == "fallback" and r.json()["cards"]


def test_cards_uses_gemma_when_available(monkeypatch):
    async def ok(notes, count, language):
        return [{"q": "Q?", "a": "A"}]

    monkeypatch.setattr(generate, "make_cards", ok)
    r = client.post("/api/cards", json={"notes": NOTES})
    assert r.json()["source"] == "gemma" and r.json()["cards"] == [{"q": "Q?", "a": "A"}]


def test_explain_503_when_gemma_down(monkeypatch):
    gemma_down(monkeypatch, "explain")
    assert client.post("/api/explain", json={"concept": "deadlock"}).status_code == 503


def test_status_reports_unavailable_when_unreachable(monkeypatch):
    # nothing listens on this port, so status must degrade rather than error
    monkeypatch.setattr(config, "OLLAMA_URL", "http://127.0.0.1:9")
    r = client.get("/api/status")
    assert r.status_code == 200 and r.json()["available"] is False


def test_frontend_files_served():
    assert "YaadDost" in client.get("/").text
    for path in ("css/styles.css", "js/api.js", "js/deck.js", "js/ui.js"):
        assert client.get(f"/static/{path}").status_code == 200, path
