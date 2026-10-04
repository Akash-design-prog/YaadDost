# YaadDost

Flashcards from your own notes, in Hinglish or English, that come back just before you'd forget them.
Built for the Hacktoberfest Weekend Challenge: *Build for a Friend*.

Paste your notes. An open-weight **Gemma** model writes the flashcards, a second Gemma pass **checks every card
against your notes and throws out anything they don't support**, and an SM-2 scheduler tells you when to
revise each card. Your notes only ever reach a Gemma server that you run yourself.

**Live demo:** _add the Render URL here_

## How it works

```
 your notes ──► Generator (Gemma) ──► Verifier (Gemma) ──► cards you keep
                  writes cards         checks each answer     + a list of what was
                  (Hinglish/English)   against the notes      removed, and why
                                                                   │
                                  SM-2 scheduler  ◄──── you review (Again / Hard / Good / Easy)
```

- **Generator:** asks Gemma for flashcards as schema-constrained JSON. Rules in the prompt: facts from the notes
  only, one card per fact, no padding, plain text.
- **Verifier:** a second Gemma call acts as a strict fact-checker. Translations and paraphrases pass; claims that
  are not in the notes fail, even if they are true in the real world. If the check can't run, the cards are
  shown as unchecked instead of being lost.
- **Scheduler:** plain SM-2, in `backend/app/services/srs.py`. No model involved, so it is deterministic and tested.
- **Offline mode:** if Gemma isn't reachable, simple rules build basic cards so the app still works.
- **Privacy:** cards are stored in your browser (localStorage). Notes go only to the Gemma server you point
  `OLLAMA_URL` at.

## Why open models

The notes are a student's private material, and the app is meant to be free to use daily. A local open-weight
model means no per-request cost, no account, and no notes leaving the machine you control. It also let us write the
Verifier ourselves and measure it (see `evals/`), which a closed API would not.

## Run it

You need Python 3.12+ and a Gemma server (Ollama).

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows. On macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements-dev.txt
uvicorn app.main:app --app-dir backend --reload
```

Open http://127.0.0.1:8000. Without a Gemma server the app runs in offline mode.

### Gemma on Colab (no local disk space needed)

1. Open `colab/gemma_server.ipynb` in Google Colab, set the runtime to **T4 GPU**, and run all cells.
2. Copy the `OLLAMA_URL` it prints, then start the app with it:

```bash
set OLLAMA_URL=https://<your-tunnel>.trycloudflare.com     # PowerShell: $env:OLLAMA_URL="..."
uvicorn app.main:app --app-dir backend
```

The default model is `gemma4:e4b`. Set `GEMMA_MODEL` to change it (for example `gemma4:e2b` for a smaller one).
The tunnel URL is public to anyone who has it and ends with the Colab session, so don't share it.

### Deploy on Render

New Web Service from this repo: build `pip install -r backend/requirements.txt`, start
`uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT`, health check `/healthz`.
Set `OLLAMA_URL` (and optionally `GEMMA_MODEL`) in the environment. `deploy/render.yaml` has the same settings.

## Tests and evaluation

```bash
pytest                      # unit tests, no model needed
```

The tests use a fake model server, so they check our code, not Gemma's quality. Quality is measured separately,
against a real Gemma, with `colab/eval_on_colab.ipynb`:

- `evals/run_eval.py` generates cards for four sets of sample notes (OS, databases, physics, messy Hinglish
  networking notes) in both languages, and prints every card to read.
- `evals/run_verifier_eval.py` plants known-wrong cards (wrong number, contradiction, true-but-not-in-notes,
  invented, reversed) among good ones and counts how many the Verifier lets through.

Automatic scores catch only gross problems. Reading the cards is part of the evaluation. For example, a
word-overlap "groundedness" score looked fine in English but flagged correct Hinglish translations, so it is
only used for English.

## Project layout

```
backend/app/
  api/        HTTP routes only
  agents/     verifier.py, pipeline.py (Generator -> Verifier)
  llm/        Ollama client, prompts, card generation
  services/   srs.py (SM-2), fallback.py (offline cards)
  core/       settings
frontend/     plain HTML, CSS and JS modules, no build step
tests/unit/   unit tests
evals/        real-Gemma evaluation scripts and sample notes
colab/        notebooks: Gemma server, and the evaluation
deploy/       Render blueprint
```

## Limits

- The Verifier is itself a model, so it can be wrong. It shows what it removed and why so you can check it.
- Cards are limited to the notes you paste: no PDF or image input yet.
- Dense notes can yield fewer cards than the maximum you ask for, because the generator is told not to pad.
- On Render's free plan the app sleeps when idle, and Gemma needs your Colab session to be running.
