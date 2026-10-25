"""BPSC Question Lab v1.0 - AI-Powered Exam Preparation Platform.

An adaptive, evidence-based study and revision environment for BPSC CCE & UPSC Prelims.
Integrates official Google Gemini SDK, deterministic analytics, adaptive spaced repetition,
and Supabase cloud compatibility.
"""

from __future__ import annotations

import json
import random
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

import ai_service
import analytics
import config
import db
import revision_engine
import schemas
import supabase_client

APP_VERSION = "1.0.0"

# -----------------------------------------------------------------------------
# Backward Compatibility Exports for Legacy Test Suite
# -----------------------------------------------------------------------------
def connect_db():
    return db.connect_db()

init_db = db.init_db
insert_question = db.insert_question
add_question = db.add_question
list_questions = db.list_questions
get_question_ids = db.get_question_ids

def get_questions_by_ids(ids: List[int]):
    return db.get_questions_by_ids(ids, conn_factory=connect_db)

record_attempt = db.record_attempt
get_attempts = db.get_attempts
get_topic_stats = db.get_topic_stats
save_error_classification = db.save_error_classification

def import_csv(uploaded_file: Any):
    return db.import_csv(uploaded_file, conn_factory=connect_db)

SUBJECTS = db.SUBJECTS
EXAMS = db.EXAMS
DIFFICULTIES = db.DIFFICULTIES
SOURCE_TYPES = db.SOURCE_TYPES
ERROR_TYPES = db.ERROR_TYPES
SAMPLE_QUESTIONS = db.SAMPLE_QUESTIONS
build_weekly_plan = revision_engine.build_weekly_plan



# -----------------------------------------------------------------------------
# App Initialization & State Management
# -----------------------------------------------------------------------------

def init_session_state() -> None:
    """Initialize Streamlit session state variables."""
    db.init_db()
    if "active_test" not in st.session_state:
        st.session_state["active_test"] = None
    if "test_results" not in st.session_state:
        st.session_state["test_results"] = None
    if "studio_questions" not in st.session_state:
        st.session_state["studio_questions"] = None
    if "tutor_history" not in st.session_state:
        st.session_state["tutor_history"] = []
    if "tutor_context_question" not in st.session_state:
        st.session_state["tutor_context_question"] = None
    if "authenticated_user" not in st.session_state:
        st.session_state["authenticated_user"] = None


# -----------------------------------------------------------------------------
# Views: 1. Dashboard
# -----------------------------------------------------------------------------

