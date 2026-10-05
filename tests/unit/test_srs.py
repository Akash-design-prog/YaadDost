import pytest

from app.services import srs


def test_first_two_good_reviews():
    s = srs.review(2.5, 0, 0, "good")
    assert (s["interval"], s["reps"]) == (1, 1)
    s = srs.review(s["ease"], s["interval"], s["reps"], "good")
    assert (s["interval"], s["reps"]) == (6, 2)


def test_interval_grows_by_ease():
    s = srs.review(2.5, 6, 2, "good")
    assert s["interval"] == 15 and s["reps"] == 3


def test_again_resets_and_floors_ease():
    s = srs.review(1.35, 20, 5, "again")
    assert s["reps"] == 0 and s["interval"] == 1 and s["ease"] == srs.MIN_EASE


def test_interval_is_capped_at_a_year():
    s = srs.review(3.0, 300, 9, "easy")
    assert s["interval"] == srs.MAX_INTERVAL == 365
    # and a capped card stays reviewable: the API accepts the state it just produced
    assert srs.review(s["ease"], s["interval"], s["reps"], "good")["interval"] == 365


def test_rejects_unknown_grade():
    with pytest.raises(ValueError):
        srs.review(2.5, 0, 0, "meh")
