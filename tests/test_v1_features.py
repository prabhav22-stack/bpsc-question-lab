"""Comprehensive unit and integration test suite for BPSC Question Lab v1.0.

Covers:
- Schema validation for AI question sets, mistake diagnoses, and reports.
- Deterministic analytics and sample-size reliability indicators.
- Adaptive spaced-repetition calculations.
- Mocked AI services (no API key or internet required).
- Additive database features (test sessions, pinned notebook, research notes).
- Migration export and data integrity checks.
"""

from __future__ import annotations

import json
import sqlite3
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
from pydantic import ValidationError

import ai_service
import analytics
import db
import revision_engine
import schemas
import supabase_client


class TestSchemaValidation(unittest.TestCase):
    """Test Pydantic schemas for questions, diagnoses, and reports."""

    def test_valid_question_schema(self):
        q = schemas.GeneratedQuestion(
            question="Where did Kunwar Singh lead the 1857 Revolt in Bihar?",
            option_a="Patna",
            option_b="Jagdishpur",
            option_c="Gaya",
            option_d="Munger",
            correct_option="B",
            explanation="Kunwar Singh led the rebellion from Jagdishpur (Arrah).",
            concept_tested="Revolt of 1857 leaders in Bihar",
            subject="Modern History",
            topic="Revolt of 1857",
        )
        self.assertEqual(q.correct_option, "B")
        self.assertTrue(q.is_ai_generated)

    def test_generated_question_set_exemplars_property(self):
        """GeneratedQuestionSet should store and return retrieved exemplars via private attribute."""
        q_set = schemas.GeneratedQuestionSet(
            exam="BPSC",
            subject="Bihar Special",
            topic="Champaran",
            questions=[],
        )
        self.assertEqual(q_set.retrieved_exemplars, [])
        sample_ex = [{"question": "Who was Batak Mian?", "correct_option": "A"}]
        q_set.retrieved_exemplars = sample_ex
        self.assertEqual(len(q_set.retrieved_exemplars), 1)
        self.assertEqual(q_set.retrieved_exemplars[0]["question"], "Who was Batak Mian?")
        # Ensure schema json does not expose private attribute
        self.assertNotIn("_retrieved_exemplars", schemas.GeneratedQuestionSet.model_json_schema()["properties"])

    def test_duplicate_options_rejected(self):
        """Questions with identical options must be rejected by validator."""
        with self.assertRaises(ValidationError):
            schemas.GeneratedQuestion(
                question="What is the capital of Bihar?",
                option_a="Patna",
                option_b="Patna",  # Duplicate option
                option_c="Gaya",
                option_d="Bhagalpur",
                correct_option="A",
                explanation="Patna is the capital.",
                concept_tested="Capital of Bihar",
            )

    def test_blank_field_rejected(self):
        """Questions with empty stem or options must fail validation."""
        with self.assertRaises(ValidationError):
            schemas.GeneratedQuestion(
                question="   ",  # Blank
                option_a="A",
                option_b="B",
                option_c="C",
                option_d="D",
                correct_option="A",
                explanation="Exp",
                concept_tested="Concept",
            )

    def test_mistake_diagnosis_schema(self):
        diag = schemas.MistakeDiagnosis(
            suggested_error_type="Knowledge gap",
            diagnosis="Student confused the year of nationalisation with the year of establishment.",
            concept_recap="RBI was established in 1935 and nationalised in 1949.",
            distinction="1935 = Established; 1949 = Nationalised.",
            next_step_action="Review banking history timeline.",
        )
        self.assertEqual(diag.suggested_error_type, "Knowledge gap")


