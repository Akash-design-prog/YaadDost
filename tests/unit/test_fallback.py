from app.services import fallback

NOTES = (
    "Deadlock: a situation where processes wait forever for resources held by each other.\n"
    "Paging divides memory into fixed-size blocks, which removes external fragmentation.\n"
)


def test_makes_definition_and_cloze_cards():
    cards = fallback.make_cards(NOTES, 5)
    assert cards[0] == {"q": "What is Deadlock?", "a": "a situation where processes wait forever for resources held by each other."}
    assert "_____" in cards[1]["q"]


def test_respects_count():
    assert len(fallback.make_cards(NOTES, 1)) == 1
