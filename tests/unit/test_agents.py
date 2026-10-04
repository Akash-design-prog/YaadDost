import json

import pytest

from app.agents import pipeline, verifier
from app.llm import client, generate
from app.llm.client import LLMUnavailable

NOTES = "Deadlock needs four conditions. HTTPS uses port 443."
CARDS = [
    {"q": "Which port does HTTPS use?", "a": "Port 443."},
    {"q": "Which port does HTTPS use?", "a": "Port 8080."},
    {"q": "Who invented the Banker's algorithm?", "a": "Dijkstra."},
]


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def _ret(v):
    return v


def fake_chat(monkeypatch, reply):
    async def chat(messages, fmt=None):
        chat.calls.append((messages, fmt))
        if isinstance(reply, Exception):
            raise reply
        return reply

    chat.calls = []
    monkeypatch.setattr(client, "chat", chat)
    return chat


def verdicts(*pairs):
    return json.dumps({"verdicts": [{"id": i, "supported": s, "reason": r} for i, s, r in pairs]})


# --- verifier ---------------------------------------------------------------

@pytest.mark.anyio
async def test_verifier_sends_notes_and_numbered_cards_with_schema(monkeypatch):
    chat = fake_chat(monkeypatch, verdicts((1, True, "ok")))
    await verifier.check(NOTES, CARDS[:1])
    messages, fmt = chat.calls[0]
    assert NOTES in messages[1]["content"] and "1. Q: Which port does HTTPS use?" in messages[1]["content"]
    assert fmt["required"] == ["verdicts"]


@pytest.mark.anyio
async def test_verifier_maps_verdicts_to_zero_based_indexes(monkeypatch):
    fake_chat(monkeypatch, verdicts((1, True, "ok"), (2, False, "notes say 443"), (3, False, "not in notes")))
    got = await verifier.check(NOTES, CARDS)
    assert got[0]["supported"] is True and got[1] == {"supported": False, "reason": "notes say 443"}
    assert got[2]["supported"] is False


@pytest.mark.anyio
async def test_verifier_ignores_out_of_range_and_non_boolean_verdicts(monkeypatch):
    raw = json.dumps({"verdicts": [
        {"id": 0, "supported": True, "reason": ""},          # ids are 1-based
        {"id": 99, "supported": True, "reason": ""},
        {"id": 1, "supported": "yes", "reason": ""},         # not a boolean
        {"id": 2, "supported": False, "reason": "$bad$"},
    ]})
    fake_chat(monkeypatch, raw)
    got = await verifier.check(NOTES, CARDS)
    assert list(got) == [1] and got[1]["reason"] == "bad"


@pytest.mark.anyio
@pytest.mark.parametrize("raw", ["not json", "{}", '{"verdicts": [{"supported": true}]}', '{"verdicts": 5}'])
async def test_verifier_raises_on_unusable_output(monkeypatch, raw):
    fake_chat(monkeypatch, raw)
    with pytest.raises(LLMUnavailable):
        await verifier.check(NOTES, CARDS)


# --- pipeline ---------------------------------------------------------------

def stub(monkeypatch, cards=CARDS, check=None):
    monkeypatch.setattr(generate, "make_cards", lambda *a, **k: _ret(list(cards)))
    if isinstance(check, Exception):
        async def boom(*a, **k):
            raise check
        monkeypatch.setattr(verifier, "check", boom)
    else:
        monkeypatch.setattr(verifier, "check", lambda *a, **k: _ret(check))


@pytest.mark.anyio
async def test_pipeline_drops_unsupported_cards_and_explains_why(monkeypatch):
    stub(monkeypatch, check={0: {"supported": True, "reason": ""},
                             1: {"supported": False, "reason": "notes say 443"},
                             2: {"supported": False, "reason": "not in notes"}})
    out = await pipeline.make_verified_cards(NOTES, 5, "english")
    assert out["verified"] is True
    assert out["cards"] == [{**CARDS[0], "checked": True}]
    assert [d["reason"] for d in out["dropped"]] == ["notes say 443", "not in notes"]
    assert [t["step"] for t in out["trace"]] == ["generate", "verify"]
    assert out["trace"][1]["kept"] == 1 and out["trace"][1]["dropped"] == 2


@pytest.mark.anyio
async def test_pipeline_keeps_cards_the_verifier_said_nothing_about(monkeypatch):
    stub(monkeypatch, check={0: {"supported": True, "reason": ""}})
    out = await pipeline.make_verified_cards(NOTES, 5, "english")
    assert [c["checked"] for c in out["cards"]] == [True, False, False] and out["dropped"] == []


@pytest.mark.anyio
async def test_pipeline_survives_a_failing_verifier(monkeypatch):
    stub(monkeypatch, check=LLMUnavailable("down"))
    out = await pipeline.make_verified_cards(NOTES, 5, "english")
    assert out["cards"] == CARDS and out["verified"] is False and out["dropped"] == []
    assert "error" in out["trace"][1]


@pytest.mark.anyio
async def test_pipeline_does_not_return_nothing_when_everything_is_rejected(monkeypatch):
    stub(monkeypatch, check={i: {"supported": False, "reason": "x"} for i in range(3)})
    out = await pipeline.make_verified_cards(NOTES, 5, "english")
    assert out["cards"] == CARDS and out["verified"] is False


@pytest.mark.anyio
async def test_pipeline_propagates_generator_failure(monkeypatch):
    async def boom(*a, **k):
        raise LLMUnavailable("down")
    monkeypatch.setattr(generate, "make_cards", boom)
    with pytest.raises(LLMUnavailable):
        await pipeline.make_verified_cards(NOTES, 5, "english")
