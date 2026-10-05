import pytest

from app.core import ratelimit


@pytest.fixture(autouse=True)
def fresh_rate_limiter(monkeypatch):
    """Every test starts with an empty, generous limiter so tests never affect each other."""
    monkeypatch.setattr(ratelimit, "limiter", ratelimit.SlidingWindow(1000))
