"""Deterministic analytics engine for BPSC Question Lab v1.0.

All numbers, accuracy percentages, priority weights, sample size ratings,
and revision retention metrics are computed strictly in Python and SQL.
Gemini never invents or calculates authoritative statistics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import pandas as pd


def compute_overall_metrics(attempts: pd.DataFrame, sessions: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """Compute top-level deterministic metrics across all attempts."""
    if attempts.empty:
        return {
            "total_attempts": 0,
            "total_correct": 0,
            "total_incorrect": 0,
            "total_unanswered": 0,
            "accuracy": 0,
            "total_tests": len(sessions) if sessions is not None else 0,
            "average_time_per_question": 0.0,
            "net_score": 0.0,
        }

    total_attempts = len(attempts)
    correct = int((attempts["is_correct"] == 1).sum())
    incorrect = int(((attempts["is_correct"] == 0) & (attempts["selected_option"] != "-")).sum())
    unanswered = int((attempts["selected_option"] == "-").sum())
    accuracy = round((correct / total_attempts) * 100) if total_attempts > 0 else 0

    avg_time = 0.0
    if "time_spent_seconds" in attempts.columns:
        times = attempts["time_spent_seconds"][attempts["time_spent_seconds"] > 0]
        if not times.empty:
            avg_time = round(float(times.mean()), 1)

    net_score = 0.0
    if "score" in attempts.columns:
        net_score = round(float(attempts["score"].sum()), 2)

    total_tests = len(sessions) if sessions is not None else 0

    return {
        "total_attempts": total_attempts,
        "total_correct": correct,
        "total_incorrect": incorrect,
        "total_unanswered": unanswered,
        "accuracy": accuracy,
        "total_tests": total_tests,
        "average_time_per_question": avg_time,
        "net_score": net_score,
    }


def compute_topic_analytics(attempts: pd.DataFrame) -> pd.DataFrame:
    """Calculate detailed performance and sample-size reliability by subject & topic."""
    if attempts.empty:
        return pd.DataFrame(columns=[
            "subject", "topic", "attempts", "correct", "wrong", "unanswered",
            "accuracy", "sample_size_label", "priority",
        ])

    records = []
    grouped = attempts.groupby(["subject", "topic"])
    for (subj, topic), group in grouped:
        total = len(group)
        corr = int((group["is_correct"] == 1).sum())
        wrong = int(((group["is_correct"] == 0) & (group["selected_option"] != "-")).sum())
        unans = int((group["selected_option"] == "-").sum())
        acc = round((corr / total) * 100) if total > 0 else 0

        # Sample size reliability indicators
        if total < 5:
            sample_label = "Preliminary (n<5)"
            confidence_factor = 0.5
        elif total <= 15:
            sample_label = "Moderate (5-15)"
            confidence_factor = 0.85
        else:
            sample_label = "High Confidence (15+)"
            confidence_factor = 1.0

        # Priority calculation: lower accuracy + higher volume of errors = higher revision urgency
        priority = round(
            ((100 - acc) * 0.55 + min(wrong, 8) * 4) * confidence_factor, 1
        )

        records.append({
            "subject": subj,
            "topic": topic,
            "attempts": total,
            "correct": corr,
            "wrong": wrong,
            "unanswered": unans,
            "accuracy": acc,
            "sample_size_label": sample_label,
            "priority": priority,
        })

    df = pd.DataFrame(records)
    return df.sort_values(["priority", "wrong"], ascending=False).reset_index(drop=True)


def identify_weak_areas(topic_df: pd.DataFrame, max_items: int = 5) -> pd.DataFrame:
    """Identify weak syllabus topics needing targeted practice."""
    if topic_df.empty:
        return topic_df
    # Weak area criteria: accuracy < 70% with at least 2 attempts
    weak = topic_df[(topic_df["attempts"] >= 2) & (topic_df["accuracy"] < 70)]
    return weak.head(max_items).reset_index(drop=True)


def compute_error_distribution(attempts: pd.DataFrame) -> Dict[str, int]:
    """Return count of mistakes by classified root cause."""
    if attempts.empty:
        return {}
    incorrect = attempts[attempts["is_correct"] == 0]
    if incorrect.empty:
        return {}
    return incorrect["error_type"].value_counts().to_dict()


def compute_recurring_mistakes(attempts: pd.DataFrame) -> pd.DataFrame:
    """Find specific questions that the user has missed multiple times."""
    if attempts.empty:
        return pd.DataFrame()
    wrong = attempts[attempts["is_correct"] == 0]
    if wrong.empty:
        return pd.DataFrame()

    counts = wrong.groupby("question_id").size().reset_index(name="wrong_count")
    recurring = counts[counts["wrong_count"] >= 2]
    if recurring.empty:
        return pd.DataFrame()

    latest = wrong.drop_duplicates(subset=["question_id"], keep="first")
    merged = pd.merge(recurring, latest, on="question_id")
    return merged.sort_values("wrong_count", ascending=False).reset_index(drop=True)


def measure_revision_outcome(attempts: pd.DataFrame) -> Dict[str, Any]:
    """Measure whether revision and repeated attempts improve retention on topics."""
    if attempts.empty:
        return {"retried_topics_count": 0, "improved_count": 0, "average_gain": 0.0}

    # Group attempts by topic and sort chronologically
    sorted_att = attempts.sort_values("attempted_at", ascending=True)
    gains: List[float] = []
    improved = 0
    retried_topics = 0

    for (subj, topic), group in sorted_att.groupby(["subject", "topic"]):
        if len(group) >= 4:
            retried_topics += 1
            mid = len(group) // 2
            first_half = group.iloc[:mid]
            second_half = group.iloc[mid:]

            acc1 = (first_half["is_correct"].sum() / len(first_half)) * 100
            acc2 = (second_half["is_correct"].sum() / len(second_half)) * 100
            gain = round(acc2 - acc1, 1)
            gains.append(gain)
            if gain > 0:
                improved += 1

    avg_gain = round(sum(gains) / len(gains), 1) if gains else 0.0
    return {
        "retried_topics_count": retried_topics,
        "improved_count": improved,
        "average_gain": avg_gain,
    }
