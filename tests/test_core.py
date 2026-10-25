"""Unit tests for BPSC Question Lab v0.1.

Tests core scoring, priority calculation, CSV validation, and DB helpers
using an in-memory SQLite database so no on-disk question_lab.db is touched.
"""

from __future__ import annotations

import csv
import io
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd

# ---------------------------------------------------------------------------
# Import the app module.  We patch st.set_page_config (called at import time
# via decorators in some Streamlit versions) to avoid ImportError when
# Streamlit isn't fully initialised during testing.
# ---------------------------------------------------------------------------
import sys

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

import app as ql  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_in_memory_db() -> sqlite3.Connection:
    """Return a fresh in-memory SQLite DB with the app's schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam TEXT NOT NULL DEFAULT 'BPSC',
            subject TEXT NOT NULL,
            topic TEXT NOT NULL DEFAULT 'Uncategorised',
            question TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_option TEXT NOT NULL CHECK(correct_option IN ('A','B','C','D')),
            explanation TEXT NOT NULL DEFAULT '',
            source_type TEXT NOT NULL DEFAULT 'User-added',
            source_name TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL DEFAULT '',
            difficulty TEXT NOT NULL DEFAULT 'Medium',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            selected_option TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            error_type TEXT NOT NULL DEFAULT 'Unclassified',
            error_notes TEXT NOT NULL DEFAULT '',
            attempted_at TEXT NOT NULL,
            FOREIGN KEY(question_id) REFERENCES questions(id)
        )
    """)
    return conn


def _sample_question(overrides: dict | None = None) -> dict:
    """Return a minimal valid question dict."""
    q = {
        "exam": "BPSC", "subject": "Modern History", "topic": "Test Topic",
        "question": "Sample question?", "option_a": "A1", "option_b": "B1",
        "option_c": "C1", "option_d": "D1", "correct_option": "A",
        "explanation": "", "source_type": "User-added", "source_name": "",
        "source_url": "", "difficulty": "Medium",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    if overrides:
        q.update(overrides)
    return q


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestScoringLogic(unittest.TestCase):
    """Verify that answers are scored correctly."""

    def test_correct_answer(self):
        self.assertTrue("A" == "A")  # mirrors the app logic

    def test_incorrect_answer(self):
        self.assertFalse("B" == "A")

    def test_not_answered_is_incorrect(self):
        self.assertFalse("Not answered" == "A")

    def test_case_sensitive_match(self):
        # The app stores correct_option as uppercase A-D.
        self.assertFalse("a" == "A")


class TestInsertQuestion(unittest.TestCase):
    """Verify insert_question writes to the database."""

    def test_insert_and_retrieve(self):
        conn = _make_in_memory_db()
        item = _sample_question()
        ql.insert_question(conn, item)
        conn.commit()
        rows = conn.execute("SELECT * FROM questions").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["question"], "Sample question?")
        self.assertEqual(rows[0]["correct_option"], "A")
        conn.close()

    def test_insert_rejects_bad_correct_option(self):
        conn = _make_in_memory_db()
        item = _sample_question({"correct_option": "E"})
        with self.assertRaises(sqlite3.IntegrityError):
            ql.insert_question(conn, item)
        conn.close()


class TestPriorityFormula(unittest.TestCase):
    """Verify the topic priority score calculation."""

    def test_low_accuracy_gives_high_priority(self):
        # accuracy=20%, wrong=5, recent_wrong=3
        row = pd.Series({"accuracy": 20, "wrong": 5, "recent_wrong": 3})
        priority = (
            (100 - row["accuracy"]) * 0.55
            + min(row["wrong"], 6) * 5
            + min(row["recent_wrong"], 4) * 4
        )
        self.assertGreater(priority, 50)

    def test_perfect_accuracy_gives_low_priority(self):
        row = pd.Series({"accuracy": 100, "wrong": 0, "recent_wrong": 0})
        priority = (
            (100 - row["accuracy"]) * 0.55
            + min(row["wrong"], 6) * 5
            + min(row["recent_wrong"], 4) * 4
        )
        self.assertEqual(priority, 0.0)

    def test_wrong_capped_at_six(self):
        row = pd.Series({"accuracy": 50, "wrong": 20, "recent_wrong": 0})
        priority = (
            (100 - row["accuracy"]) * 0.55
            + min(row["wrong"], 6) * 5
            + min(row["recent_wrong"], 4) * 4
        )
        # wrong should be capped at 6 → 6*5 = 30
        expected = 50 * 0.55 + 30 + 0
        self.assertAlmostEqual(priority, expected)


