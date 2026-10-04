from scoring import GROUNDED_MIN, groundedness, hinglish_share, score_cards

NOTES = "Deadlock needs mutual exclusion, hold and wait, no preemption and circular wait. TCP uses port 80."


def test_grounded_answer_scores_high():
    assert groundedness("mutual exclusion and circular wait", NOTES) == 1.0


def test_invented_answer_scores_low():
    assert groundedness("uses semaphores to schedule quantum threads", NOTES) < GROUNDED_MIN


def test_numbers_count_as_content():
    assert groundedness("443", NOTES) == 0.0
    assert groundedness("80", NOTES) == 1.0


def test_no_content_words_is_not_penalised():
    assert groundedness("it is", NOTES) == 1.0


def test_hinglish_share():
    assert hinglish_share("tcp reliable hota hai aur udp nahi") > 0.4
    assert hinglish_share("TCP is reliable and UDP is not") == 0.0
    assert hinglish_share("") == 0.0


CARDS = [
    {"q": "What is deadlock?", "a": "mutual exclusion and circular wait"},
    {"q": "what is Deadlock", "a": "uses semaphores to schedule quantum threads"},
]


def test_score_cards_flags_problems_in_english():
    s = score_cards(CARDS, NOTES, "english")
    assert s["cards"] == 2 and s["duplicates"] == 1 and s["ungrounded"] == 1
    assert s["hinglish_cards"] is None


def test_hinglish_skips_word_overlap_but_still_counts_duplicates():
    # translated answers can't be checked by word overlap, so the field is None, not a false alarm
    s = score_cards(CARDS, NOTES, "hinglish")
    assert s["ungrounded"] is None and s["mean_groundedness"] is None
    assert s["duplicates"] == 1 and s["hinglish_cards"] == 0


def test_score_cards_empty():
    assert score_cards([], NOTES, "english")["cards"] == 0
