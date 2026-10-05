"""Property-based tests: instead of a few hand-picked examples, Hypothesis tries hundreds of generated inputs."""
import math

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings, strategies as st

from app.llm.generate import clean_text
from app.main import app
from app.services import fallback, srs

GRADES = list(srs.GRADES)


@st.composite
def valid_states(draw):
    """A card state that could really occur: the interval follows from how many times it was passed."""
    reps = draw(st.integers(0, 40))
    interval = {0: 0, 1: 1, 2: 6}[reps] if reps <= 2 else draw(st.integers(6, 36500))
    return draw(st.floats(srs.MIN_EASE, 4.0)), interval, reps


# --- scheduler -------------------------------------------------------------------------

@given(valid_states(), st.sampled_from(GRADES))
def test_srs_state_always_stays_valid(state, grade):
    ease, interval, reps = state
    n = srs.review(ease, interval, reps, grade)
    assert n["ease"] >= srs.MIN_EASE and n["interval"] >= 1 and n["reps"] >= 0
    assert math.isfinite(n["ease"])


@given(valid_states())
def test_srs_failing_always_resets_and_brings_the_card_back_tomorrow(state):
    n = srs.review(*state, "again")
    assert n["reps"] == 0 and n["interval"] == 1


@given(valid_states(), st.sampled_from(["hard", "good", "easy"]))
def test_srs_passing_never_shortens_the_interval(state, grade):
    ease, interval, reps = state
    assert srs.review(ease, interval, reps, grade)["interval"] >= min(interval, srs.MAX_INTERVAL)


@given(valid_states())
def test_srs_better_grades_never_lower_the_ease(state):
    eases = [srs.review(*state, g)["ease"] for g in ("again", "hard", "good", "easy")]
    assert eases == sorted(eases)


@given(valid_states(), st.sampled_from(["hard", "good", "easy"]))
def test_srs_a_long_run_of_passes_keeps_growing_without_overflow(state, grade):
    ease, interval, reps = state
    for _ in range(30):
        n = srs.review(ease, interval, reps, grade)
        ease, interval, reps = n["ease"], n["interval"], n["reps"]
    assert interval <= srs.MAX_INTERVAL and math.isfinite(ease)


# --- text cleaning ---------------------------------------------------------------------

@given(st.text())
def test_clean_text_is_idempotent_and_leaves_no_control_characters_or_dollars(s):
    out = clean_text(s)
    assert clean_text(out) == out
    assert "$" not in out and "\t" not in out and "\x08" not in out
    assert out == out.strip() and "  " not in out


# --- offline card maker ----------------------------------------------------------------

@given(st.text(max_size=3000), st.integers(1, 25))
def test_fallback_never_crashes_and_respects_count(notes, count):
    cards = fallback.make_cards(notes, count)
    assert len(cards) <= count
    assert all(c["q"].strip() and c["a"].strip() for c in cards)
    assert len({c["q"] for c in cards}) == len(cards)


# --- API: garbage in must never become a 500 -------------------------------------------

client = TestClient(app)


@settings(max_examples=60, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    ease=st.one_of(st.floats(allow_nan=False, allow_infinity=False), st.integers(), st.text(), st.none()),
    interval=st.one_of(st.integers(-10**15, 10**15), st.text(), st.none()),
    reps=st.one_of(st.integers(-10**15, 10**15), st.floats(allow_nan=False, allow_infinity=False), st.none()),
    grade=st.one_of(st.sampled_from(GRADES), st.text(max_size=10), st.none()),
)
def test_review_endpoint_only_ever_answers_200_or_422(ease, interval, reps, grade):
    r = client.post("/api/review", json={"ease": ease, "interval": interval, "reps": reps, "grade": grade})
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        assert r.json()["interval"] >= 1


@settings(max_examples=40, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(notes=st.text(max_size=9000), count=st.integers(-5, 40), language=st.text(max_size=12))
def test_cards_endpoint_only_ever_answers_200_or_422(notes, count, language):
    r = client.post("/api/cards", json={"notes": notes, "count": count, "language": language})
    assert r.status_code in (200, 422)
