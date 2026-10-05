"""Thin client for an Ollama server running an open-weight Gemma model.

The server is yours: locally, or in a Colab notebook behind a tunnel (see colab/).
Nothing here talks to a closed API.
"""
import httpx

from app.core import config


class LLMUnavailable(Exception):
    pass


def _headers() -> dict:
    # Some tunnels (ngrok free) show an interstitial unless this header is set.
    return {"ngrok-skip-browser-warning": "1"}


async def status() -> dict:
    try:
        # a short connect timeout, so a dead address shows "Offline mode" in about 2 seconds instead of 5
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0), headers=_headers()) as c:
            r = await c.get(f"{config.OLLAMA_URL}/api/tags")
            r.raise_for_status()
            names = [m.get("name", "") for m in r.json().get("models", [])]
        return {"available": any(n.startswith(config.MODEL) for n in names), "model": config.MODEL}
    except Exception:
        return {"available": False, "model": config.MODEL}


async def chat(messages: list[dict], fmt: dict | None = None) -> str:
    body = {"model": config.MODEL, "messages": messages, "stream": False, "options": {"temperature": 0.3}}
    if fmt:
        body["format"] = fmt
    try:
        async with httpx.AsyncClient(timeout=config.LLM_TIMEOUT, headers=_headers()) as c:
            r = await c.post(f"{config.OLLAMA_URL}/api/chat", json=body)
            r.raise_for_status()
            return r.json()["message"]["content"]
    except (httpx.HTTPError, KeyError, ValueError) as e:
        raise LLMUnavailable(str(e)) from e
