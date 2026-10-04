"""Scores for generated flashcards. Pure functions, so they are unit-tested without a model."""
import re

# Common Roman-script Hindi words. Used only to check that "hinglish" output really is Hinglish.
HINDI_WORDS = {
    "hai", "hain", "ka", "ki", "ke", "ko", "se", "mein", "me", "nahi", "aur", "yeh", "ye", "woh", "kya",
    "kyun", "hota", "hoti", "hote", "jab", "tab", "jo", "par", "bhi", "toh", "ek", "karta", "karti",
    "karte", "kaise", "kyunki", "liye", "wala", "wali",
}
GROUNDED_MIN = 0.5


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def groundedness(answer: str, notes: str) -> float:
    """Share of the answer's content words (4+ letters or numbers) that appear in the notes.

    A rough check that the answer is built from the notes and not from the model's memory.
    Returns 1.0 for an answer with no content words (nothing to contradict).
    """
    note_words = set(words(notes))
    content = [w for w in words(answer) if len(w) >= 4 or w.isdigit()]
    if not content:
        return 1.0
    return sum(w in note_words for w in content) / len(content)


def hinglish_share(text: str) -> float:
    """Share of words that are common Hindi words. Plain English text scores near 0."""
    ws = words(text)
    return sum(w in HINDI_WORDS for w in ws) / len(ws) if ws else 0.0


def score_cards(cards: list[dict], notes: str, language: str) -> dict:
    n = len(cards)
    if n == 0:
        return {"cards": 0, "ungrounded": 0, "duplicates": 0, "mean_groundedness": 0.0, "hinglish_cards": 0}
    questions = [re.sub(r"\W+", " ", c["q"].lower()).strip() for c in cards]
    # Word overlap only works when cards and notes share a language. A Hinglish card that
    # faithfully translates English notes scores low ("organize karna" vs "organising"), so for
    # Hinglish these two fields are None and the Verifier agent (A1) judges grounding instead.
    if language == "english":
        g = [groundedness(c["a"], notes) for c in cards]
        ungrounded, mean_g = sum(x < GROUNDED_MIN for x in g), round(sum(g) / n, 3)
    else:
        ungrounded, mean_g = None, None
    return {
        "cards": n,
        "ungrounded": ungrounded,
        "duplicates": n - len(set(questions)),
        "mean_groundedness": mean_g,
        # in hinglish mode, how many cards actually contain Hindi words
        "hinglish_cards": sum(hinglish_share(c["q"] + " " + c["a"]) > 0 for c in cards) if language == "hinglish" else None,
    }