def show_dashboard() -> None:
    """Overview dashboard with key deterministic metrics and study tools."""
    st.title("📚 BPSC Question Lab v1.0")
    st.caption(f"Version {APP_VERSION} · Personal AI Examination Laboratory for BPSC & UPSC")

    attempts = db.get_attempts()
    sessions = db.get_test_sessions()
    overall = analytics.compute_overall_metrics(attempts, sessions)
    q_all = db.list_questions()

    # Top KPI Metrics
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Question Bank", len(q_all))
    k2.metric("Tests Completed", overall["total_tests"])
    k3.metric("Total Attempts", overall["total_attempts"])
    k4.metric("Overall Accuracy", f"{overall['accuracy']}%" if overall["total_attempts"] > 0 else "N/A")
    k5.metric("Net Score", f"{overall['net_score']:.1f}")

    # Cloud & AI System Status Pills
    s1, s2 = st.columns(2)
    with s1:
        if config.is_gemini_configured():
            st.success(f"🤖 Gemini AI: Connected ({config.get_gemini_model()})")
        else:
            st.warning("🤖 Gemini AI: Not configured. Set GEMINI_API_KEY in `.streamlit/secrets.toml` or `.env`.")
    with s2:
        if config.is_supabase_configured():
            user = st.session_state.get("authenticated_user")
            if user:
                st.success(f"☁️ Supabase Cloud: Logged in as {user.get('email', 'User')}")
            else:
                st.info("☁️ Supabase Cloud: Ready (Login under Settings to sync data)")
        else:
            st.caption("💾 Local Mode: Storing data safely in local SQLite database")

    st.divider()

    # Topic Analytics & Weak Spots
    col_left, col_right = st.columns([3, 2])
    with col_left:
        st.subheader("📊 Weakest Syllabus Areas")
        if not attempts.empty:
            topic_df = analytics.compute_topic_analytics(attempts)
            weak = analytics.identify_weak_areas(topic_df, max_items=5)
            if not weak.empty:
                st.dataframe(
                    weak[["subject", "topic", "attempts", "accuracy", "sample_size_label", "priority"]].rename(
                        columns={"attempts": "Attempts", "accuracy": "Accuracy (%)", "sample_size_label": "Evidence", "priority": "Urgency"}
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.success("No critical weak spots detected with low accuracy! Keep practising.")
        else:
            st.info("No test attempts recorded yet. Start a test to reveal your performance breakdown.")

    with col_right:
        st.subheader("🎯 Quick Actions")
        if st.button("🚀 Start Practice Test", type="primary", use_container_width=True):
            st.session_state["nav_page"] = "Practice & Mock Tests"
            st.rerun()
        if st.button("✨ Generate AI Questions", use_container_width=True):
            st.session_state["nav_page"] = "AI Question Studio"
            st.rerun()
        if st.button("📕 Open Error Notebook", use_container_width=True):
            st.session_state["nav_page"] = "Error Notebook"
            st.rerun()
        if st.button("📅 View Adaptive Revision Plan", use_container_width=True):
            st.session_state["nav_page"] = "Revision Planner"
            st.rerun()


# -----------------------------------------------------------------------------
# Views: 2. Question Bank
# -----------------------------------------------------------------------------

def show_question_bank() -> None:
    """Browse, filter, search, import, and export the question bank."""
    st.title("📖 Question Bank")
    st.write("Browse, filter, import and export questions stored on this computer.")

    # CSV Import Area
    with st.expander("📥 Import Questions from CSV", expanded=False):
        upload = st.file_uploader(
            "Upload CSV file",
            type=["csv"],
            help="Template columns: exam, subject, topic, question, option_a, option_b, option_c, option_d, correct_option",
        )
        if upload is not None and st.button("Import Uploaded CSV", type="primary"):
            inserted, problems = db.import_csv(upload)
            st.success(f"Successfully imported {inserted} question(s).")
            for prob in problems[:10]:
                st.warning(prob)
            if len(problems) > 10:
                st.caption(f"{len(problems) - 10} additional messages not shown.")
            st.rerun()

    all_questions = db.list_questions()
    if all_questions.empty:
        st.info("Your question bank is empty. Add a question or import a CSV.")
        return

    # Filter Controls
    c1, c2, c3, c4, c5 = st.columns(5)
    exam_filter = c1.selectbox("Filter by Exam", ["All", "BPSC", "UPSC"], key="qb_exam")
    subjects = ["All"] + sorted(all_questions["subject"].dropna().unique().tolist())
    subject_filter = c2.selectbox("Filter by Subject", subjects, key="qb_subj")

    interim = db.list_questions(exam=exam_filter, subject=subject_filter)
    topics = ["All"] + sorted(interim["topic"].dropna().unique().tolist())
    topic_filter = c3.selectbox("Filter by Topic", topics, key="qb_top")
    
    src_choices = ["All", "Official PYQ", "Built-in sample", "AI-generated", "User-added"]
    source_filter = c4.selectbox("Provenance / Source", src_choices, key="qb_src")
    search_query = c5.text_input("Search Keyword", placeholder="e.g. Patna, Champaran...")

    filtered = db.list_questions(exam_filter, subject_filter, topic_filter, source_filter)
    if search_query.strip():
        term = search_query.strip().lower()
        filtered = filtered[
            filtered["question"].str.lower().str.contains(term, na=False)
            | filtered["topic"].str.lower().str.contains(term, na=False)
            | filtered["explanation"].str.lower().str.contains(term, na=False)
        ]

    st.caption(f"Showing {len(filtered)} of {len(all_questions)} question(s).")

    # Display Table with Provenance Columns
    disp_cols = [
        "id", "source_type", "exam_edition", "exam_year", "subject", "topic",
        "question", "correct_option", "difficulty", "answer_key_status"
    ]
    available_cols = [c for c in disp_cols if c in filtered.columns]
    st.dataframe(filtered[available_cols], use_container_width=True, hide_index=True)

    # Detailed Provenance Cards
    with st.expander("🔍 View Detailed Question & Provenance Cards", expanded=False):
        for _, q in filtered.head(15).iterrows():
            badge = "🏛️ Official Verified PYQ" if q.get("source_type") == "Official PYQ" else ("🤖 AI-Generated Practice" if q.get("is_ai_generated") else "📌 Practice Sample")
            provenance_line = f"**{badge}**"
            if q.get("exam_edition"):
                provenance_line += f" · {q['exam_edition']}"
            if q.get("exam_year"):
                provenance_line += f" ({q['exam_year']})"
            if q.get("paper_set"):
                provenance_line += f" · {q['paper_set']}"
            if q.get("official_qno") and int(q["official_qno"]) > 0:
                provenance_line += f" · Q.{int(q['official_qno'])}"
            if q.get("answer_key_status"):
                provenance_line += f" · Status: `{q['answer_key_status']}`"

            st.markdown(f"#### Question #{q['id']}: {q['question']}")
            st.caption(provenance_line)
            st.write(f"- **A.** {q['option_a']}\n- **B.** {q['option_b']}\n- **C.** {q['option_c']}\n- **D.** {q['option_d']}")
            st.info(f"**Correct Option:** `{q['correct_option']}` · **Explanation:** {q['explanation']}")
            st.divider()

    # Export Buttons
    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        csv_bytes = all_questions.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Export Questions to CSV",
            data=csv_bytes,
            file_name="bpsc_question_bank_export.csv",
            mime="text/csv",
        )
    with col_exp2:
        attempts = db.get_attempts()
        if not attempts.empty:
            att_csv = attempts.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Export Attempt History to CSV",
                data=att_csv,
                file_name="bpsc_attempts_export.csv",
                mime="text/csv",
            )


# -----------------------------------------------------------------------------
# Views: 3. AI Question Studio
# -----------------------------------------------------------------------------

