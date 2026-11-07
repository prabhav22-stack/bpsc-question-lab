"""Free Spaced Repetition Scheduler (FSRS) Memory Engine for Question Lab.

Implements the open-source FSRS DSR (Difficulty, Stability, Retrievability) algorithm
for scientifically optimal spaced repetition, predicting exact memory retention
and calculating personalized review schedules for BPSC and UPSC aspirants.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import fsrs
    _HAS_FSRS = True
except ImportError:
    _HAS_FSRS = False


# Default FSRS Scheduler instance calibrated to 90% target retention
def _get_scheduler(desired_retention: float = 0.90) -> Any:
    if not _HAS_FSRS:
        return None
    return fsrs.Scheduler(desired_retention=desired_retention)


def init_fsrs_card(card_id: Optional[int] = None) -> Any:
    """Initialize a new FSRS card."""
    if not _HAS_FSRS:
        return None
    now = datetime.now(timezone.utc)
    c = fsrs.Card(card_id=card_id or int(now.timestamp() * 1000))
    return c


def rating_from_attempt(is_correct: bool, confidence: str = "Medium") -> Any:
    """Map user's test answer correctness and confidence to an FSRS rating."""
    if not _HAS_FSRS:
        return None
    conf_lower = str(confidence).lower()
    if not is_correct:
        return fsrs.Rating.Again
    # Answer was correct:
    if "high" in conf_lower:
        return fsrs.Rating.Easy
    elif "guess" in conf_lower or "low" in conf_lower:
        return fsrs.Rating.Hard
    return fsrs.Rating.Good


def record_fsrs_review(
    card_json: str,
    is_correct: bool,
    confidence: str = "Medium",
    review_time: Optional[datetime] = None,
    desired_retention: float = 0.90,
) -> Tuple[str, float, datetime]:
    """Process a review through the FSRS algorithm and return updated card JSON, stability, and due date.

    Returns:
        (updated_card_json, stability, due_datetime)
    """
    if not _HAS_FSRS:
        # Fallback when fsrs is absent
        now = review_time or datetime.now(timezone.utc)
        due = now + timedelta(days=3 if is_correct else 1)
        return ("", 2.0 if is_correct else 0.5, due)

    now = review_time or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # Restore card from json or initialize
    c: Optional[fsrs.Card] = None
    if isinstance(card_json, fsrs.Card):
        c = card_json
    elif isinstance(card_json, str) and card_json.strip():
        try:
            c = fsrs.Card.from_json(card_json)
        except Exception:
            c = None

    if c is None:
        c = fsrs.Card()

    scheduler = _get_scheduler(desired_retention=desired_retention)
    rating = rating_from_attempt(is_correct=is_correct, confidence=confidence)

    updated_card, review_log = scheduler.review_card(c, rating, now)
    stability = float(updated_card.stability or 1.0)
    due_date = updated_card.due
    card_str = updated_card.to_json()

    return (card_str, stability, due_date)


def compute_retrievability(
    stability: Optional[float],
    last_review: Optional[Union[str, datetime]],
    now: Optional[datetime] = None,
) -> float:
    """Compute the current probability of memory recall (Retrievability R, 0.0 to 1.0).

    Uses the FSRS forgetting curve: R(t) = (1 + factor * (t / S))^-0.5
    Where t is days elapsed since last review, and S is memory stability.
    """
    if not stability or stability <= 0:
        return 0.50

    cur_now = now or datetime.now(timezone.utc)
    if cur_now.tzinfo is None:
        cur_now = cur_now.replace(tzinfo=timezone.utc)

    if last_review is None:
        return 0.90

    if isinstance(last_review, str):
        try:
            # Handle ISO strings with Z or timezone offset
            clean_str = last_review.replace("Z", "+00:00")
            lr_dt = datetime.fromisoformat(clean_str)
        except Exception:
            return 0.75
    else:
        lr_dt = last_review

    if lr_dt.tzinfo is None:
        lr_dt = lr_dt.replace(tzinfo=timezone.utc)

    delta_days = max(0.0, (cur_now - lr_dt).total_seconds() / 86400.0)
    if delta_days == 0:
        return 1.0

    # FSRS memory power law forgetting curve
    # R = (1 + factor * (t / S))^-w, standard FSRS factor ~ 19/81, w ~ 0.5
    factor = 19.0 / 81.0
    r = math.pow(1.0 + factor * (delta_days / stability), -0.5)
    return max(0.05, min(1.0, float(r)))


def get_retrievability_label(retrievability: float) -> Tuple[str, str]:
    """Return descriptive status and hex color for retrievability percentage."""
    pct = retrievability * 100.0
    if pct >= 88.0:
        return ("Fresh in Memory", "#10b981")  # Green
    elif pct >= 70.0:
        return ("Review Recommended", "#38bdf8")  # Cyan / Blue
    elif pct >= 50.0:
        return ("Memory Decaying", "#f59e0b")  # Amber / Warning
    else:
        return ("Critical / Near Forgotten", "#ef4444")  # Red / Urgent
