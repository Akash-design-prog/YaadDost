"""Run the real card generator against a live Gemma server and score the output.

    set OLLAMA_URL=https://<your-colab-tunnel>.trycloudflare.com      (PowerShell: $env:OLLAMA_URL="...")
    python evals/run_eval.py --language hinglish --count 8

Writes evals/results/<language>.json and prints every card so you can read them yourself.
Automatic scores only catch gross problems; reading the cards is part of the evaluation.
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "evals")]

from app.core import config  # noqa: E402
from app.llm import client, generate  # noqa: E402
from scoring import score_cards  # noqa: E402


async def main(language: str, count: int):
    st = await client.status()
    print(f"server: {config.OLLAMA_URL}\nmodel : {config.MODEL}  (available: {st['available']})")
    if not st["available"]:
        sys.exit("Gemma is not reachable. Check OLLAMA_URL and that the model finished downloading.")

    results = []
    for path in sorted((ROOT / "evals" / "samples").glob("*.txt")):
        notes = path.read_text(encoding="utf-8")
        t0 = time.time()
        try:
            cards = await generate.make_cards(notes, count, language)
            err = None
        except client.LLMUnavailable as e:
            cards, err = [], str(e)
        secs = round(time.time() - t0, 1)
        scores = score_cards(cards, notes, language)
        results.append({"sample": path.name, "seconds": secs, "error": err, "scores": scores, "cards": cards})

        print(f"\n=== {path.name}  ({secs}s)  {scores}" + (f"  ERROR: {err}" if err else ""))
        for c in cards:
            print(f"  Q: {c['q']}\n  A: {c['a']}\n")

    out = ROOT / "evals" / "results"
    out.mkdir(exist_ok=True)
    (out / f"{language}.json").write_text(json.dumps({"model": config.MODEL, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved {out / (language + '.json')}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--language", choices=["english", "hinglish"], default="hinglish")
    ap.add_argument("--count", type=int, default=8)
    a = ap.parse_args()
    asyncio.run(main(a.language, a.count))