def show_question_studio() -> None:
    """Dedicated studio to generate, inspect, edit, and save authentic-style questions."""
    st.title("✨ AI Question Studio")
    st.write(
        "Generate authentic, syllabus-aligned practice questions for BPSC and UPSC Prelims. "
        "Questions are strictly practice material inspired by exam patterns, never falsified as official PYQs."
    )

    if not config.is_gemini_configured():
        st.warning("⚠️ Gemini API is not configured. Please add `GEMINI_API_KEY` to your environment to enable AI generation.")
        return

    with st.container(border=True):
        st.subheader("1. Generation Controls")
        c1, c2, c3 = st.columns(3)
        exam = c1.selectbox("Target Exam", ["BPSC", "UPSC", "Both"], index=0)
        subject = c2.selectbox("Subject", db.SUBJECTS, index=0)
        difficulty = c3.selectbox("Difficulty", ["Easy", "Medium", "Hard", "Mixed"], index=1)

        c4, c5, c6 = st.columns(3)
        topic = c4.text_input("Topic", value="Revolt of 1857 in Bihar")
        subtopic = c5.text_input("Subtopic / Theme (Optional)", placeholder="e.g. Kunwar Singh's role, Jagdishpur")
        count = c6.slider("Number of Questions", min_value=1, max_value=10, value=3)

        c7, c8 = st.columns(2)
        question_type = c7.selectbox(
            "Question Type",
            [
                "Standard MCQ",
                "Statement-based (1 and 2 only, etc.)",
                "Chronological Sequence",
                "Matching Columns",
                "Assertion and Reason",
                "Bihar Special Focus",
            ],
            index=0,
        )
        focus = c8.selectbox(
            "Pedagogical Focus",
            [
                "PYQ-inspired practice",
                "Core concept learning",
                "Weak area reinforcement",
                "Tricky distractor elimination",
            ],
            index=0,
        )

        notes_context = st.text_area(
            "Source Material or Reference Notes (Optional)",
            placeholder="Paste excerpts from notes, articles, or syllabus documents here...",
            height=100,
        )

        # Show which genuine BPSC PYQs are available as few-shot exemplars for this subject/topic
        available_exemplars = db.retrieve_pyq_exemplars(
            subject=subject,
            topic=topic.strip() or "General",
            exam=exam,
            limit=3,
        )
        if available_exemplars:
            exemplar_editions = ", ".join(sorted({ex.get("exam_edition", "BPSC PYQ") for ex in available_exemplars if ex.get("exam_edition")}))
            st.caption(
                f"🏛️ **Strict BPSC Benchmark Active**: Will retrieve {len(available_exemplars)} genuine PYQ exemplar(s) "
                f"({exemplar_editions}) to enforce authentic exam depth, multi-statement phrasing, and distractor plausibility."
            )

        if st.button("Generate Questions", type="primary"):
            with st.spinner("Retrieving BPSC PYQs and generating calibrated exam questions..."):
                try:
                    q_set = ai_service.generate_question_set(
                        exam=exam,
                        subject=subject,
                        topic=topic.strip() or "General",
                        subtopic=subtopic.strip(),
                        count=count,
                        difficulty=difficulty if difficulty != "Mixed" else "Medium",
                        question_type=question_type,
                        focus=focus,
                        notes_or_context=notes_context,
                    )
                    st.session_state["studio_questions"] = [q.model_dump() for q in q_set.questions]
                    st.session_state["studio_exemplars"] = q_set.retrieved_exemplars
                    st.success(f"Generated {len(q_set.questions)} question(s) strictly calibrated against {len(q_set.retrieved_exemplars)} genuine BPSC Prelims PYQs!")
                except Exception as exc:
                    st.error(f"Generation error: {exc}")

    # 2. Preview, Edit & Save Area
    studio_items = st.session_state.get("studio_questions")
    if studio_items:
        st.subheader("2. Review & Edit Questions Before Saving")

        exemplars = st.session_state.get("studio_exemplars", [])
        if exemplars:
            with st.expander(f"🏛️ View {len(exemplars)} Genuine BPSC Prelims PYQ Benchmarks Used for Generation", expanded=False):
                st.caption("The AI model was instructed to strictly match the depth, statement structure, and distractor plausibility of these authentic BPSC questions:")
                for ex in exemplars:
                    st.markdown(f"**{ex.get('exam_edition', 'BPSC PYQ')}** (Q.{ex.get('official_qno', '-')}) · *{ex.get('subject')} · {ex.get('topic')}*")
                    st.markdown(f"> **{ex.get('question')}**")
                    st.caption(f"Correct: **{ex.get('correct_option')}** · {ex.get('explanation', '')[:140]}...")
                    st.divider()

        st.info("💡 You can edit any question stem, options, or explanation before saving to your Question Bank.")

        questions_to_save: List[Dict[str, Any]] = []
        for i, q in enumerate(studio_items):
            with st.expander(f"Question {i+1}: {q['question'][:80]}...", expanded=True):
                q_text = st.text_area(f"Question #{i+1}", value=q["question"], key=f"sq_text_{i}")
                o1, o2 = st.columns(2)
                oa = o1.text_input("Option A", value=q["option_a"], key=f"sq_oa_{i}")
                ob = o2.text_input("Option B", value=q["option_b"], key=f"sq_ob_{i}")
                oc = o1.text_input("Option C", value=q["option_c"], key=f"sq_oc_{i}")
                od = o2.text_input("Option D", value=q["option_d"], key=f"sq_od_{i}")

                curr_idx = ["A", "B", "C", "D"].index(q["correct_option"]) if q["correct_option"] in ["A", "B", "C", "D"] else 0
                correct_opt = st.radio("Correct Answer", ["A", "B", "C", "D"], index=curr_idx, horizontal=True, key=f"sq_cor_{i}")

                exp_text = st.text_area("Explanation", value=q.get("explanation", ""), key=f"sq_exp_{i}")
                dist_text = st.text_input("Distractor Notes", value=q.get("distractor_notes", ""), key=f"sq_dist_{i}")
                concept_tested = st.text_input("Concept Tested", value=q.get("concept_tested", ""), key=f"sq_con_{i}")

                questions_to_save.append({
                    "exam": exam,
                    "subject": subject,
                    "topic": topic.strip() or "General",
                    "subtopic": subtopic.strip(),
                    "question": q_text.strip(),
                    "option_a": oa.strip(),
                    "option_b": ob.strip(),
                    "option_c": oc.strip(),
                    "option_d": od.strip(),
                    "correct_option": correct_opt,
                    "explanation": exp_text.strip(),
                    "distractor_notes": dist_text.strip(),
                    "concept_tested": concept_tested.strip(),
                    "question_type": question_type,
                    "source_type": "AI-generated",
                    "source_name": "Question Studio",
                    "source_url": "",
                    "difficulty": difficulty if difficulty != "Mixed" else "Medium",
                    "is_ai_generated": 1,
                })

        col_save, col_clear = st.columns([2, 1])
        if col_save.button("💾 Save All Questions to Question Bank", type="primary"):
            saved_count = 0
            for item in questions_to_save:
                db.add_question(item)
                saved_count += 1
            st.success(f"Saved {saved_count} questions into your Question Bank!")
            st.session_state["studio_questions"] = None
            st.rerun()

        if col_clear.button("Discard Set"):
            st.session_state["studio_questions"] = None
            st.rerun()


