"""SM-2 spaced repetition. Pure functions: the browser keeps the state, the server does the math."""

MIN_EASE = 1.3
MAX_INTERVAL = 365   # days. Without a cap, repeated "easy" reviews grow the interval without bound.

# Button -> SM-2 quality (0-5)
GRADES = {"again": 1, "hard": 3, "good": 4, "easy": 5}


def review(ease: float, interval: int, reps: int, grade: str) -> dict:
    """Return the next scheduling state for a card after a review.

    interval is in days. A failed review (again) resets reps and brings the card back tomorrow.
    """
    if grade not in GRADES:
        raise ValueError(f"unknown grade: {grade}")
    q = GRADES[grade]

    if q < 3:
        reps = 0
        interval = 1
    else:
        reps += 1
        if reps == 1:
            interval = 1
        elif reps == 2:
            interval = 6
        else:
            interval = min(MAX_INTERVAL, max(1, round(interval * ease)))

    ease = max(MIN_EASE, ease + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    return {"ease": round(ease, 3), "interval": interval, "reps": reps}
