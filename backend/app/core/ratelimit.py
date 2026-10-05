"""Per-IP rate limit for the endpoints that use the Gemma server (each call costs real GPU time)."""
import math
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from . import config


class SlidingWindow:
    """Allow `limit` hits per `window` seconds for each key. A limit of 0 or less means unlimited."""

    def __init__(self, limit: int, window: float = 60.0, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> float | None:
        """Record a hit. Returns None if allowed, else the seconds to wait."""
        if self.limit <= 0:
            return None
        now = self.clock()
        q = self.hits[key]
        while q and now - q[0] >= self.window:
            q.popleft()
        if len(q) >= self.limit:
            return self.window - (now - q[0])
        q.append(now)
        if len(self.hits) > 10_000:   # don't grow forever: forget keys with nothing recent
            self.hits = defaultdict(deque, {k: v for k, v in self.hits.items() if v and now - v[-1] < self.window})
        return None


limiter = SlidingWindow(config.RATE_LIMIT_PER_MIN)


def client_ip(request: Request) -> str:
    # Behind Render's proxy the last X-Forwarded-For entry is the one the proxy itself added.
    # Earlier entries can be forged by the caller, so they are ignored.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


async def rate_limit(request: Request):
    wait = limiter.check(client_ip(request))
    if wait is not None:
        seconds = math.ceil(wait)
        raise HTTPException(
            429, f"That's a lot of requests in a minute. Try again in {seconds} seconds.", headers={"Retry-After": str(seconds)}
        )