# -----------------------------------------------------------------------------
# Views: 4. Practice & Mock Tests
# -----------------------------------------------------------------------------

def show_practice() -> None:
    """Examination engine supporting practice tests, timed tests, and full mocks."""
    st.title("📝 Practice & Mock Tests")
    st.caption("Customizable scoring, negative marking rules, confidence tracking, and error classification.")

    results = st.session_state.get("test_results")
    active_test = st.session_state.get("active_test")

    # Display Test Results if just finished
    if results is not None:
        st.subheader("Test Scorecard")
        total = len(results["items"])
        correct = sum(1 for r in results["items"] if r["is_correct"])
        incorrect = sum(1 for r in results["items"] if not r["is_correct"] and r["selected_option"] != "-")
        unanswered = sum(1 for r in results["items"] if r["selected_option"] == "-")
        accuracy = round(correct / total * 100) if total > 0 else 0

        sc1, sc2, sc3, sc4, sc5 = st.columns(5)
        sc1.metric("Total Score", f"{results['total_score']:.2f}")
        sc2.metric("Accuracy", f"{accuracy}%")
        sc3.metric("Correct", correct)
        sc4.metric("Incorrect", incorrect)
        sc5.metric("Unanswered", unanswered)

        st.divider()

        # Detailed Review per Question
        for idx, res in enumerate(results["items"], start=1):
            status = "✅ Correct" if res["is_correct"] else ("⚠️ Unanswered" if res["selected_option"] == "-" else "❌ Incorrect")
            with st.expander(f"{status} | Question {idx}: {res['question'][:75]}...", expanded=not res["is_correct"]):
                st.markdown(f"**{res['question']}**")
                st.write(f"**Your Answer:** {res['selected_option']}. {res['selected_text']}")
                st.write(f"**Correct Answer:** {res['correct_option']}. {res['correct_text']}")
                if res.get("explanation"):
                    st.info(f"**Explanation:** {res['explanation']}")
                if res.get("distractor_notes"):
                    st.caption(f"**Distractor Analysis:** {res['distractor_notes']}")

                # Action: Explain My Mistake with AI Tutor
                if not res["is_correct"] and config.is_gemini_configured():
                    if st.button(f"🔍 Explain My Mistake with AI Tutor", key=f"tutor_ask_{idx}"):
                        st.session_state["tutor_context_question"] = res
                        st.session_state["nav_page"] = "AI Study Tutor"
                        st.rerun()

        if st.button("Start Another Test", type="primary"):
            st.session_state["test_results"] = None
            st.session_state["active_test"] = None
            st.rerun()
        return

    # Configuration for New Test
    with st.container(border=True):
        st.subheader("Configure Test Session")
        f1, f2, f3, f4 = st.columns(4)
        exam = f1.selectbox("Exam", ["All", "BPSC", "UPSC"], key="p_exam")
        subjects = ["All"] + sorted(db.list_questions()["subject"].dropna().unique().tolist())
        subject = f2.selectbox("Subject", subjects, key="p_subj")
        interim = db.list_questions(exam=exam, subject=subject)
        topics = ["All"] + sorted(interim["topic"].dropna().unique().tolist())
        topic = f3.selectbox("Topic", topics, key="p_top")
        src_types = ["All Questions", "Official PYQs Only", "AI Practice Sets", "Starter Samples"]
        src_choice = f4.selectbox("Question Provenance", src_types, key="p_src")

        src_map = {
            "All Questions": "All",
            "Official PYQs Only": "Official PYQ",
            "AI Practice Sets": "AI-generated",
            "Starter Samples": "Built-in sample",
        }
        matching_ids = db.get_question_ids(exam, subject, topic, source_type=src_map[src_choice])
        if not matching_ids:
            st.warning("No questions match these filters. Add or generate some questions first.")
            return

        c_cnt, c_mode, c_neg = st.columns(3)
        count = c_cnt.slider(
            "Questions in test",
            min_value=1,
            max_value=min(50, len(matching_ids)),
            value=min(10, len(matching_ids)),
        )
        test_mode = c_mode.selectbox(
            "Test Mode", ["Practice (Untimed)", "Timed Drill (1 min/Q)", "Full Mock Exam"]
        )
        negative_rate = c_neg.selectbox(
            "Negative Marking",
            [0.0, 0.25, 0.33],
            format_func=lambda x: f"None (0.0)" if x == 0.0 else f"-{x} marks per wrong answer",
        )

        if st.button("🚀 Start Test", type="primary"):
            selected_ids = random.sample(matching_ids, k=count)
            st.session_state["active_test"] = {
                "session_id": str(uuid.uuid4())[:8],
                "question_ids": selected_ids,
                "exam": exam,
                "test_mode": test_mode,
                "negative_rate": negative_rate,
                "start_time": time.time(),
            }
            st.rerun()

    # Active Test Submission Form
    if active_test:
        q_frame = db.get_questions_by_ids(active_test["question_ids"])
        st.subheader(f"Test in Progress · {len(q_frame)} questions ({active_test['test_mode']})")

        answers: Dict[int, str] = {}
        confidences: Dict[int, str] = {}

        with st.form("active_test_form"):
            for i, row in q_frame.iterrows():
                qid = int(row["id"])
                st.markdown(f"**{i + 1}. {row['question']}**")
                st.caption(f"{row['subject']} · {row['topic']} · Difficulty: {row['difficulty']}")

                opts = {
                    "A": str(row["option_a"]),
                    "B": str(row["option_b"]),
                    "C": str(row["option_c"]),
                    "D": str(row["option_d"]),
                }
                c_opt, c_conf = st.columns([3, 1])
                selection = c_opt.radio(
                    "Select Option",
                    options=list(opts.keys()),
                    format_func=lambda val, o=opts: f"{val}. {o[val]}",
                    key=f"ans_{qid}",
                    index=None,
                )
                conf = c_conf.selectbox(
                    "Confidence",
                    ["High", "Medium", "Guess"],
                    key=f"conf_{qid}",
                )
                answers[qid] = selection or "-"
                confidences[qid] = conf
                st.divider()

            submitted = st.form_submit_button("Submit Test & View Analysis", type="primary")

        if submitted:
            time_spent = round(time.time() - active_test["start_time"], 1)
            results_items = []
            correct_cnt = 0
            incorrect_cnt = 0
            unanswered_cnt = 0
            total_score = 0.0

            for _, row in q_frame.iterrows():
                qid = int(row["id"])
                chosen = answers.get(qid, "-")
                correct = row["correct_option"]
                is_correct = chosen == correct
                confidence = confidences.get(qid, "Medium")

                # Scoring calculation
                if chosen == "-":
                    q_score = 0.0
                    unanswered_cnt += 1
                elif is_correct:
                    q_score = 1.0
                    correct_cnt += 1
                else:
                    q_score = -float(active_test["negative_rate"])
                    incorrect_cnt += 1
                total_score += q_score

                # Persist to database
                db.record_attempt(
                    question_id=qid,
                    selected_option=chosen,
                    correct_option=correct,
                    test_session_id=active_test["session_id"],
                    time_spent_seconds=time_spent / len(q_frame),
                    confidence_rating=confidence,
                    score=q_score,
                )

                opts = {"A": row["option_a"], "B": row["option_b"], "C": row["option_c"], "D": row["option_d"]}
                results_items.append({
                    "question_id": qid,
                    "question": row["question"],
                    "selected_option": chosen,
                    "selected_text": opts.get(chosen, "Not answered"),
                    "is_correct": is_correct,
                    "correct_option": correct,
                    "correct_text": opts.get(correct, ""),
                    "explanation": row.get("explanation", ""),
                    "distractor_notes": row.get("distractor_notes", ""),
                    "subject": row["subject"],
                    "topic": row["topic"],
                })

            # Record session summary
            db.record_test_session(
                session_id=active_test["session_id"],
                exam=active_test["exam"],
                test_mode=active_test["test_mode"],
                total_questions=len(q_frame),
                correct_count=correct_cnt,
                incorrect_count=incorrect_cnt,
                unanswered_count=unanswered_cnt,
                negative_mark_rate=active_test["negative_rate"],
                total_score=total_score,
                time_spent_seconds=time_spent,
            )

            st.session_state["test_results"] = {
                "items": results_items,
                "total_score": total_score,
                "time_spent": time_spent,
            }
            st.session_state["active_test"] = None
            st.rerun()


