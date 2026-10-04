"""Seeded test for the Verifier agent: can it catch cards we know are wrong?

    python evals/run_verifier_eval.py        (needs a running Gemma, same setup as run_eval.py)

Cases mix good cards (verbatim, paraphrased, Hinglish) with planted bad ones (wrong number, contradiction,
true-but-not-in-notes, invented, reversed). The number that matters most is false accepts: a bad card let through.
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend")]

from app.agents import verifier  # noqa: E402
from app.core import config  # noqa: E402
from app.llm import client  # noqa: E402


async def main():
    st = await client.status()
    print(f"server: {config.OLLAMA_URL}  model: {config.MODEL}  available: {st['available']}")
    if not st["available"]:
        sys.exit("Gemma is not reachable.")

    data = json.loads((ROOT / "evals" / "verifier_cases.json").read_text(encoding="utf-8"))
    cases = data["cases"]
    runs = 3   # the model is not perfectly deterministic, so repeat and report every run
    summary = []
    for run in range(1, runs + 1):
        got = await verifier.check(data["notes"], cases)
        fa = fr = missing = 0
        print(f"\n--- run {run}")
        for i, c in enumerate(cases):
            v = got.get(i)
            if v is None:
                missing += 1
                mark = "NO VERDICT"
            elif v["supported"] == c["supported"]:
                mark = "ok"
            elif v["supported"]:
                fa += 1
                mark = "FALSE ACCEPT (bad card let through)"
            else:
                fr += 1
                mark = "false reject (good card dropped)"
            print(f"  [{mark}] expect={'keep' if c['supported'] else 'drop'}  {c['q']} -> {c['a']}  ({c['why']})"
                  + (f"\n        verifier: {v['reason']}" if v else ""))
        summary.append({"false_accepts": fa, "false_rejects": fr, "no_verdict": missing})
        print(f"  false accepts: {fa}   false rejects: {fr}   no verdict: {missing}   of {len(cases)}")

    out = ROOT / "evals" / "results"
    out.mkdir(exist_ok=True)
    (out / "verifier.json").write_text(json.dumps({"model": config.MODEL, "runs": summary}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