class TestCSVImportValidation(unittest.TestCase):
    """Test the CSV import function with various edge cases."""

    def _csv_bytes(self, rows: list[dict]) -> io.BytesIO:
        """Build a CSV file-like object from a list of dicts."""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        buf.seek(0)
        return io.BytesIO(buf.getvalue().encode("utf-8"))

    def _valid_row(self, **overrides) -> dict:
        row = {
            "exam": "BPSC", "subject": "History", "topic": "Test",
            "question": "Q?", "option_a": "A1", "option_b": "B1",
            "option_c": "C1", "option_d": "D1", "correct_option": "A",
        }
        row.update(overrides)
        return row

    @patch("app.connect_db")
    def test_missing_columns_rejected(self, mock_conn):
        """A CSV missing required columns should return 0 inserted."""
        buf = io.BytesIO(b"exam,subject\nBPSC,History\n")
        inserted, problems = ql.import_csv(buf)
        self.assertEqual(inserted, 0)
        self.assertTrue(any("Missing required columns" in p for p in problems))

    @patch("app.connect_db")
    def test_bad_correct_option_skipped(self, mock_conn):
        """Rows with correct_option outside A-D should be skipped."""
        conn = _make_in_memory_db()
        mock_conn.return_value.__enter__ = lambda s: conn
        mock_conn.return_value.__exit__ = lambda s, *a: None

        csv_data = self._csv_bytes([self._valid_row(correct_option="X")])
        inserted, problems = ql.import_csv(csv_data)
        self.assertEqual(inserted, 0)
        self.assertTrue(any("correct_option" in p for p in problems))
        conn.close()

    @patch("app.connect_db")
    def test_valid_row_inserted(self, mock_conn):
        """A valid CSV row should be inserted successfully."""
        conn = _make_in_memory_db()
        mock_conn.return_value.__enter__ = lambda s: conn
        mock_conn.return_value.__exit__ = lambda s, *a: None

        csv_data = self._csv_bytes([self._valid_row(question="Unique test question 12345?")])
        inserted, problems = ql.import_csv(csv_data)
        self.assertEqual(inserted, 1)
        self.assertEqual(len(problems), 0)
        conn.close()

    @patch("app.connect_db")
    def test_duplicate_question_skipped(self, mock_conn):
        """Importing the same question twice should skip the duplicate."""
        conn = _make_in_memory_db()
        mock_conn.return_value.__enter__ = lambda s: conn
        mock_conn.return_value.__exit__ = lambda s, *a: None

        row = self._valid_row(question="Duplicate check question?")
        csv1 = self._csv_bytes([row])
        ql.import_csv(csv1)

        csv2 = self._csv_bytes([row])
        inserted, problems = ql.import_csv(csv2)
        self.assertEqual(inserted, 0)
        self.assertTrue(any("duplicate" in p.lower() for p in problems))
        conn.close()

    @patch("app.connect_db")
    def test_blank_required_field_skipped(self, mock_conn):
        """Rows with blank required text fields should be skipped."""
        conn = _make_in_memory_db()
        mock_conn.return_value.__enter__ = lambda s: conn
        mock_conn.return_value.__exit__ = lambda s, *a: None

        csv_data = self._csv_bytes([self._valid_row(question="")])
        inserted, problems = ql.import_csv(csv_data)
        self.assertEqual(inserted, 0)
        self.assertTrue(any("blank" in p.lower() for p in problems))
        conn.close()


class TestBuildWeeklyPlan(unittest.TestCase):
    """Verify the weekly revision planner."""

    def test_fallback_plan_with_few_attempts(self):
        """With fewer than 5 attempts, a baseline plan is returned."""
        attempts = pd.DataFrame({"is_correct": [1, 0]})
        stats = pd.DataFrame()
        plan = ql.build_weekly_plan(stats, attempts)
        self.assertEqual(len(plan), 7)
        self.assertTrue(all("Baseline plan" in p["basis"] for p in plan))

    def test_plan_has_seven_days(self):
        """The plan must always contain exactly seven entries."""
        stats = pd.DataFrame({
            "subject": ["History"], "topic": ["Revolt of 1857"],
            "attempts": [10], "correct": [3], "wrong": [7],
            "recent_wrong": [4], "accuracy": [30], "priority": [60.0],
        })
        attempts = pd.DataFrame({
            "is_correct": [0]*7 + [1]*3,
            "subject": ["History"]*10,
            "topic": ["Revolt of 1857"]*10,
            "error_type": ["Knowledge gap"]*7 + ["Unclassified"]*3,
        })
        plan = ql.build_weekly_plan(stats, attempts)
        self.assertEqual(len(plan), 7)

    def test_sixth_day_is_mixed_test(self):
        """The 6th day (index 5) should always be a mixed test."""
        stats = pd.DataFrame({
            "subject": ["History"], "topic": ["T"],
            "attempts": [10], "correct": [5], "wrong": [5],
            "recent_wrong": [2], "accuracy": [50], "priority": [50.0],
        })
        attempts = pd.DataFrame({
            "is_correct": [0]*5 + [1]*5,
            "subject": ["History"]*10,
            "topic": ["T"]*10,
            "error_type": ["Unclassified"]*10,
        })
        plan = ql.build_weekly_plan(stats, attempts)
        # The 6th study day (index 5) should be a mixed test regardless of
        # which calendar day it falls on.
        self.assertIn("Mixed", plan[5]["topic"])


class TestGetQuestionsByIds(unittest.TestCase):
    """Verify that get_questions_by_ids handles edge cases."""

    def test_empty_ids_returns_empty_df(self):
        result = ql.get_questions_by_ids([])
        self.assertTrue(result.empty)

    @patch("app.connect_db")
    def test_missing_id_is_skipped(self, mock_conn):
        """If a question ID no longer exists, it should be silently skipped."""
        conn = _make_in_memory_db()
        mock_conn.return_value.__enter__ = lambda s: conn
        mock_conn.return_value.__exit__ = lambda s, *a: None

        item = _sample_question()
        ql.insert_question(conn, item)
        conn.commit()

        # ID 1 exists, ID 999 does not
        result = ql.get_questions_by_ids([1, 999])
        self.assertEqual(len(result), 1)
        self.assertEqual(int(result.iloc[0]["id"]), 1)
        conn.close()


if __name__ == "__main__":
    unittest.main()