# -----------------------------------------------------------------------------
# Views: 5. AI Study Tutor
# -----------------------------------------------------------------------------

def show_ai_tutor() -> None:
    """Conversational study tutor with pedagogical modes and mistake analysis."""
    st.title("🎓 AI Study Tutor")
    st.write("Understand core concepts, analyze mistakes, explore mnemonics, and test understanding.")

    if not config.is_gemini_configured():
        st.warning("⚠️ Gemini API is not configured. Please add `GEMINI_API_KEY` to enable the AI Tutor.")
        return

    # Check if arrived from a test mistake
    ctx_q = st.session_state.get("tutor_context_question")
    if ctx_q:
        st.info(f"📍 Context: Analyzing your mistake on **{ctx_q['subject']} · {ctx_q['topic']}**")

    c_mode, c_clear = st.columns([4, 1])
    mode = c_mode.selectbox(
        "Pedagogical Mode",
        [
            "Explain my mistake",
            "Explain from first principles",
            "Give a short BPSC exam-oriented explanation",
            "Explain why each option is right or wrong",
            "Give me a hint without revealing the answer",
            "Teach using a simple example or analogy",
            "Give me a memory aid, comparison table or timeline",
            "Explain the difference between two easily confused concepts",
            "Ask me follow-up questions to test understanding",
        ],
    )
    if c_clear.button("Clear Chat"):
        st.session_state["tutor_history"] = []
        st.session_state["tutor_context_question"] = None
        st.rerun()

    # User Query Input
    user_query = st.chat_input("Ask a question, enter two concepts to compare, or request clarification...")

    # Display Chat History
    for msg in st.session_state["tutor_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_query or (ctx_q and not st.session_state["tutor_history"]):
        prompt_query = user_query or f"Why was my answer ({ctx_q['selected_option']}) wrong, and how do I master this?"
        st.session_state["tutor_history"].append({"role": "user", "content": prompt_query})
        with st.chat_message("user"):
            st.markdown(prompt_query)

        with st.chat_message("assistant"):
            with st.spinner("AI Tutor is thinking..."):
                try:
                    ans = ai_service.tutor_query(
                        mode=mode,
                        user_query=prompt_query,
                        question_text=ctx_q["question"] if ctx_q else "",
                        options={
                            "A": ctx_q.get("selected_text", "") if ctx_q and ctx_q.get("selected_option") == "A" else "",
                            "B": ctx_q.get("correct_text", "") if ctx_q and ctx_q.get("correct_option") == "B" else "",
                        } if ctx_q else None,
                        correct_option=ctx_q["correct_option"] if ctx_q else "",
                        selected_option=ctx_q["selected_option"] if ctx_q else "",
                        explanation=ctx_q.get("explanation", "") if ctx_q else "",
                        chat_history=st.session_state["tutor_history"],
                    )
                    st.markdown(ans)
                    st.session_state["tutor_history"].append({"role": "assistant", "content": ans})
                except Exception as exc:
                    st.error(f"Tutor error: {exc}")


# -----------------------------------------------------------------------------
# Views: 6. Performance Coach
# -----------------------------------------------------------------------------

def show_performance_coach() -> None:
    """Diagnostic report generator that synthesizes deterministic test metrics."""
    st.title("🏆 AI Performance Coach")
    st.caption("Evidence-based diagnostic report evaluating your real test history and error patterns.")

    attempts = db.get_attempts()
    sessions = db.get_test_sessions()
    if attempts.empty:
        st.info("No attempts recorded yet. Complete a few practice tests to generate your performance diagnostic.")
        return

    overall = analytics.compute_overall_metrics(attempts, sessions)
    topic_df = analytics.compute_topic_analytics(attempts)
    error_counts = analytics.compute_error_distribution(attempts)

    col1, col2, col3 = st.columns(3)
    col1.metric("Tests Tracked", overall["total_tests"])
    col2.metric("Total Questions Attempted", overall["total_attempts"])
    col3.metric("Measured Accuracy", f"{overall['accuracy']}%")

    if st.button("🔍 Generate AI Diagnostic Report", type="primary"):
        with st.spinner("Performance Coach is evaluating test data..."):
            try:
                summary_stats = {
                    "total_attempts": overall["total_attempts"],
                    "accuracy": overall["accuracy"],
                    "total_tests": overall["total_tests"],
                    "topic_stats": topic_df.head(8).to_dict("records"),
                    "error_counts": error_counts,
                }
                recent_incorrect = attempts[attempts["is_correct"] == 0].head(10).to_dict("records")
                report: schemas.DiagnosticReport = ai_service.generate_performance_coach_report(
                    summary_stats, recent_incorrect
                )
                st.session_state["coach_report"] = report.model_dump()
                st.success("Performance Diagnostic Report ready!")
            except Exception as exc:
                st.error(f"Coach error: {exc}")

    # Display Report
    saved_report = st.session_state.get("coach_report")
    if saved_report:
        st.divider()
        st.subheader("📋 Diagnostic Summary")
        st.write(saved_report["test_summary"])

        c_str, c_wk = st.columns(2)
        with c_str:
            st.markdown("#### 💪 Demonstrated Strengths")
            for s in saved_report.get("strong_areas", []):
                st.markdown(f"- {s}")
        with c_wk:
            st.markdown("#### ⚠️ High-Priority Weak Areas")
            for w in saved_report.get("weak_areas", []):
                st.markdown(f"- {w}")

        st.subheader("🛠️ Recommended Action Items")
        for item in saved_report.get("recommended_action_items", []):
            with st.container(border=True):
                st.markdown(f"**{item['topic']}** · Priority: `{item['priority']}`")
                st.write(item["action"])
                st.caption(f"**Evidence:** {item['rationale']}")


# -----------------------------------------------------------------------------
# Views: 7. Error Notebook
# -----------------------------------------------------------------------------

def show_error_notebook() -> None:
    """Persistent mistake diagnosis and question pinning system."""
    st.title("📕 Error Notebook")
    st.write("Track every incorrect answer, understand root causes, and pin tricky questions for revision.")

    attempts = db.get_attempts()
    if attempts.empty:
        st.info("No test attempts recorded yet. Mistakes from tests will appear here automatically.")
        return

    incorrect = attempts[attempts["is_correct"] == 0].copy()
    if incorrect.empty:
        st.success("🎉 No incorrect attempts recorded so far! Keep practising to test your knowledge.")
        return

    # Mistake Drill Action
    c_hdr1, c_hdr2 = st.columns([3, 1])
    c_hdr1.metric("Total Recorded Mistakes", len(incorrect))
    if c_hdr2.button("🎯 Practice My Mistakes", type="primary", use_container_width=True):
        missed_ids = list(incorrect["question_id"].unique())
        selected_ids = random.sample(missed_ids, k=min(10, len(missed_ids)))
        st.session_state["active_test"] = {
            "session_id": str(uuid.uuid4())[:8],
            "question_ids": selected_ids,
            "exam": "BPSC",
            "test_mode": "Mistake Remediation Drill",
            "negative_rate": 0.0,
            "start_time": time.time(),
        }
        st.session_state["nav_page"] = "Practice & Mock Tests"
        st.rerun()

    st.divider()

    # Filter by Error Classification
    f_col1, f_col2 = st.columns(2)
    err_filter = f_col1.selectbox("Filter by Mistake Reason", ["All"] + db.ERROR_TYPES)
    filtered = incorrect
    if err_filter != "All":
        filtered = filtered[filtered["error_type"] == err_filter]

    st.caption(f"Showing {len(filtered)} mistake(s).")

    for _, row in filtered.head(25).iterrows():
        att_id = int(row["attempt_id"])
        qid = int(row["question_id"])
        is_pinned = db.is_question_pinned(qid)

        pin_label = "📌 Pinned" if is_pinned else "📍 Pin for Revision"
        with st.expander(f"{row['subject']} · {row['topic']} · {row['attempted_at'][:16]}", expanded=(row["error_type"] == "Unclassified")):
            st.markdown(f"**Question:** {row['question']}")
            ans_display = "Not answered" if row["selected_option"] == "-" else row["selected_option"]
            st.write(f"**Your Answer:** {ans_display} · **Correct Answer:** {row['correct_option']}")
            if row.get("explanation"):
                st.info(f"**Explanation:** {row['explanation']}")

            ec1, ec2 = st.columns([1, 2])
            current_err_idx = db.ERROR_TYPES.index(row["error_type"]) if row["error_type"] in db.ERROR_TYPES else 0
            err_type = ec1.selectbox("Classify Mistake", db.ERROR_TYPES, index=current_err_idx, key=f"nb_err_{att_id}")
            err_note = ec2.text_input("Personal Study Note", value=str(row["error_notes"] or ""), key=f"nb_note_{att_id}")

            btn_col1, btn_col2, btn_col3 = st.columns(3)
            if btn_col1.button("Save Classification", key=f"save_err_{att_id}"):
                db.save_error_classification(att_id, err_type, err_note)
                st.success("Classification saved!")
                st.rerun()

            if btn_col2.button(pin_label, key=f"pin_{att_id}"):
                if is_pinned:
                    db.unpin_question(qid)
                    st.info("Unpinned question.")
                else:
                    db.pin_question(qid, note=err_note)
                    st.success("Question pinned to notebook!")
                st.rerun()

            if config.is_gemini_configured() and btn_col3.button("🤖 Diagnose with AI", key=f"ai_diag_{att_id}"):
                with st.spinner("Diagnosing mistake..."):
                    try:
                        diag = ai_service.diagnose_mistake(
                            question_text=row["question"],
                            options={"A": "", "B": "", "C": "", "D": ""},
                            correct_option=row["correct_option"],
                            selected_option=row["selected_option"],
                            explanation=row.get("explanation", ""),
                            subject=row["subject"],
                            topic=row["topic"],
                        )
                        st.markdown(f"**AI Diagnosis:** {diag.diagnosis}")
                        st.markdown(f"**Core Concept:** {diag.concept_recap}")
                        st.markdown(f"**Next Action:** {diag.next_step_action}")
                        db.save_error_classification(att_id, diag.suggested_error_type, diag.next_step_action)
                    except Exception as exc:
                        st.error(f"Diagnosis failed: {exc}")


# -----------------------------------------------------------------------------
# Views: 8. Revision Planner
# -----------------------------------------------------------------------------

def show_revision_planner() -> None:
    """Adaptive 7-day revision schedule with spaced repetition intervals."""
    st.title("📅 Adaptive Revision Planner")
    st.write("Evidence-driven study plan based on accuracy, error recurrence, and interval spacing.")

    attempts = db.get_attempts()
    topic_stats = db.get_topic_stats()

    # Target Exam Configuration
    with st.container(border=True):
        st.subheader("Configure Target Exam & Study Rhythm")
        c1, c2, c3 = st.columns(3)
        exam_target_date = c1.date_input("Target Exam Date", value=date.today() + timedelta(days=90))
        daily_minutes = c2.slider("Daily Revision Budget (minutes)", min_value=30, max_value=240, value=90, step=15)
        preferred_subj = c3.multiselect("Focus Subjects (Optional)", db.SUBJECTS, default=[])

    # Retention Metric Check
    retention = analytics.measure_revision_outcome(attempts)
    if retention["retried_topics_count"] > 0:
        st.success(
            f"📈 Revision Effectiveness: Retried topics showed an average accuracy gain of "
            f"**{retention['average_gain']:+0.1f}%** across {retention['retried_topics_count']} topics!"
        )

    # Generate Adaptive Plan
    plan = revision_engine.generate_adaptive_weekly_plan(
        stats=topic_stats,
        attempts=attempts,
        target_exam_date=exam_target_date,
        daily_available_minutes=daily_minutes,
        preferred_subjects=preferred_subj,
    )

    st.subheader("7-Day Revision Schedule")
    for item in plan:
        with st.container(border=True):
            st.markdown(f"### {item['day']} ({item['date']}) · {item['subject']}: {item['topic']}")
            st.write(item["task"])
            col_meta1, col_meta2 = st.columns([3, 1])
            col_meta1.caption(f"**Rationale:** {item['basis']}")
            col_meta2.caption(f"⏱️ Est: {item['estimated_minutes']} mins")

    # Export Plan
    plan_df = pd.DataFrame(plan)
    csv_bytes = plan_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download Weekly Plan as CSV",
        data=csv_bytes,
        file_name="bpsc_weekly_revision_plan.csv",
        mime="text/csv",
    )


