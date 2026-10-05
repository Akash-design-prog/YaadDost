from fastapi.testclient import TestClient

from app.core import ratelimit
from app.core.ratelimit import SlidingWindow
from app.main import app

NOTES = "Deadlock: a situation where processes wait forever for resources held by each other."


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_allows_up_to_the_limit_then_blocks_with_wait_time():
    clock = Clock()
    w = SlidingWindow(3, 60, clock)
    assert [w.check("a") for _ in range(3)] == [None, None, None]
    clock.now += 10
    assert w.check("a") == 50          # oldest hit was 10s ago, so 50s to wait


def test_window_slides_and_frees_up():
    clock = Clock()
    w = SlidingWindow(2, 60, clock)
    w.check("a"), w.check("a")
    assert w.check("a") is not None
    clock.now += 60
    assert w.check("a") is None


def test_keys_are_independent():
    w = SlidingWindow(1, 60, Clock())
    assert w.check("a") is None and w.check("b") is None and w.check("a") is not None


def test_zero_limit_means_unlimited():
    w = SlidingWindow(0, 60, Clock())
    assert all(w.check("a") is None for _ in range(500))


def test_memory_is_pruned_when_many_visitors_come_and_go():
    clock = Clock()
    w = SlidingWindow(5, 60, clock)
    for i in range(10_001):
        w.check(f"ip{i}")
    clock.now += 120
    w.check("fresh")
    assert len(w.hits) < 100


def test_api_returns_429_with_retry_after(monkeypatch):
    monkeypatch.setattr(ratelimit, "limiter", SlidingWindow(2, 60, Clock()))
    client = TestClient(app)
    ok = [client.post("/api/cards", json={"notes": NOTES}).status_code for _ in range(2)]
    blocked = client.post("/api/cards", json={"notes": NOTES})
    assert ok == [200, 200] and blocked.status_code == 429
    detail = blocked.json()["detail"]
    assert blocked.headers["retry-after"] == "60" and "try again in 60 seconds" in detail.lower()
    assert "please" not in detail.lower()


def test_explain_shares_the_limit_but_cheap_endpoints_are_free(monkeypatch):
    monkeypatch.setattr(ratelimit, "limiter", SlidingWindow(1, 60, Clock()))
    client = TestClient(app)
    client.post("/api/cards", json={"notes": NOTES})
    assert client.post("/api/explain", json={"concept": "deadlock"}).status_code == 429
    for path in ("/healthz", "/api/status"):
        assert client.get(path).status_code == 200
    assert client.post("/api/review", json={"grade": "good"}).status_code == 200


def test_forwarded_header_uses_the_proxy_added_entry_not_a_forged_one(monkeypatch):
    monkeypatch.setattr(ratelimit, "limiter", SlidingWindow(1, 60, Clock()))
    client = TestClient(app)
    # the caller forges the first entry; the proxy appends the real address last
    first = client.post("/api/cards", json={"notes": NOTES}, headers={"X-Forwarded-For": "1.1.1.1, 9.9.9.9"})
    forged_again = client.post("/api/cards", json={"notes": NOTES}, headers={"X-Forwarded-For": "2.2.2.2, 9.9.9.9"})
    other_visitor = client.post("/api/cards", json={"notes": NOTES}, headers={"X-Forwarded-For": "2.2.2.2, 8.8.8.8"})
    assert (first.status_code, forged_again.status_code, other_visitor.status_code) == (200, 429, 200)
