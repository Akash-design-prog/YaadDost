"""What happens when Gemma, the tunnel or the network misbehaves."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.llm import client as llm
from app.main import app

api = TestClient(app)
NOTES = "Deadlock: a situation where processes wait forever for resources held by each other.\n" * 3


@pytest.fixture
def anyio_backend():
    return "asyncio"


def fake_server(monkeypatch, handler):
    real = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kw: real(transport=transport, **kw))


# --- the client turns every kind of failure into one error ------------------------------

@pytest.mark.anyio
@pytest.mark.parametrize("handler", [
    lambda r: (_ for _ in ()).throw(httpx.ReadTimeout("slow")),
    lambda r: (_ for _ in ()).throw(httpx.ConnectTimeout("no route")),
    lambda r: (_ for _ in ()).throw(httpx.ConnectError("refused")),
    lambda r: httpx.Response(530, text="tunnel is gone"),          # Cloudflare: tunnel offline
    lambda r: httpx.Response(502, text="bad gateway"),
    lambda r: httpx.Response(200, text="<html>not json</html>"),
    lambda r: httpx.Response(200, json={"unexpected": "shape"}),
    lambda r: httpx.Response(200, json={"error": "model 'gemma4:e4b' not found"}),
], ids=["read-timeout", "connect-timeout", "refused", "tunnel-530", "502", "html-body", "wrong-shape", "model-missing"])
async def test_every_failure_becomes_llm_unavailable(monkeypatch, handler):
    fake_server(monkeypatch, handler)
    with pytest.raises(llm.LLMUnavailable):
        await llm.chat([{"role": "user", "content": "hi"}])


@pytest.mark.anyio
async def test_status_is_false_when_the_model_is_not_pulled(monkeypatch):
    fake_server(monkeypatch, lambda r: httpx.Response(200, json={"models": [{"name": "llama3:8b"}]}))
    assert (await llm.status())["available"] is False


@pytest.mark.anyio
async def test_status_is_true_when_the_tagged_model_is_present(monkeypatch):
    fake_server(monkeypatch, lambda r: httpx.Response(200, json={"models": [{"name": f"{config.MODEL}"}]}))
    assert (await llm.status())["available"] is True


@pytest.mark.anyio
@pytest.mark.parametrize("handler", [
    lambda r: httpx.Response(500, text="boom"),
    lambda r: httpx.Response(200, text="garbage"),
])
async def test_status_never_raises(monkeypatch, handler):
    fake_server(monkeypatch, handler)
    assert (await llm.status())["available"] is False


# --- the app keeps working end to end -----------------------------------------------------

def test_cards_still_work_when_the_tunnel_is_dead(monkeypatch):
    fake_server(monkeypatch, lambda r: httpx.Response(530, text="gone"))
    r = api.post("/api/cards", json={"notes": NOTES, "count": 3})
    assert r.status_code == 200 and r.json()["source"] == "fallback" and r.json()["cards"]


def test_cards_still_work_when_gemma_times_out(monkeypatch):
    def slow(request):
        raise httpx.ReadTimeout("slow")
    fake_server(monkeypatch, slow)
    assert api.post("/api/cards", json={"notes": NOTES}).json()["source"] == "fallback"


def test_explain_says_so_plainly_when_gemma_is_down(monkeypatch):
    fake_server(monkeypatch, lambda r: httpx.Response(530, text="gone"))
    r = api.post("/api/explain", json={"concept": "deadlock"})
    assert r.status_code == 503 and "Gemma" in r.json()["detail"]


def test_generator_ok_but_verifier_reply_broken_keeps_the_cards(monkeypatch):
    import json
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:   # card generation
            return httpx.Response(200, json={"message": {"content": json.dumps({"cards": [{"q": "Q?", "a": "A."}]})}})
        return httpx.Response(200, json={"message": {"content": "this is not json"}})   # verification

    fake_server(monkeypatch, handler)
    body = api.post("/api/cards", json={"notes": NOTES}).json()
    assert body["source"] == "gemma" and body["verified"] is False
    assert [c["q"] for c in body["cards"]] == ["Q?"] and body["trace"][1]["step"] == "verify"


def test_nothing_usable_in_the_notes_is_a_clear_422_not_an_empty_success():
    r = api.post("/api/cards", json={"notes": "a b c d e f g h i j k l m n o p q r s t"})
    assert r.status_code == 422 and "Couldn't find anything" in r.json()["detail"]