# -----------------------------------------------------------------------------
# Views: 9. Current Affairs & Sources
# -----------------------------------------------------------------------------

def show_current_affairs() -> None:
    """Source-aware research and syllabus fact synthesis with citations."""
    st.title("🌐 Current Affairs & Source Research")
    st.write("Extract high-yield exam facts, policy highlights, and Bihar-specific angles with verifiable citations.")

    if not config.is_gemini_configured():
        st.warning("⚠️ Gemini API is not configured. Please add `GEMINI_API_KEY` to enable research synthesis.")
        return

    with st.container(border=True):
        st.subheader("Research Syllabus Topic")
        q_text = st.text_input("Enter topic, government scheme, or policy development", value="Bihar Industrial Investment Promotion Policy")
        bihar_angle = st.checkbox("Include Bihar-specific angle & state budget linkage", value=True)

        if st.button("🔍 Research & Synthesize", type="primary"):
            with st.spinner("Synthesizing verified exam facts..."):
                try:
                    summary_text, citations = ai_service.research_topic_with_grounding(
                        query=q_text, include_bihar_angle=bihar_angle
                    )
                    st.session_state["research_result"] = {
                        "topic": q_text,
                        "text": summary_text,
                        "citations": citations,
                    }
                    st.success("Research synthesis complete!")
                except Exception as exc:
                    st.error(f"Research failed: {exc}")

    res = st.session_state.get("research_result")
    if res:
        st.subheader(f"Synthesis: {res['topic']}")
        st.markdown(res["text"])

        if res["citations"]:
            st.markdown("#### 🔗 Retrieved Sources & Grounding Citations")
            for c in res["citations"]:
                st.markdown(f"- [{c['title']}]({c['url']})")

        c_save, c_gen = st.columns(2)
        if c_save.button("💾 Save Research Notes"):
            db.save_research_note(
                topic=res["topic"],
                title=res["topic"],
                summary=res["text"],
                key_facts=[],
                bihar_angle="Included" if bihar_angle else "",
            )
            st.success("Saved to Research Notes!")

        if c_gen.button("✨ Generate MCQs from this Research"):
            st.session_state["nav_page"] = "AI Question Studio"
            st.rerun()