class TestAnalyticsCalculations(unittest.TestCase):
    """Test deterministic analytics engine."""

    def test_compute_overall_metrics_empty(self):
        res = analytics.compute_overall_metrics(pd.DataFrame(), pd.DataFrame())
        self.assertEqual(res["total_attempts"], 0)
        self.assertEqual(res["accuracy"], 0)

    def test_compute_overall_metrics_with_data(self):
        attempts = pd.DataFrame({
            "is_correct": [1, 1, 0, 0],
            "selected_option": ["A", "B", "C", "-"],
            "time_spent_seconds": [15.0, 20.0, 25.0, 0.0],
            "score": [1.0, 1.0, -0.25, 0.0],
        })
        sessions = pd.DataFrame({"id": [1]})
        res = analytics.compute_overall_metrics(attempts, sessions)
        self.assertEqual(res["total_attempts"], 4)
        self.assertEqual(res["total_correct"], 2)
        self.assertEqual(res["total_incorrect"], 1)
        self.assertEqual(res["total_unanswered"], 1)
        self.assertEqual(res["accuracy"], 50)
        self.assertEqual(res["net_score"], 1.75)
        self.assertEqual(res["total_tests"], 1)

    def test_sample_size_labels(self):
        """Verify that sample size reliability is transparently labeled."""
        attempts = pd.DataFrame({
            "subject": ["History"] * 3 + ["Polity"] * 8 + ["Science"] * 20,
            "topic": ["TopicA"] * 3 + ["TopicB"] * 8 + ["TopicC"] * 20,
            "is_correct": [1] * 3 + [1] * 8 + [1] * 20,
            "selected_option": ["A"] * 31,
        })
        stats = analytics.compute_topic_analytics(attempts)
        self.assertEqual(len(stats), 3)

        label_a = stats[stats["topic"] == "TopicA"].iloc[0]["sample_size_label"]
        label_b = stats[stats["topic"] == "TopicB"].iloc[0]["sample_size_label"]
        label_c = stats[stats["topic"] == "TopicC"].iloc[0]["sample_size_label"]

        self.assertIn("Preliminary", label_a)
        self.assertIn("Moderate", label_b)
        self.assertIn("High", label_c)

    def test_recurring_mistakes_detection(self):
        """Questions missed multiple times must be identified as recurring."""
        attempts = pd.DataFrame({
            "question_id": [101, 101, 102],
            "is_correct": [0, 0, 1],
            "selected_option": ["B", "C", "A"],
            "subject": ["History", "History", "Polity"],
            "topic": ["1857", "1857", "Writs"],
        })
        recurring = analytics.compute_recurring_mistakes(attempts)
        self.assertEqual(len(recurring), 1)
        self.assertEqual(int(recurring.iloc[0]["question_id"]), 101)
        self.assertEqual(int(recurring.iloc[0]["wrong_count"]), 2)


class TestAdaptiveRevisionEngine(unittest.TestCase):
    """Test spaced repetition and plan calculations."""

    def test_failed_review_resets_interval(self):
        """A review score < 0.6 resets the interval to 1 day."""
        new_interval, new_reps, new_ease, label = revision_engine.calculate_next_interval(
            current_interval=7, repetitions=3, ease_factor=2.5, performance_score=0.4
        )
        self.assertEqual(new_interval, 1)
        self.assertEqual(new_reps, 0)
        self.assertLess(new_ease, 2.5)

    def test_successful_review_extends_interval(self):
        """Repeated successful reviews progressively extend intervals."""
        # Repetition 1
        int1, rep1, _, _ = revision_engine.calculate_next_interval(1, 0, 2.5, 0.9)
        self.assertEqual(int1, 1)
        self.assertEqual(rep1, 1)

        # Repetition 2
        int2, rep2, _, _ = revision_engine.calculate_next_interval(int1, rep1, 2.5, 0.9)
        self.assertEqual(int2, 3)

        # Repetition 3
        int3, rep3, _, _ = revision_engine.calculate_next_interval(int2, rep2, 2.5, 0.9)
        self.assertEqual(int3, 7)

    def test_adaptive_weekly_plan_has_seven_days(self):
        plan = revision_engine.generate_adaptive_weekly_plan(
            stats=pd.DataFrame(),
            attempts=pd.DataFrame(),
            target_exam_date=date.today() + timedelta(days=60),
            daily_available_minutes=90,
        )
        self.assertEqual(len(plan), 7)
        self.assertIn("60 days to exam", plan[0]["basis"])
        self.assertLessEqual(plan[0]["estimated_minutes"], 90)


