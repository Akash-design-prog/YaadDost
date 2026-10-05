# Evaluation results

Model: `gemma4:e4b` through Ollama on a Colab T4 GPU. Raw logs are in `evals/baseline/`. Reproduce with
`colab/eval_on_colab.ipynb`.

## What was measured

| Check | Script | Result |
|---|---|---|
| Card generation, English | `evals/run_eval.py --language english` | 4 sample sets, 29 cards, 0 duplicates, no invented facts found on reading all of them |
| Card generation, Hinglish | `evals/run_eval.py --language hinglish` | 4 sample sets, 30 cards, 0 duplicates, no wrong facts found on reading all of them |
| Verifier on planted errors | `evals/run_verifier_eval.py`, 3 runs | 12 cases (6 good, 6 planted wrong): **0 false accepts, 0 false rejects, 0 missing verdicts in all 3 runs** |
| Speed | generation, per sample set | about 13 to 19 seconds on the T4 |
| **Full pipeline through the app** | `POST /api/cards` (Generator then Verifier) over 4 note sets x 2 languages, plus `/api/explain` | 8 of 8 requests answered by Gemma, every card marked checked, 60 cards kept, **0 removed**. 29 to 45 seconds per request (generate 17 to 23 s, verify 13 to 21 s) through a public tunnel. Explanation endpoint worked. |

The planted wrong cards were: a wrong number, a contradiction, a true-but-not-in-the-notes fact, an invented
explanation, a reversed meaning, and a topic the notes never cover. The good cards included verbatim,
paraphrased, and Hinglish-translated answers. The Verifier handled all of them, and its stated reasons matched
the real reason each time.

## What changed because of the evaluation

| Found in a real run | Fix |
|---|---|
| Near-duplicate cards when asked for more cards than the notes support | Prompt: one card per fact, fewer cards instead of padding; the count is a maximum |
| Instructions leaking into questions ("(List the four conditions)") and answer fragments ("Voltage (V) ke.") | Prompt rules for self-contained questions and full-sentence answers |
| LaTeX in answers; `\times` inside JSON decoded to a tab, giving `V <tab>imes I` and stray `$` signs | Prompt forbids LaTeX; `clean_text` repairs the tab and strips `$`. Confirmed fixed in the third run |
| A word-overlap "groundedness" score flagged correct Hinglish translations as ungrounded | The score is only used for English. Grounding of Hinglish cards is judged by the Verifier |

## Honest limits

- **Small test.** 12 verifier cases and 4 note sets, all on computer science and physics notes. The cases were
  written by us after we had seen how the generator behaves, so they are probably easier than real student notes.
  Zero errors here does not mean zero errors in general.
- **The Verifier removed nothing in the full-pipeline run.** On these four note sets the Generator's cards were already
  faithful, so the Verifier had nothing to catch. Its ability to catch wrong cards is shown only by the seeded test above
  (0 false accepts in 3 runs), not by real-world removals. The "removed cards" panel therefore stays empty on this data.
- **Latency is real.** Two sequential model calls make a request take roughly 30 to 45 seconds through a tunnel, so the UI
  needs a clear progress state.
- **Quality issues that remain.** A few cards are weak but supported, for example "What characteristic defines TCP? →
  TCP is reliable", and one Hinglish question asks "kyun" (why) without the answer explaining why. The Verifier
  checks truth against the notes, not how good a question is.
- **The English word-overlap score** still flags two correct cards because the notes say "3-way" and the card says
  "three-way", or "7" versus "seven". It is a rough signal. Reading the cards is part of the evaluation.
- **Dense notes** produce fewer cards than the maximum, so some facts get no card.