# -----------------------------------------------------------------------------
# Views: 10. Settings & Data Management
# -----------------------------------------------------------------------------

def show_settings() -> None:
    """Authentication, API key status, cloud synchronization, and local backups."""
    st.title("⚙️ Settings & Data Management")

    # API Configuration Status
    st.subheader("1. AI Service Configuration")
    key = config.get_gemini_api_key()
    c_s1, c_s2 = st.columns(2)
    c_s1.write(f"**Gemini API Key:** `{config.mask_secret(key)}`")
    c_s2.write(f"**Active Model:** `{config.get_gemini_model()}`")

    # On-demand connection tester (only triggers on explicit user click)
    col_t1, col_t2 = st.columns([1, 2])
    if col_t1.button("🔌 Test Gemini Connection", type="primary"):
        with st.spinner("Testing API connection..."):
            res = ai_service.test_connection()
            st.session_state["gemini_test_result"] = res

    conn_res = st.session_state.get("gemini_test_result")
    if conn_res:
        if conn_res["success"]:
            st.success(f"✅ {conn_res['message']}")
        else:
            st.error(f"❌ {conn_res['message']}")

    if not config.is_gemini_configured():
        st.info(
            "To configure your Gemini key:\n"
            "1. Create `.streamlit/secrets.toml` in your project folder.\n"
            "2. Add: `GEMINI_API_KEY = \"your_api_key_here\"`"
        )

    st.divider()

    # Supabase Cloud Authentication & Migration
    st.subheader("2. Supabase Cloud Sync")
    if config.is_supabase_configured():
        user = st.session_state.get("authenticated_user")
        if user:
            st.success(f"Logged in as: **{user['email']}** (ID: `{user['id'][:8]}...`)")
            col_m1, col_m2 = st.columns(2)
            if col_m1.button("☁️ Sync Local SQLite Data to Supabase", type="primary"):
                with st.spinner("Syncing data to Supabase..."):
                    try:
                        res = supabase_client.migrate_local_data_to_supabase(user["id"])
                        st.success(f"Synced {res['questions_migrated']} questions and {res['sessions_migrated']} sessions!")
                    except Exception as exc:
                        st.error(f"Migration error: {exc}")
            if col_m2.button("Logout"):
                supabase_client.sign_out()
                st.session_state["authenticated_user"] = None
                st.rerun()
        else:
            t_login, t_signup = st.tabs(["Log In", "Sign Up"])
            with t_login:
                with st.form("sb_login_form"):
                    l_email = st.text_input("Email")
                    l_pass = st.text_input("Password", type="password")
                    if st.form_submit_button("Log In"):
                        ok, msg, usr = supabase_client.sign_in(l_email, l_pass)
                        if ok:
                            st.session_state["authenticated_user"] = usr
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
            with t_signup:
                with st.form("sb_signup_form"):
                    s_email = st.text_input("Email")
                    s_pass = st.text_input("Password", type="password")
                    if st.form_submit_button("Register"):
                        ok, msg, usr = supabase_client.sign_up(s_email, s_pass)
                        if ok:
                            st.success("Account created! Please log in.")
                        else:
                            st.error(msg)
    else:
        st.caption(
            "Supabase credentials are not configured. To enable cloud database sync and multi-user login, "
            "set `SUPABASE_URL` and `SUPABASE_ANON_KEY` in `.streamlit/secrets.toml`."
        )

    st.divider()

    # Local SQLite Backup
    st.subheader("3. Local Data Backup & Export")
    st.write("Create a full JSON snapshot of all questions, attempts, test sessions, and notebook notes.")
    json_data = db.export_sqlite_to_json()
    st.download_button(
        "⬇️ Download Complete SQLite Database Snapshot (JSON)",
        data=json_data.encode("utf-8"),
        file_name=f"question_lab_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
    )


