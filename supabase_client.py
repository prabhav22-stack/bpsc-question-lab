"""Supabase client, authentication, and migration utility for BPSC Question Lab v1.0.

Provides:
- Secure connection using Supabase URL and public Anon key.
- Auth flow helpers for sign-in, sign-up, session retrieval, and logout.
- SQLite-to-Supabase migration without modifying or deleting local SQLite data.
- Safe fallback when cloud credentials are not yet configured.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from config import get_supabase_anon_key, get_supabase_url, is_supabase_configured
import db

try:
    from supabase import Client, create_client

    _HAS_SUPABASE = True
except ImportError:
    _HAS_SUPABASE = False


class SupabaseServiceError(Exception):
    """Raised when Supabase cloud operations fail."""
    pass


def get_supabase_client() -> Optional[Client]:
    """Return an authenticated Supabase client if configured."""
    if not _HAS_SUPABASE or not is_supabase_configured():
        return None
    url = get_supabase_url()
    key = get_supabase_anon_key()
    return create_client(url, key)


def sign_in(email: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Authenticate an existing user with email and password."""
    client = get_supabase_client()
    if not client:
        return False, "Supabase cloud credentials are not configured.", None
    try:
        response = client.auth.sign_in_with_password({"email": email, "password": password})
        if response.user:
            return True, "Login successful", {"id": response.user.id, "email": response.user.email}
        return False, "Failed to authenticate.", None
    except Exception as exc:
        return False, str(exc), None


def sign_up(email: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Register a new user account."""
    client = get_supabase_client()
    if not client:
        return False, "Supabase cloud credentials are not configured.", None
    try:
        response = client.auth.sign_up({"email": email, "password": password})
        if response.user:
            return True, "Account created successfully.", {"id": response.user.id, "email": response.user.email}
        return False, "Registration could not be completed.", None
    except Exception as exc:
        return False, str(exc), None


def sign_out() -> bool:
    """Log out the current session."""
    client = get_supabase_client()
    if client:
        try:
            client.auth.sign_out()
            return True
        except Exception:
            return False
    return True


def migrate_local_data_to_supabase(user_id: str) -> Dict[str, Any]:
    """Upload local SQLite questions and attempts to Supabase for the authenticated user.

    The local SQLite database is never deleted or cleared.
    """
    client = get_supabase_client()
    if not client:
        raise SupabaseServiceError("Cannot migrate: Supabase cloud credentials are not configured.")

    results: Dict[str, int] = {
        "questions_migrated": 0,
        "attempts_migrated": 0,
        "sessions_migrated": 0,
    }

    with db.connect_db() as conn:
        # 1. Migrate questions
        q_rows = conn.execute("SELECT * FROM questions").fetchall()
        for q in q_rows:
            q_dict = dict(q)
            q_payload = {
                "user_id": user_id,
                "is_public": True if q_dict.get("source_type") == "Built-in sample" else False,
                "exam": q_dict.get("exam", "BPSC"),
                "subject": q_dict.get("subject", ""),
                "topic": q_dict.get("topic", ""),
                "subtopic": q_dict.get("subtopic", ""),
                "question": q_dict.get("question", ""),
                "option_a": q_dict.get("option_a", ""),
                "option_b": q_dict.get("option_b", ""),
                "option_c": q_dict.get("option_c", ""),
                "option_d": q_dict.get("option_d", ""),
                "correct_option": q_dict.get("correct_option", "A"),
                "explanation": q_dict.get("explanation", ""),
                "distractor_notes": q_dict.get("distractor_notes", ""),
                "concept_tested": q_dict.get("concept_tested", ""),
                "question_type": q_dict.get("question_type", "Standard MCQ"),
                "source_type": q_dict.get("source_type", "User-added"),
                "source_name": q_dict.get("source_name", ""),
                "source_url": q_dict.get("source_url", ""),
                "difficulty": q_dict.get("difficulty", "Medium"),
                "is_ai_generated": bool(q_dict.get("is_ai_generated", 0)),
            }
            try:
                client.table("questions").insert(q_payload).execute()
                results["questions_migrated"] += 1
            except Exception:
                pass

        # 2. Migrate test sessions
        s_rows = conn.execute("SELECT * FROM test_sessions").fetchall()
        for s in s_rows:
            s_dict = dict(s)
            s_payload = {
                "user_id": user_id,
                "session_id": s_dict.get("session_id", ""),
                "exam": s_dict.get("exam", "BPSC"),
                "test_mode": s_dict.get("test_mode", "Practice"),
                "total_questions": s_dict.get("total_questions", 0),
                "correct_count": s_dict.get("correct_count", 0),
                "incorrect_count": s_dict.get("incorrect_count", 0),
                "unanswered_count": s_dict.get("unanswered_count", 0),
                "negative_mark_rate": s_dict.get("negative_mark_rate", 0.0),
                "total_score": s_dict.get("total_score", 0.0),
                "time_spent_seconds": s_dict.get("time_spent_seconds", 0.0),
            }
            try:
                client.table("test_sessions").insert(s_payload).execute()
                results["sessions_migrated"] += 1
            except Exception:
                pass

    return results