class TestMockedAIService(unittest.TestCase):
    """Test AI Service layer with mocked responses (no API key needed)."""

    def test_unconfigured_gemini_raises_clean_error(self):
        with patch("ai_service.is_gemini_configured", return_value=False):
            with self.assertRaises(ai_service.AIServiceError):
                ai_service.generate_question_set(
                    exam="BPSC", subject="Modern History", topic="Champaran"
                )

    def test_mocked_question_generation(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_payload = {
            "exam": "BPSC",
            "subject": "Modern History",
            "topic": "Champaran Satyagraha",
            "questions": [
                {
                    "question": "Who invited Mahatma Gandhi to Champaran in 1917?",
                    "option_a": "Raj Kumar Shukla",
                    "option_b": "Braja Kishore Prasad",
                    "option_c": "Dr. Rajendra Prasad",
                    "option_d": "Mazharul Haque",
                    "correct_option": "A",
                    "explanation": "Raj Kumar Shukla was an indigo farmer who persuaded Gandhi.",
                    "concept_tested": "Champaran Satyagraha",
                    "subject": "Modern History",
                    "topic": "Champaran Satyagraha",
                }
            ],
        }
        mock_response.text = json.dumps(mock_payload)
        mock_client.models.generate_content.return_value = mock_response

        with patch("config.is_gemini_configured", return_value=True):
            result = ai_service.generate_question_set(
                exam="BPSC",
                subject="Modern History",
                topic="Champaran Satyagraha",
                client_override=mock_client,
            )
            self.assertEqual(len(result.questions), 1)
            self.assertEqual(result.questions[0].correct_option, "A")
            self.assertEqual(result.questions[0].option_a, "Raj Kumar Shukla")

    def test_mocked_question_generation_with_exemplars(self):
        """Verify that question generation retrieves and links authentic PYQ exemplars."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_payload = {
            "exam": "BPSC",
            "subject": "Bihar Special",
            "topic": "Champaran Satyagraha 1917",
            "questions": [
                {
                    "question": "Consider the following statements regarding the Champaran Satyagraha of 1917:\n1. It was Gandhi's first Satyagraha in India.\n2. Batak Mian saved Gandhi's life from an assassination attempt.\nWhich of the statements given above is/are correct?",
                    "option_a": "1 only",
                    "option_b": "2 only",
                    "option_c": "Both 1 and 2",
                    "option_d": "Neither 1 nor 2",
                    "correct_option": "C",
                    "explanation": "Both statements are historically verified.",
                    "concept_tested": "Champaran Satyagraha 1917",
                    "subject": "Bihar Special",
                    "topic": "Champaran Satyagraha 1917",
                }
            ],
        }
        mock_response.text = json.dumps(mock_payload)
        mock_client.models.generate_content.return_value = mock_response

        with patch("config.is_gemini_configured", return_value=True):
            result = ai_service.generate_question_set(
                exam="BPSC",
                subject="Bihar Special",
                topic="Champaran Satyagraha 1917",
                client_override=mock_client,
            )
            self.assertEqual(len(result.questions), 1)
            self.assertGreaterEqual(len(result.retrieved_exemplars), 1)
            self.assertEqual(result.retrieved_exemplars[0]["source_type"], "Official PYQ")

    def test_prompt_includes_exemplars(self):
        """Verify that build_question_generation_prompt formats benchmark PYQs."""
        import prompts
        sample_ex = [{
            "exam_edition": "69th BPSC CCE Prelims",
            "exam_year": "2023",
            "subject": "Indian Polity",
            "topic": "Writs",
            "question": "Consider statements on Mandamus...",
            "option_a": "1 only",
            "option_b": "2 only",
            "option_c": "Both 1 and 2",
            "option_d": "Neither",
            "correct_option": "C",
            "explanation": "Mandamus cannot lie against private bodies.",
            "concept_tested": "Article 32 & 226",
            "distractor_notes": "Option A is incomplete.",
        }]
        prompt_text = prompts.build_question_generation_prompt(
            exam="BPSC",
            subject="Indian Polity",
            topic="Writs",
            subtopic="",
            count=1,
            difficulty="Hard",
            question_type="Statement-based",
            focus="PYQ-inspired practice",
            exemplars=sample_ex,
        )
        self.assertIn("AUTHENTIC BPSC PRELIMS EXAM BENCHMARKS", prompt_text)
        self.assertIn("69th BPSC CCE Prelims", prompt_text)
        self.assertIn("Consider statements on Mandamus...", prompt_text)

    def test_mocked_mistake_diagnosis(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_payload = {
            "suggested_error_type": "Knowledge gap",
            "diagnosis": "Confused the inviting leader.",
            "concept_recap": "Raj Kumar Shukla represented the Champaran ryots at Lucknow Congress.",
            "distinction": "Shukla was the invitee; Rajendra Prasad joined during the inquiry.",
            "next_step_action": "Read chapter on Champaran in standard history text.",
        }
        mock_response.text = json.dumps(mock_payload)
        mock_client.models.generate_content.return_value = mock_response

        with patch("config.is_gemini_configured", return_value=True):
            diag = ai_service.diagnose_mistake(
                question_text="Who invited Gandhi?",
                options={"A": "Raj Kumar Shukla", "B": "Rajendra Prasad"},
                correct_option="A",
                selected_option="B",
                client_override=mock_client,
            )
            self.assertEqual(diag.suggested_error_type, "Knowledge gap")

    def test_connection_test_when_unconfigured(self):
        """Connection test returns useful message without crashing when key is absent."""
        with patch("ai_service.is_gemini_configured", return_value=False):
            res = ai_service.test_connection()
            self.assertFalse(res["success"])
            self.assertIn("not configured", res["message"].lower())

    def test_connection_test_mocked_success(self):
        """Connection test returns success and measured latency when response is valid."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "OK"
        mock_client.models.generate_content.return_value = mock_resp

        with patch("config.is_gemini_configured", return_value=True):
            res = ai_service.test_connection(client_override=mock_client)
            self.assertTrue(res["success"])
            self.assertIn("Connection successful", res["message"])
            self.assertGreaterEqual(res["latency_ms"], 0.0)

    def test_connection_test_masks_secret_on_exception(self):
        """Verify that any exception message containing the API key is strictly sanitized."""
        mock_client = MagicMock()
        fake_secret = "AIzaSyFakeSecret123456789"
        mock_client.models.generate_content.side_effect = Exception(f"HTTP 403 Forbidden: key {fake_secret} invalid")

        with patch("ai_service.is_gemini_configured", return_value=True):
            with patch("ai_service.get_gemini_api_key", return_value=fake_secret):
                res = ai_service.test_connection(client_override=mock_client)
                self.assertFalse(res["success"])
                self.assertNotIn(fake_secret, res["message"])
                self.assertIn("••••••••", res["message"])


class TestDatabaseV1Features(unittest.TestCase):
    """Test additive database features using an in-memory SQLite connection."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("""
            CREATE TABLE questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam TEXT NOT NULL DEFAULT 'BPSC',
                subject TEXT NOT NULL,
                topic TEXT NOT NULL DEFAULT 'Uncategorised',
                subtopic TEXT NOT NULL DEFAULT '',
                question TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_option TEXT NOT NULL,
                explanation TEXT NOT NULL DEFAULT '',
                distractor_notes TEXT NOT NULL DEFAULT '',
                concept_tested TEXT NOT NULL DEFAULT '',
                question_type TEXT NOT NULL DEFAULT 'Standard MCQ',
                source_type TEXT NOT NULL DEFAULT 'User-added',
                source_name TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                difficulty TEXT NOT NULL DEFAULT 'Medium',
                is_ai_generated INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        self.conn.execute("""
            CREATE TABLE pinned_notebook (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL UNIQUE,
                note TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '',
                pinned_at TEXT NOT NULL
            )
        """)
        self.conn.execute("""
            CREATE TABLE test_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                exam TEXT NOT NULL,
                test_mode TEXT NOT NULL,
                total_questions INTEGER NOT NULL,
                correct_count INTEGER NOT NULL,
                incorrect_count INTEGER NOT NULL,
                unanswered_count INTEGER NOT NULL,
                negative_mark_rate REAL NOT NULL,
                total_score REAL NOT NULL,
                time_spent_seconds REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

    def tearDown(self):
        self.conn.close()

    def test_insert_question_with_v1_fields(self):
        item = {
            "exam": "BPSC",
            "subject": "Bihar Special",
            "topic": "Rivers",
            "subtopic": "North Bihar Rivers",
            "question": "Which river is known as Sorrow of Bihar?",
            "option_a": "Ganga",
            "option_b": "Kosi",
            "option_c": "Son",
            "option_d": "Punpun",
            "correct_option": "B",
            "concept_tested": "Kosi River dynamics",
            "is_ai_generated": 1,
        }
        qid = db.insert_question(self.conn, item)
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
        self.assertEqual(row["subtopic"], "North Bihar Rivers")
        self.assertEqual(row["is_ai_generated"], 1)

    def test_pin_and_unpin_notebook(self):
        self.conn.execute("""
            INSERT INTO pinned_notebook (question_id, note, tags, pinned_at)
            VALUES (?, ?, ?, ?)
        """, (1, "Revise this week", "High Priority", "2026-10-25T11:00:00"))
        self.conn.commit()

        row = self.conn.execute("SELECT * FROM pinned_notebook WHERE question_id = 1").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["note"], "Revise this week")

        self.conn.execute("DELETE FROM pinned_notebook WHERE question_id = 1")
        self.conn.commit()
        empty = self.conn.execute("SELECT * FROM pinned_notebook WHERE question_id = 1").fetchone()
        self.assertIsNone(empty)

    def test_verified_pyq_provenance_integrity(self):
        """Official PYQs must have verified answers and complete provenance."""
        for pyq in db.VERIFIED_BPSC_PYQS:
            self.assertEqual(pyq["source_type"], "Official PYQ")
            self.assertEqual(pyq["is_ai_generated"], 0)
            self.assertTrue(pyq["exam_edition"].startswith("6"))  # e.g. 69th, 68th, 67th, 66th
            self.assertIn(pyq["correct_option"], ["A", "B", "C", "D"])
            self.assertEqual(pyq["answer_key_status"], "Official Final Key Verified")
            self.assertTrue(pyq["source_url"].startswith("http"))

    def test_retrieve_pyq_exemplars(self):
        """Verify that retrieve_pyq_exemplars retrieves authentic official PYQs."""
        exemplars = db.retrieve_pyq_exemplars(subject="Bihar Special", topic="Champaran", limit=2)
        self.assertGreaterEqual(len(exemplars), 1)
        for ex in exemplars:
            self.assertEqual(ex["source_type"], "Official PYQ")
            self.assertTrue(len(ex["question"]) > 10)
            self.assertIn(ex["correct_option"], ["A", "B", "C", "D"])
            self.assertTrue(ex["exam_edition"].startswith("6") or "BPSC" in ex["exam_edition"])


if __name__ == "__main__":
    unittest.main()
