import json

import httpx
import pytest

from app.llm import client, generate


@pytest.fixture
def anyio_backend():
    return "asyncio"


def fake_ollama(monkeypatch, handler):
    real = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(client.httpx, "AsyncClient", lambda **kw: real(transport=transport, **kw))


@pytest.mark.anyio
async def test_parses_schema_json_and_retries(monkeypatch):
    replies = iter(["not json", json.dumps({"cards": [{"q": " Why? ", "a": " Because. "}, {"q": "", "a": "x"}]})])

    def handler(request: httpx.Request):
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["format"]["required"] == ["cards"] and body["stream"] is False
        return httpx.Response(200, json={"message": {"content": next(replies)}})

    fake_ollama(monkeypatch, handler)
    assert await generate.make_cards("notes", 5, "english") == [{"q": "Why?", "a": "Because."}]


@pytest.mark.anyio
async def test_unreachable_raises(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("nope")

    fake_ollama(monkeypatch, handler)
    with pytest.raises(client.LLMUnavailable):
        await generate.make_cards("notes", 5, "english")
