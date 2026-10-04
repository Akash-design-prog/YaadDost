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


# --- regression: LaTeX garbage seen in the second real Gemma run -------------

BS = chr(92)   # a single backslash, built explicitly so editors/shells can't swallow it
TAB = chr(9)


def test_clean_text_fixes_the_real_corrupted_strings():
    # what JSON decoding produced from Gemma's LaTeX times sign: TAB + "imes"
    assert generate.clean_text(f"P = V {TAB}imes I") == "P = V × I"
    assert generate.clean_text("Power ($P$) ka product") == "Power (P) ka product"
    assert generate.clean_text("($R = R1 + R2 + R3$)") == "(R = R1 + R2 + R3)"
    assert generate.clean_text(f"a{TAB}b  c{chr(8)}d") == "a b cd"
    assert generate.clean_text("  plain text  ") == "plain text"


async def _async(value):
    return value


@pytest.mark.anyio
async def test_unescaped_latex_in_model_json_is_cleaned(monkeypatch):
    # The model wrote a LaTeX times sign with ONE backslash inside JSON; json.loads reads backslash-t as a TAB.
    raw = '{"cards": [{"q": "Formula?", "a": "$P = V ' + BS + 'times I$"}]}'
    monkeypatch.setattr(client, "chat", lambda *a, **k: _async(raw))
    assert (await generate.make_cards("notes", 3, "english"))[0]["a"] == "P = V × I"


@pytest.mark.anyio
async def test_explanations_keep_lines_but_lose_latex(monkeypatch):
    nl = chr(10)
    monkeypatch.setattr(client, "chat", lambda *a, **k: _async(f"Line one $x${nl}{nl}Line two"))
    assert await generate.explain("x", "", "english") == f"Line one x{nl}{nl}Line two"
