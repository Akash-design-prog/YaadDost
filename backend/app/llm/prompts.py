"""Prompts and the JSON schema Gemma must answer in."""

CARDS_SCHEMA = {
    "type": "object",
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"q": {"type": "string"}, "a": {"type": "string"}},
                "required": ["q", "a"],
            },
        }
    },
    "required": ["cards"],
}

STYLE = {
    "english": "Write in clear, simple English.",
    "hinglish": (
        "Write in Hinglish: Hindi in Roman script mixed with English technical terms, "
        "the way college students actually talk. Keep technical terms in English."
    ),
}


def cards_messages(notes: str, count: int, language: str) -> list[dict]:
    system = (
        "You turn a student's study notes into revision flashcards. "
        "Use ONLY facts present in the notes; never add outside facts. "
        "Each card is one question (q) and one short answer (a). Prefer questions that test "
        f"understanding over copying sentences. {STYLE[language]} "
        'Reply as JSON: {"cards": [{"q": "...", "a": "..."}]}.'
    )
    user = f"Make up to {count} flashcards from these notes:\n\n{notes}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def explain_messages(concept: str, notes: str, language: str) -> list[dict]:
    system = (
        "You are a patient study friend. Explain the concept in 4-6 short sentences using an everyday "
        "analogy, then give one quick self-check question. Stay faithful to the student's notes if they "
        f"cover it. {STYLE[language]}"
    )
    user = f"Concept: {concept}\n\nStudent's notes (may be empty):\n{notes}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
