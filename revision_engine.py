"""Adaptive spaced-repetition and revision planner engine for BPSC Question Lab v1.0.

Provides:
- Deterministic spaced-repetition interval scheduling based on empirical performance.
- Dynamic daily and weekly plan generation with customizable exam target date.
- Time capacity budgeting (minutes per session).
- Tracking planned vs. completed revision tasks.
- Preserves backward compatibility with legacy build_weekly_plan calls.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
import pandas as pd


# Default Spaced-Repetition intervals (in days) upon successful review
DEFAULT_INTERVALS = [1, 3, 7, 16, 35, 75]


def calculate_next_interval(
    current_interval: int,
    repetitions: int,
    ease_factor: float,
    performance_score: float,  # 0.0 to 1.0 (e.g. accuracy on review)
) -> Tuple[int, int, float, str]:
    """Calculate the next review interval and ease factor using modified SM-2 principles.

    Returns:
        (next_interval_days, updated_repetitions, updated_ease_factor, status_label)
    """
    if performance_score < 0.6:  # Failed review
        new_interval = 1
        new_reps = 0
        new_ease = max(1.3, ease_factor - 0.2)
        label = "Reset interval (needs consolidation)"
    else:  # Successful review
        new_reps = repetitions + 1
        if new_reps == 1:
            new_interval = 1
        elif new_reps == 2:
            new_interval = 3
        elif new_reps == 3:
            new_interval = 7
        else:
            new_interval = int(round(current_interval * ease_factor))
        new_ease = min(3.0, ease_factor + 0.1)
        label = f"Interval extended to {new_interval} day(s)"

    return new_interval, new_reps, round(new_ease, 2), label


def generate_adaptive_weekly_plan(
    stats: pd.DataFrame,
    attempts: pd.DataFrame,
    target_exam_date: Optional[date] = None,
    daily_available_minutes: int = 120,
    preferred_subjects: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Build a comprehensive 7-day adaptive revision plan with deterministic rationale."""
    all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    today = date.today()
    today_weekday = today.weekday()  # 0=Monday, 6=Sunday
    days = all_days[today_weekday:] + all_days[:today_weekday]

    # Calculate days remaining until target exam, if set
    days_to_exam = (target_exam_date - today).days if target_exam_date else None
    urgency_suffix = f" ({days_to_exam} days to exam)" if days_to_exam is not None and days_to_exam > 0 else ""

    # Fallback plan when there are fewer than 5 recorded attempts
    if len(attempts) < 5 or stats.empty:
        fallback = [
            ("Modern History", "Champaran & 1857 in Bihar", "Revise core facts and events, then take 15 recall MCQs.", 45),
            ("General Science", "Physics & Biology Core", "Review high-yield scientific units and biological classifications.", 40),
            ("Bihar Special", "Geography & Rivers of Bihar", "Study Gandak, Kosi, and Son river basins on the map; attempt 15 MCQs.", 45),
            ("Indian Polity", "Fundamental Rights & DPSP", "Compare Articles 14-32 and write key writ jurisdictions.", 40),
            ("Economy", "Budget & Economic Survey Highlights", "Memorize key fiscal indicators and welfare allocations.", 35),
            ("Mixed Practice", "Full Weekly Cross-Subject Drill", "Take a timed 25-question mixed practice test and classify all errors.", 60),
            ("Review & Reset", "Error Notebook Consolidation", "Retry every missed question from the week; confirm zero repeated errors.", 45),
        ]
        return [
            {
                "day": day,
                "date": (today + timedelta(days=idx)).strftime("%b %d"),
                "subject": item[0],
                "topic": item[1],
                "task": item[2],
                "estimated_minutes": min(item[3], daily_available_minutes),
                "basis": f"Baseline plan: not enough attempt data yet{urgency_suffix}",
                "is_completed": False,
            }
            for idx, (day, item) in enumerate(zip(days, fallback))
        ]

    # Filter by preferred subjects if supplied
    ranked = stats.copy()
    if preferred_subjects and any(s in ranked["subject"].values for s in preferred_subjects):
        ranked = ranked[ranked["subject"].isin(preferred_subjects)]

    # Prioritize topics with low accuracy and repeated errors
    ranked["adjusted_priority"] = ranked["priority"] + (ranked["attempts"].clip(upper=5) / 5.0 * 4)
    ranked = ranked.sort_values("adjusted_priority", ascending=False)
    top_candidates = ranked.head(max(4, len(ranked))).to_dict("records")

    # Mistake categories lookup
    wrong_rows = attempts[attempts["is_correct"] == 0]
    mistake_counts = (
        wrong_rows.groupby(["subject", "topic", "error_type"]).size().reset_index(name="count")
        if not wrong_rows.empty
        else pd.DataFrame()
    )

    plan = []
    for i, day in enumerate(days):
        day_date = today + timedelta(days=i)
        date_str = day_date.strftime("%b %d")

        if i == 5:
            plan.append({
                "day": day,
                "date": date_str,
                "subject": "Mixed Practice",
                "topic": "Timed Cross-Syllabus Drill",
                "task": "Take a 30-question timed mixed mock. Deliberately check stems for NOT/INCORRECT and review elimination steps.",
                "estimated_minutes": min(60, daily_available_minutes),
                "basis": "Consolidation day: verifies whether weak-topic revisions transfer to fresh questions.",
                "is_completed": False,
            })
            continue

        if i == 6:
            plan.append({
                "day": day,
                "date": date_str,
                "subject": "Review & Reset",
                "topic": "Error Notebook Clearing",
                "task": "Retry all pinned difficult questions without consulting notes. Re-diagnose any recurring mistakes.",
                "estimated_minutes": min(45, daily_available_minutes),
                "basis": "Retention check: ensures errors are actively corrected before introducing new topics.",
                "is_completed": False,
            })
            continue

        entry = top_candidates[i % len(top_candidates)]
        subj = str(entry["subject"])
        top = str(entry["topic"])

        # Determine dominant error type for customized task recommendation
        dom_error = "Unclassified"
        if not mistake_counts.empty:
            matching = mistake_counts[(mistake_counts["subject"] == subj) & (mistake_counts["topic"] == top)]
            if not matching.empty:
                dom_error = matching.sort_values("count", ascending=False).iloc[0]["error_type"]

        if dom_error == "Knowledge gap":
            task = f"Read standard textbook notes on {top}. Create a 1-page recall sheet of dates/facts, then attempt 10 targeted MCQs."
        elif dom_error == "Conceptual confusion":
            task = f"Draft a side-by-side comparison table clarifying the exact distinctions in {top}. Retest with 10 questions."
        elif dom_error == "Misread question":
            task = f"Practice 10 questions on {top} untimed. Circle keywords (NOT, EXCLUDING, ONLY, ALL) before selecting."
        elif dom_error == "Incorrect elimination / guess":
            task = f"For 10 practice questions on {top}, write down the exact reason for rejecting options A, B, C or D."
        elif dom_error == "Careless error":
            task = f"Attempt 10 questions on {top} with a mandatory 5-second verification pause before submitting each answer."
        else:
            task = f"Review key principles of {top}, retry previously missed questions, and test with 10 fresh practice questions."

        # Rationale string
        acc = int(entry.get("accuracy", 0))
        att = int(entry.get("attempts", 0))
        wrong_cnt = int(entry.get("wrong", 0))
        if acc < 50:
            basis = f"High Urgency{urgency_suffix}: {acc}% accuracy across {att} attempt(s)."
        elif wrong_cnt >= 3:
            basis = f"Repeated Errors{urgency_suffix}: {wrong_cnt} incorrect answers; current accuracy {acc}%."
        else:
            basis = f"Weak Spot Priority score {entry.get('priority', 0)}{urgency_suffix}: accuracy {acc}% across {att} attempts."

        plan.append({
            "day": day,
            "date": date_str,
            "subject": subj,
            "topic": top,
            "task": task,
            "estimated_minutes": min(45, daily_available_minutes),
            "basis": basis,
            "is_completed": False,
        })

    return plan


def build_weekly_plan(stats: pd.DataFrame, attempts: pd.DataFrame) -> List[Dict[str, str]]:
    """Legacy backward-compatible adapter returning list of dicts with day, topic, task, basis."""
    full_plan = generate_adaptive_weekly_plan(stats, attempts)
    return [
        {
            "day": item["day"],
            "topic": f"{item['subject']}: {item['topic']}" if item["subject"] not in ["Mixed Practice", "Review & Reset"] else item["subject"],
            "task": item["task"],
            "basis": item["basis"],
        }
        for item in full_plan
    ]
