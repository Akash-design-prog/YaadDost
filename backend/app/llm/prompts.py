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
        "Rules:\n"
        "1. Use ONLY facts present in the notes; never add outside facts.\n"
        "2. Each card is one question (q) and one short answer (a).\n"
        "3. Each fact gets exactly ONE card. Never ask about the same fact twice in different words, "
        "even if that means making fewer cards than the maximum. Fewer good cards beat padded ones.\n"
        "4. Write the answer as a complete short sentence, not a fragment, unless it is just a name, "
        "number or formula.\n"
        "5. The question must stand alone. Do not add instructions in brackets such as "
        "(List the four conditions), and do not end it with commands like 'explain' or 'simple terms mein'.\n"
        f"{STYLE[language]} "
        'Reply as JSON: {"cards": [{"q": "...", "a": "..."}]}.'
    )
    user = f"Make at most {count} flashcards from these notes:\n\n{notes}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def explain_messages(concept: str, notes: str, language: str) -> list[dict]:
    system = (
        "You are a patient study friend. Explain the concept in 4-6 short sentences using an everyday "
        "analogy, then give one quick self-check question. Stay faithful to the student's notes if they "
        f"cover it. {STYLE[language]}"
    )
    user = f"Concept: {concept}\n\nStudent's notes (may be empty):\n{notes}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