# -----------------------------------------------------------------------------
# Main Application Entry Point
# -----------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="BPSC Question Lab v1.0",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_session_state()

    # Sidebar Navigation
    st.sidebar.title("📚 Question Lab")
    st.sidebar.caption(f"v{APP_VERSION} · BPSC CCE & UPSC")

    pages = [
        "Dashboard",
        "Question Bank",
        "AI Question Studio",
        "Practice & Mock Tests",
        "AI Study Tutor",
        "AI Performance Coach",
        "Error Notebook",
        "Revision Planner",
        "Current Affairs & Sources",
        "Settings & Data",
    ]

    # Handle programmatic redirects
    default_page = st.session_state.get("nav_page", "Dashboard")
    if default_page not in pages:
        default_page = "Dashboard"

    selected_page = st.sidebar.radio("Navigate", pages, index=pages.index(default_page))
    st.session_state["nav_page"] = selected_page

    st.sidebar.divider()
    st.sidebar.markdown(
        "**Target Exam:** 71st BPSC CCE Prelims\n\n"
        "**Syllabus Coverage:**\n"
        "- History of India & Bihar\n"
        "- Bihar Special Geography\n"
        "- Indian Polity & Economy\n"
        "- General Science & Tech\n"
        "- Current Affairs\n"
    )

    # Route to selected page
    if selected_page == "Dashboard":
        show_dashboard()
    elif selected_page == "Question Bank":
        show_question_bank()
    elif selected_page == "AI Question Studio":
        show_question_studio()
    elif selected_page == "Practice & Mock Tests":
        show_practice()
    elif selected_page == "AI Study Tutor":
        show_ai_tutor()
    elif selected_page == "AI Performance Coach":
        show_performance_coach()
    elif selected_page == "Error Notebook":
        show_error_notebook()
    elif selected_page == "Revision Planner":
        show_revision_planner()
    elif selected_page == "Current Affairs & Sources":
        show_current_affairs()
    elif selected_page == "Settings & Data":
        show_settings()


if __name__ == "__main__":
    main()
