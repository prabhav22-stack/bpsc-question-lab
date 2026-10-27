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

    def test_hindi_mock_question_schema(self):
        """Verify ExtractedMockQuestion accepts original_language and original_question_hindi."""
        mq = schemas.ExtractedMockQuestion(
            question="Which article of the Constitution provides for the Election Commission?",
            option_a="Article 324",
            option_b="Article 356",
            option_c="Article 280",
            option_d="Article 370",
            correct_option="A",
            explanation="Article 324 provides for the Election Commission.",
            subject="Polity",
            topic="Election Commission",
            original_language="Hindi",
            original_question_hindi="संविधान का कौन सा अनुच्छेद निर्वाचन आयोग का प्रावधान करता है?",
        )
        self.assertEqual(mq.original_language, "Hindi")
        self.assertIn("निर्वाचन आयोग", mq.original_question_hindi)


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

    def test_translate_hindi_question_to_english(self):
        """Verify translating Hindi question with mocked Gemini response."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = json.dumps({
            "question": "Which article of the Indian Constitution provides for the Election Commission?",
            "option_a": "Article 324",
            "option_b": "Article 356",
            "option_c": "Article 280",
            "option_d": "Article 370",
            "explanation": "Article 324 vests the superintendence, direction, and control of elections in an Election Commission.",
        })
        mock_client.models.generate_content.return_value = mock_resp

        with patch("ai_service.is_gemini_configured", return_value=True), \
             patch("ai_service._get_client", return_value=mock_client):
            res = ai_service.translate_hindi_question_to_english(
                question="संविधान का कौन सा अनुच्छेद निर्वाचन आयोग का प्रावधान करता है?",
                option_a="अनुच्छेद 324",
                option_b="अनुच्छेद 356",
                option_c="अनुच्छेद 280",
                option_d="अनुच्छेद 370",
                explanation="अनुच्छेद 324 निर्वाचन आयोग से संबंधित है।",
            )
            self.assertEqual(res["question"], "Which article of the Indian Constitution provides for the Election Commission?")
            self.assertEqual(res["option_a"], "Article 324")

    def test_mocked_mnemonic_generation(self):
        """Verify generating memory mnemonics with mocked Gemini client."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = json.dumps({
            "mnemonic": "Shukla Invited Bapu to Champaran (SIBC)",
            "core_fact": "Raj Kumar Shukla persuaded Mahatma Gandhi to visit Champaran in 1917.",
            "trap_to_avoid": "Do not confuse Shukla with Dr. Rajendra Prasad who joined the inquiry committee later.",
            "bihar_angle": "Champaran is located in North-West Bihar (Tirhut Division).",
        })
        mock_client.models.generate_content.return_value = mock_resp
        anchor = ai_service.generate_mnemonic_anchor(
            question_text="Who invited Gandhi to Champaran?",
            options={"A": "Raj Kumar Shukla", "B": "Rajendra Prasad"},
            correct_option="A",
            client_override=mock_client,
        )
        self.assertIn("SIBC", anchor.mnemonic)
        self.assertIn("Tirhut", anchor.bihar_angle)

    def test_mocked_question_deep_dive(self):
        """Verify generating question deep dive exam intelligence."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = json.dumps({
            "high_yield_facts": ["Lucknow Pact 1916", "Tinkathia System (3/20th)", "Batak Mian assassination plot foiled"],
            "bpsc_trend_note": "BPSC asks at least 1 question on Champaran in every CCE Prelims.",
            "likely_exam_variations": ["Chronology of Gandhi's early satyagrahas: Champaran -> Ahmedabad -> Kheda"],
            "related_articles_or_dates": "December 1916 (Lucknow Session) -> April 1917 (Motihari arrival)",
        })
        mock_client.models.generate_content.return_value = mock_resp
        dive = ai_service.generate_question_deep_dive(
            question_text="Who invited Gandhi to Champaran?",
            options={"A": "Raj Kumar Shukla"},
            correct_option="A",
            client_override=mock_client,
        )
        self.assertEqual(len(dive.high_yield_facts), 3)
        self.assertIn("BPSC asks at least 1 question", dive.bpsc_trend_note)

    def test_mocked_weekly_strategy_briefing(self):
        """Verify weekly study strategy briefing synthesis."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = json.dumps({
            "executive_summary": "Solid accuracy in History, urgent reinforcement needed in General Science.",
            "daily_focus_tips": ["Monday: Focus on 1857 Bihar revolt leaders", "Tuesday: Revise Fundamental Rights"],
            "neglected_subject_alert": "General Science has only 2 attempts this week.",
            "exam_mindset_tip": "Do not rush question stems with 'Not correct' qualifiers.",
        })
        mock_client.models.generate_content.return_value = mock_resp
        briefing = ai_service.synthesize_weekly_strategy_briefing(
            schedule_days=[{"day_number": 1, "topic": "Modern History"}],
            overall_stats={"accuracy": 72, "total_attempts": 25},
            error_counts={"Knowledge gap": 4},
            client_override=mock_client,
        )
        self.assertIn("General Science", briefing.neglected_subject_alert)
        self.assertEqual(len(briefing.daily_focus_tips), 2)

    def test_consult_gemini_architect(self):
        """Verify consultative helper for technical queries."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Recommended approach: Use RapidOCR with text fallback."
        mock_client.models.generate_content.return_value = mock_resp
        res = ai_service.consult_gemini_architect(
            query="Best OCR approach for bilingual scans?",
            client_override=mock_client,
        )
        self.assertIn("RapidOCR", res)



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
                exam_edition TEXT NOT NULL DEFAULT '',
                exam_year TEXT NOT NULL DEFAULT '',
                paper_set TEXT NOT NULL DEFAULT '',
                official_qno INTEGER NOT NULL DEFAULT 0,
                answer_key_status TEXT NOT NULL DEFAULT 'Unverified',
                original_language TEXT NOT NULL DEFAULT 'English',
                original_question_hindi TEXT NOT NULL DEFAULT '',
                normalized_stem TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        db._ensure_mock_files_table(self.conn)
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
            self.assertTrue(any(pyq["exam_edition"].startswith(p) for p in ("6", "7")))
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

    def test_update_question_fields(self):
        """Verify update_question_fields updates question fields and recomputes normalized_stem."""
        qid = db.insert_question(self.conn, {
            "question": "संविधान का कौन सा अनुच्छेद?",
            "option_a": "A",
            "option_b": "B",
            "option_c": "C",
            "option_d": "D",
            "correct_option": "A",
            "subject": "Polity",
            "original_language": "Hindi",
        })
        self.conn.commit()

        # Mock connect_db to return self.conn
        with patch("db.connect_db") as mock_conn_fn:
            mock_conn_fn.return_value.__enter__.return_value = self.conn
            updated = db.update_question_fields(qid, {
                "question": "Which article of the Constitution?",
                "original_question_hindi": "संविधान का कौन सा अनुच्छेद?",
            })
            self.assertTrue(updated)

        row = self.conn.execute("SELECT question, original_question_hindi, normalized_stem FROM questions WHERE id = ?", (qid,)).fetchone()
        self.assertEqual(row["question"], "Which article of the Constitution?")
        self.assertEqual(row["original_question_hindi"], "संविधान का कौन सा अनुच्छेद?")
        self.assertIn("which article of the constitution", row["normalized_stem"])

    def test_adjacent_pyq_separation_and_management(self):
        """Verify that BPSC-Adjacent PYQs are strictly separated from Mocks and Official PYQs."""
        # Insert 1 Official PYQ, 1 Adjacent PYQ (CDPO), and 1 Mock Question
        db.insert_question(self.conn, {
            "question": "What is the capital of ancient Magadha?",
            "option_a": "Rajgriha", "option_b": "Patliputra", "option_c": "Vaishali", "option_d": "Champa",
            "correct_option": "A", "explanation": "Rajgriha was the first capital of Magadha.",
            "source_type": "Official PYQ", "source_name": "67th BPSC CCE", "exam_edition": "67th BPSC CCE Prelims",
            "subject": "History", "exam_year": 2022
        })
        db.insert_question(self.conn, {
            "question": "When was the Bihar Development Council formed?",
            "option_a": "1952", "option_b": "1954", "option_c": "1956", "option_d": "1960",
            "correct_option": "A", "explanation": "Formed in 1952.",
            "source_type": "Adjacent PYQ", "source_name": "BPSC CDPO Prelims 2022", "exam_edition": "BPSC CDPO Prelims 2022",
            "subject": "Bihar Special", "exam_year": 2022
        })
        db.insert_question(self.conn, {
            "question": "Which coaching test series mock question is this?",
            "option_a": "Test 1", "option_b": "Test 2", "option_c": "Test 3", "option_d": "Test 4",
            "correct_option": "A", "explanation": "Coaching mock test.",
            "source_type": "Mock question", "source_name": "Drishti Mock 01", "exam_edition": "Drishti Mock 01 (Mock PDF)",
            "subject": "Polity"
        })
        self.conn.commit()

        with patch("db.connect_db") as mock_conn_fn:
            mock_conn_fn.return_value.__enter__.return_value = self.conn

            # 1. Verify list_questions separation
            adj_df = db.list_questions(source_type="Adjacent PYQ")
            self.assertEqual(len(adj_df), 1)
            self.assertEqual(adj_df.iloc[0]["source_name"], "BPSC CDPO Prelims 2022")
            self.assertEqual(adj_df.iloc[0]["source_type"], "Adjacent PYQ")

            mock_df = db.list_questions(source_type="Mock question")
            self.assertEqual(len(mock_df), 1)
            self.assertEqual(mock_df.iloc[0]["source_name"], "Drishti Mock 01")

            off_df = db.list_questions(source_type="Official PYQ")
            self.assertEqual(len(off_df), 1)
            self.assertEqual(off_df.iloc[0]["source_name"], "67th BPSC CCE")

            # 2. Verify get_adjacent_exam_names
            adj_names = db.get_adjacent_exam_names()
            self.assertIn("BPSC CDPO Prelims 2022", adj_names)
            self.assertNotIn("Drishti Mock 01", adj_names)

            # 3. Verify delete_adjacent_exam
            del_cnt = db.delete_adjacent_exam("BPSC CDPO Prelims 2022")
            self.assertEqual(del_cnt, 1)

            # Check that adjacent question was deleted, but mock and official remain intact
            self.assertEqual(len(db.list_questions(source_type="Adjacent PYQ")), 0)
            self.assertEqual(len(db.list_questions(source_type="Mock question")), 1)
            self.assertEqual(len(db.list_questions(source_type="Official PYQ")), 1)

    def test_ocr_jobs_job_type_segregation(self):
        """Verify that OCR jobs isolate background execution by job_type ('mock' vs 'pyq')."""
        with patch("db.connect_db") as mock_conn_fn:
            mock_conn_fn.return_value.__enter__.return_value = self.conn

            db.create_ocr_job(
                job_id="job-mock-1",
                filename="mock_test_01.pdf",
                mock_title="Drishti Mock Test 01",
                target_exam="BPSC",
                job_type="mock",
            )
            db.create_ocr_job(
                job_id="job-pyq-1",
                filename="bpsc_cdpo_2022.pdf",
                mock_title="BPSC CDPO Prelims 2022",
                target_exam="BPSC",
                job_type="pyq",
            )

            # Mock job query should only return job-mock-1
            active_mock = db.get_active_ocr_job(job_type="mock")
            self.assertIsNotNone(active_mock)
            self.assertEqual(active_mock["job_id"], "job-mock-1")
            self.assertEqual(active_mock["job_type"], "mock")

            # PYQ job query should only return job-pyq-1
            active_pyq = db.get_active_ocr_job(job_type="pyq")
            self.assertIsNotNone(active_pyq)
            self.assertEqual(active_pyq["job_id"], "job-pyq-1")
            self.assertEqual(active_pyq["job_type"], "pyq")


class TestMockQuestionsAndPDFExtractor(unittest.TestCase):
    """Test suite for Mock Questions database features and PDF OCR extraction pipeline."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("""
            CREATE TABLE questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam TEXT NOT NULL DEFAULT 'BPSC',
                subject TEXT NOT NULL,
                topic TEXT NOT NULL DEFAULT 'General',
                question TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_option TEXT NOT NULL,
                explanation TEXT NOT NULL DEFAULT '',
                source_type TEXT NOT NULL DEFAULT 'User-added',
                source_name TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                difficulty TEXT NOT NULL DEFAULT 'Medium',
                created_at TEXT NOT NULL,
                subtopic TEXT NOT NULL DEFAULT '',
                is_ai_generated INTEGER NOT NULL DEFAULT 0,
                distractor_notes TEXT NOT NULL DEFAULT '',
                concept_tested TEXT NOT NULL DEFAULT '',
                question_type TEXT NOT NULL DEFAULT 'Standard MCQ',
                exam_edition TEXT NOT NULL DEFAULT '',
                exam_year TEXT NOT NULL DEFAULT '',
                paper_set TEXT NOT NULL DEFAULT '',
                official_qno INTEGER NOT NULL DEFAULT 0,
                answer_key_status TEXT NOT NULL DEFAULT 'Unverified',
                original_language TEXT NOT NULL DEFAULT 'English',
                original_question_hindi TEXT NOT NULL DEFAULT '',
                normalized_stem TEXT NOT NULL DEFAULT ''
            )
        """)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_extracted_mock_question_schema_normalization(self):
        """Test subject normalization and option cleaning in ExtractedMockQuestion."""
        q = schemas.ExtractedMockQuestion(
            question="Which river is known as the Sorrow of Bihar?",
            option_a="Ganga",
            option_b="Kosi",
            option_c="Son",
            option_d="Gandak",
            correct_option="B",
            explanation="The Kosi River causes frequent flooding in North Bihar.",
            subject="bihar special",  # lowercase should normalize
            topic="River Systems",
        )
        self.assertEqual(q.subject, "Bihar Special")
        self.assertEqual(q.correct_option, "B")

        # Test polity normalization
        q_pol = schemas.ExtractedMockQuestion(
            question="Which Article deals with Financial Emergency?",
            option_a="Article 352",
            option_b="Article 356",
            option_c="Article 360",
            option_d="Article 368",
            correct_option="C",
            explanation="Article 360 empowers the President to proclaim Financial Emergency.",
            subject="polity",
            topic="Emergency Provisions",
        )
        self.assertEqual(q_pol.subject, "Indian Polity")

    def test_extracted_mock_question_set(self):
        """Test ExtractedMockQuestionSet with multiple items."""
        q_set = schemas.ExtractedMockQuestionSet(
            questions=[
                schemas.ExtractedMockQuestion(
                    question="Test Q1",
                    option_a="A1",
                    option_b="B1",
                    option_c="C1",
                    option_d="D1",
                    correct_option="A",
                    subject="Modern History",
                ),
                schemas.ExtractedMockQuestion(
                    question="Test Q2",
                    option_a="A2",
                    option_b="B2",
                    option_c="C2",
                    option_d="D2",
                    correct_option="C",
                    subject="General Science",
                ),
            ]
        )
        self.assertEqual(len(q_set.questions), 2)
        self.assertEqual(q_set.questions[0].subject, "Modern History")
        self.assertEqual(q_set.questions[1].subject, "General Science")

    def test_mock_questions_db_operations(self):
        """Test inserting mock questions and listing via db.list_mock_questions."""
        item = {
            "exam": "BPSC",
            "subject": "Modern History",
            "topic": "1857 Revolt",
            "question": "Who led the 1857 uprising in Rohilkhand?",
            "option_a": "Khan Bahadur Khan",
            "option_b": "Kunwar Singh",
            "option_c": "Nana Saheb",
            "option_d": "Begum Hazrat Mahal",
            "correct_option": "A",
            "explanation": "Khan Bahadur Khan led the rebellion in Bareilly/Rohilkhand.",
            "source_type": "Mock question",
            "source_name": "Test Series Mock 1",
            "exam_edition": "Test Series Mock 1 (Mock PDF)",
            "difficulty": "Medium",
        }
        qid = db.insert_question(self.conn, item)
        self.conn.commit()

        # Query using connection
        row = self.conn.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["source_type"], "Mock question")
        self.assertEqual(row["source_name"], "Test Series Mock 1")

        # Test delete operation
        self.conn.execute("DELETE FROM questions WHERE source_type = 'Mock question' AND source_name = ?", ("Test Series Mock 1",))
        self.conn.commit()
        cnt = self.conn.execute("SELECT COUNT(*) FROM questions WHERE source_type = 'Mock question'").fetchone()[0]
        self.assertEqual(cnt, 0)

    def test_pdf_extractor_detect_and_slice(self):
        """Test PDF type detection and slicing with in-memory PDFs."""
        import io
        import pypdf
        import pdf_extractor

        # 1. Blank/scanned PDF (no text)
        w_blank = pypdf.PdfWriter()
        w_blank.add_blank_page(width=200, height=200)
        w_blank.add_blank_page(width=200, height=200)
        buf_blank = io.BytesIO()
        w_blank.write(buf_blank)
        reader_blank = pypdf.PdfReader(io.BytesIO(buf_blank.getvalue()))

        is_scanned, mode_desc, total_pages = pdf_extractor.detect_pdf_type(reader_blank)
        self.assertTrue(is_scanned)
        self.assertIn("Scanned Image", mode_desc)
        self.assertEqual(total_pages, 2)

        # 2. Slicing test
        sliced_bytes = pdf_extractor.slice_pdf_chunk(reader_blank, 0, 1)
        sliced_reader = pypdf.PdfReader(io.BytesIO(sliced_bytes))
        self.assertEqual(len(sliced_reader.pages), 1)

    def test_normalize_question_text(self):
        """Verify that question stems are normalized accurately across numbered variations."""
        stems = [
            "1. Which river is known as the Sorrow of Bihar?",
            "Q. 1 Which river is known as the Sorrow of Bihar",
            "Question 1: Which river is known as the Sorrow of Bihar?",
            "(1) Which river is known as the Sorrow of Bihar?",
            "Which river is known as the Sorrow of Bihar?",
        ]
        normalized = [db.normalize_question_text(s) for s in stems]
        # All 5 variations must produce the exact same normalized stem
        self.assertEqual(len(set(normalized)), 1)
        self.assertEqual(normalized[0], "which river is known as the sorrow of bihar")

    def test_filter_duplicate_questions(self):
        """Verify that filter_duplicate_questions detects intra-batch and database duplicates."""
        # Insert a baseline question into self.conn
        item = {
            "exam": "BPSC",
            "subject": "Geography",
            "topic": "Rivers",
            "question": "Which river is known as the Sorrow of Bihar?",
            "option_a": "Ganga",
            "option_b": "Kosi",
            "option_c": "Son",
            "option_d": "Gandak",
            "correct_option": "B",
        }
        db.insert_question(self.conn, item)
        self.conn.commit()

        incoming_batch = [
            # 1. Duplicate of question already in DB (with leading '1. ')
            {
                "question": "1. Which river is known as the Sorrow of Bihar?",
                "option_a": "Ganga",
                "option_b": "Kosi",
                "option_c": "Son",
                "option_d": "Gandak",
                "correct_option": "B",
                "subject": "Geography",
            },
            # 2. New unique question
            {
                "question": "What is the capital of Bihar?",
                "option_a": "Gaya",
                "option_b": "Patna",
                "option_c": "Munger",
                "option_d": "Bhagalpur",
                "correct_option": "B",
                "subject": "Bihar Special",
            },
            # 3. Repeat of question 2 within the same batch (intra-batch duplicate)
            {
                "question": "Q2. What is the capital of Bihar?",
                "option_a": "Gaya",
                "option_b": "Patna",
                "option_c": "Munger",
                "option_d": "Bhagalpur",
                "correct_option": "B",
                "subject": "Bihar Special",
            },
        ]

        unique_qs, dupes = db.filter_duplicate_questions(incoming_batch, conn=self.conn)
        self.assertEqual(len(unique_qs), 1)
        self.assertEqual(len(dupes), 2)
        self.assertIn("capital of Bihar", unique_qs[0]["question"])
        self.assertIn("Already exists", dupes[0]["duplicate_reason"])
        self.assertIn("current upload batch", dupes[1]["duplicate_reason"])

    def test_pdf_upload_registry(self):
        """Verify tracking of uploaded mock PDF file names and hashes."""
        # Test file not uploaded yet
        is_up, _ = db.is_pdf_already_uploaded("drishti_mock_01.pdf", "hash123")
        self.assertFalse(is_up)

        # Record file
        db.record_uploaded_pdf(
            filename="drishti_mock_01.pdf",
            file_hash="hash123",
            mock_title="Drishti Mock 01",
            questions_count=100,
        )

        # Test file detected
        is_up2, meta = db.is_pdf_already_uploaded("drishti_mock_01.pdf", "hash123")
        self.assertTrue(is_up2)
        self.assertEqual(meta["mock_title"], "Drishti Mock 01")
        self.assertEqual(meta["questions_count"], 100)

        # Cleanup
        db.delete_mock_test("Drishti Mock 01")
        is_up3, _ = db.is_pdf_already_uploaded("drishti_mock_01.pdf", "hash123")
        self.assertFalse(is_up3)

    def test_ocr_engine_probes_and_listing(self):
        """Verify that get_available_ocr_engines correctly enumerates RapidOCR, PaddleOCR, Pytesseract, and Gemini."""
        import ocr_engine

        engines = ocr_engine.get_available_ocr_engines()
        self.assertIsInstance(engines, list)
        self.assertGreaterEqual(len(engines), 4)

        keys = [e["key"] for e in engines]
        self.assertIn("rapidocr", keys)
        self.assertIn("paddleocr", keys)
        self.assertIn("pytesseract", keys)
        self.assertIn("gemini_vision", keys)
        self.assertIn("gemini_file", keys)

        # Gemini Vision cloud fallback must always report available=True
        gemini_eng = next(e for e in engines if e["key"] == "gemini_vision")
        self.assertTrue(gemini_eng["available"])

    def test_ocr_quality_evaluator(self):
        """Verify that evaluate_ocr_quality distinguishes real MCQs from degraded scans/noise."""
        import ocr_engine

        # Empty or very short
        self.assertFalse(ocr_engine.evaluate_ocr_quality(""))
        self.assertFalse(ocr_engine.evaluate_ocr_quality("Short text"))

        # Random non-MCQ noise
        noise = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore."
        self.assertFalse(ocr_engine.evaluate_ocr_quality(noise))

        # Authentic MCQ text with options
        mcq_text = (
            "1. Who among the following led the Revolt of 1857 in Jagdishpur, Bihar?\n"
            "(A) Amar Singh\n"
            "(B) Kunwar Singh\n"
            "(C) Hare Krishna Singh\n"
            "(D) Pir Ali\n"
            "Correct Answer: (B)\n"
            "Explanation: Veer Kunwar Singh led the rebellion in Bihar."
        )
        self.assertTrue(ocr_engine.evaluate_ocr_quality(mcq_text))

        # Bilingual / format variation with question words and options
        bilingual_mcq = (
            "Which article of the Indian Constitution deals with the Election Commission of India?\n"
            "a. Article 324\n"
            "b. Article 280\n"
            "c. Article 356\n"
            "d. Article 370\n"
            "Consider the following statements and select the correct option."
        )
        self.assertTrue(ocr_engine.evaluate_ocr_quality(bilingual_mcq))

    def test_local_ocr_cascade_execution_and_fallback(self):
        """Verify cascaded local OCR: uses text mode when quality is good, falls back to Vision when quality is low."""
        import io
        from unittest.mock import MagicMock, patch
        import pypdf
        import pdf_extractor

        # Create a sample 2-page blank PDF
        w = pypdf.PdfWriter()
        w.add_blank_page(width=200, height=200)
        w.add_blank_page(width=200, height=200)
        buf = io.BytesIO()
        w.write(buf)
        pdf_bytes = buf.getvalue()

        # Mock Gemini response
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "questions": [
                {
                    "question": "Which river is known as the Sorrow of Bihar?",
                    "option_a": "Ganga",
                    "option_b": "Kosi",
                    "option_c": "Son",
                    "option_d": "Gandak",
                    "correct_option": "B",
                    "explanation": "Kosi causes frequent flooding in North Bihar.",
                    "subject": "Bihar Special",
                    "topic": "Rivers",
                    "difficulty": "Easy",
                    "question_type": "Static",
                }
            ]
        })

        # Case 1: Local OCR succeeds with high quality text
        high_quality_ocr = (
            "1. Which river is known as the Sorrow of Bihar?\n"
            "(a) Ganga\n(b) Kosi\n(c) Son\n(d) Gandak\n"
            "Explanation: Kosi causes seasonal floods in Bihar."
        )
        with patch("config.is_gemini_configured", return_value=True), \
             patch("ai_service._get_client") as mock_get_client, \
             patch("ocr_engine.ocr_page", return_value=(high_quality_ocr, "RapidOCR (ONNX)", 0.92)):

            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_response
            mock_get_client.return_value = mock_client

            qs, stats = pdf_extractor.extract_mock_questions_from_pdf(
                pdf_bytes=pdf_bytes,
                mock_title="Test Cascade Mock",
                ocr_strategy="auto",
            )

            self.assertEqual(len(qs), 1)
            self.assertEqual(stats["local_ocr_pages"], 2)
            self.assertEqual(stats["vision_fallback_pages"], 0)
            self.assertGreater(stats["tokens_saved_estimate"], 0)
            self.assertIn("RapidOCR (ONNX)", stats["local_engines_used"])

        # Case 2: Local OCR yields degraded/empty text -> Automatic fallback to Gemini Multimodal Vision!
        with patch("config.is_gemini_configured", return_value=True), \
             patch("ai_service._get_client") as mock_get_client, \
             patch("ocr_engine.ocr_page", return_value=("", "None", 0.0)):

            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_response
            mock_get_client.return_value = mock_client

            qs2, stats2 = pdf_extractor.extract_mock_questions_from_pdf(
                pdf_bytes=pdf_bytes,
                mock_title="Test Fallback Mock",
                ocr_strategy="auto",
            )

            self.assertEqual(len(qs2), 1)
            # Must fall back to Gemini Multimodal Vision to guarantee zero lost questions
            self.assertEqual(stats2["local_ocr_pages"], 0)
            self.assertEqual(stats2["vision_fallback_pages"], 2)

    def test_gemini_native_file_api_extraction(self):
        """Verify extraction using Gemini Native File API with upload and cleanup."""
        import io
        from unittest.mock import MagicMock, patch
        import pypdf
        import pdf_extractor

        # Create a sample 2-page blank PDF
        w = pypdf.PdfWriter()
        w.add_blank_page(width=200, height=200)
        w.add_blank_page(width=200, height=200)
        buf = io.BytesIO()
        w.write(buf)
        pdf_bytes = buf.getvalue()

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "questions": [
                {
                    "question": "Which Mauryan ruler embraced Buddhism after the Kalinga War?",
                    "option_a": "Chandragupta Maurya",
                    "option_b": "Bindusara",
                    "option_c": "Ashoka",
                    "option_d": "Brihadratha",
                    "correct_option": "C",
                    "explanation": "Ashoka embraced Buddhism after witnessing the devastation of the Kalinga War.",
                    "subject": "Ancient & Medieval History",
                    "topic": "Mauryan Empire",
                    "difficulty": "Easy",
                    "question_type": "Standard MCQ",
                    "original_language": "English",
                }
            ]
        })

        mock_file = MagicMock()
        mock_file.name = "files/test_mock_123"
        mock_file.state = "ACTIVE"

        mock_client = MagicMock()
        mock_client.files.upload.return_value = mock_file
        mock_client.models.generate_content.return_value = mock_response

        with patch("config.is_gemini_configured", return_value=True), \
             patch("ai_service._get_client", return_value=mock_client):

            qs, stats = pdf_extractor.extract_mock_questions_from_pdf(
                pdf_bytes=pdf_bytes,
                mock_title="Test Mauryan Mock",
                ocr_strategy="gemini_file",
                chunk_size=4,
            )

            self.assertEqual(len(qs), 1)
            self.assertEqual(qs[0]["question"], "Which Mauryan ruler embraced Buddhism after the Kalinga War?")
            self.assertEqual(qs[0]["correct_option"], "C")
            self.assertEqual(stats["gemini_file_pages"], 2)
            self.assertEqual(stats["ocr_strategy"], "gemini_file")

            # Verify client.files.upload was called with temporary file
            self.assertTrue(mock_client.files.upload.called)
            # Verify client.files.delete was called to clean up uploaded file
            mock_client.files.delete.assert_called_with(name="files/test_mock_123")

    def test_safe_parse_question_json_truncated_recovery(self):
        """Verify that truncated Gemini JSON outputs are safely recovered without crashing."""
        import pdf_extractor

        # Incomplete JSON simulation cut off mid-question by token limit
        truncated_json = """
        {
            "questions": [
                {
                    "question": "What is the capital of Bihar?",
                    "option_a": "Patna",
                    "option_b": "Gaya",
                    "option_c": "Munger",
                    "option_d": "Bhagalpur",
                    "correct_option": "A",
                    "explanation": "Patna is the state capital.",
                    "subject": "Bihar Special"
                },
                {
                    "question": "Who was the first Chief Minister of Bihar?",
                    "option_a": "Sri Krishna Sinha",
                    "option_b": "Incomplete cut off text...
        """
        recovered = pdf_extractor.safe_parse_question_json(truncated_json)
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["question"], "What is the capital of Bihar?")
        self.assertEqual(recovered[0]["correct_option"], "A")

    def test_optimize_image_for_fast_ocr(self):
        """Verify that oversized scans (>1600px) are downscaled and converted to grayscale for fast OCR."""
        from PIL import Image
        import ocr_engine

        # Create a large 3000x2000 RGB test image
        large_img = Image.new("RGB", (3000, 2000), color=(255, 255, 255))
        opt_img = ocr_engine.optimize_image_for_fast_ocr(large_img, max_dim=1600)

        # Max dimension must now be <= 1600
        self.assertLessEqual(max(opt_img.size), 1600)
        self.assertEqual(opt_img.size[0], 1600)
        self.assertEqual(opt_img.size[1], int(2000 * (1600 / 3000)))
        # Must be single-channel grayscale ("L")
        self.assertEqual(opt_img.mode, "L")

    def test_ocr_jobs_db_lifecycle_and_cancellation(self):
        """Verify the SQLite ocr_jobs lifecycle: create, update progress, cancel request, query active, and clear."""
        # Use our in-memory test connection
        conn_factory = lambda: self.conn

        job_id = "test_job_101"
        db.create_ocr_job(
            job_id=job_id,
            filename="mock_01.pdf",
            mock_title="Drishti BPSC 01",
            target_exam="BPSC",
            total_pages=20,
            conn_factory=conn_factory,
        )

        # Must report as active job
        active = db.get_active_ocr_job(conn_factory=conn_factory)
        self.assertIsNotNone(active)
        self.assertEqual(active["job_id"], job_id)
        self.assertEqual(active["status"], "running")
        self.assertFalse(db.is_ocr_job_cancel_requested(job_id, conn_factory=conn_factory))

        # Update progress
        db.update_ocr_job_progress(
            job_id=job_id,
            progress=0.50,
            progress_msg="Processing page 10 (50%)...",
            processed_pages=10,
            conn_factory=conn_factory,
        )
        job = db.get_ocr_job(job_id, conn_factory=conn_factory)
        self.assertAlmostEqual(job["progress"], 0.50)
        self.assertEqual(job["processed_pages"], 10)

        # Request cancellation
        db.request_cancel_ocr_job(job_id, conn_factory=conn_factory)
        self.assertTrue(db.is_ocr_job_cancel_requested(job_id, conn_factory=conn_factory))
        job_cancelled = db.get_ocr_job(job_id, conn_factory=conn_factory)
        self.assertEqual(job_cancelled["status"], "cancelled")

        # Clear job
        db.clear_ocr_job(job_id, conn_factory=conn_factory)
        self.assertIsNone(db.get_ocr_job(job_id, conn_factory=conn_factory))

    def test_background_job_cancellation_abort(self):
        """Verify that a background extraction job stops immediately when cancel is requested."""
        import io
        import time
        from unittest.mock import MagicMock, patch
        import pypdf
        import pdf_extractor

        # Create a 4-page blank PDF
        w = pypdf.PdfWriter()
        for _ in range(4):
            w.add_blank_page(width=200, height=200)
        buf = io.BytesIO()
        w.write(buf)
        pdf_bytes = buf.getvalue()

        # Start job
        job_id = pdf_extractor.start_background_extraction_job(
            pdf_bytes=pdf_bytes,
            filename="cancel_test.pdf",
            mock_title="Cancel Test Mock",
            chunk_size=1,
        )

        # Request cancel immediately
        db.request_cancel_ocr_job(job_id)
        self.assertTrue(db.is_ocr_job_cancel_requested(job_id))

        # Wait briefly for thread to terminate
        time.sleep(0.5)
        job = db.get_ocr_job(job_id)
        self.assertEqual(job["status"], "cancelled")
        # Cleanup
        db.clear_ocr_job(job_id)



if __name__ == "__main__":
    unittest.main()
