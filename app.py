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
# -----------------------------------------------------------------------------
# App Initialization, Custom Styling & State Management
# -----------------------------------------------------------------------------

def inject_custom_css() -> None:
    """Inject modern, responsive CSS styling for high-yield exam preparation UI."""
    css = """
    <style>
    /* Global Container & Typography Polish */
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 3rem;
        max-width: 1200px;
    }
    
    /* Modern Card Container */
    .bpsc-card {
        background: var(--background-color, #ffffff);
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-radius: 12px;
        padding: 18px 22px;
        margin-bottom: 16px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .bpsc-card:hover {
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
    }
    
    /* Hero Banner */
    .bpsc-hero {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #1e293b 100%);
        color: #ffffff;
        padding: 24px 28px;
        border-radius: 16px;
        margin-bottom: 24px;
        border: 1px solid rgba(255, 255, 255, 0.12);
        box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.35);
    }
    .bpsc-hero-badge {
        display: inline-block;
        background: rgba(245, 158, 11, 0.2);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.4);
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        margin-bottom: 8px;
    }
    
    /* Provenance Badges */
    .bpsc-badge {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.2px;
    }
    .badge-pyq {
        background-color: #ecfdf5;
        color: #065f46;
        border: 1px solid #a7f3d0;
    }
    .badge-ai {
        background-color: #f5f3ff;
        color: #5b21b6;
        border: 1px solid #ddd6fe;
    }
    .badge-sample {
        background-color: #eff6ff;
        color: #1e40af;
        border: 1px solid #bfdbfe;
    }
    .badge-verified {
        background-color: #fef3c7;
        color: #92400e;
        border: 1px solid #fde68a;
    }
    .badge-difficulty-easy {
        background-color: #f0fdf4;
        color: #166534;
        border: 1px solid #bbf7d0;
    }
    .badge-difficulty-medium {
        background-color: #fffbeb;
        color: #92400e;
        border: 1px solid #fde68a;
    }
    .badge-difficulty-hard {
        background-color: #fef2f2;
        color: #991b1b;
        border: 1px solid #fecaca;
    }
    
    /* Metric Cards Enhancement */
    [data-testid="stMetric"] {
        background: rgba(248, 250, 252, 0.85);
        border: 1px solid rgba(226, 232, 240, 0.95);
        border-radius: 12px;
        padding: 14px 18px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    
    /* Sidebar Brand Box */
    .sidebar-brand-card {
        background: linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%);
        color: white;
        padding: 16px;
        border-radius: 14px;
        margin-bottom: 16px;
        border: 1px solid rgba(255, 255, 255, 0.15);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
    .sidebar-target-box {
        background: rgba(30, 58, 138, 0.07);
        border-left: 3px solid #3b82f6;
        padding: 12px 14px;
        border-radius: 0 10px 10px 0;
        font-size: 13px;
        margin-top: 12px;
        line-height: 1.4;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


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
    """Overview dashboard with key deterministic metrics, syllabus readiness, and quick study tools."""
    st.markdown(
        """
        <div class="bpsc-hero">
            <span class="bpsc-hero-badge">🎯 71st BPSC CCE Prelims Target Tracker</span>
            <h2 style="color: white; margin: 8px 0 4px 0; font-size: 26px; font-weight: 800;">BPSC Question Lab</h2>
            <p style="color: #cbd5e1; margin: 0; font-size: 14px;">
                Evidence-based exam preparation with authentic 10-year PYQ benchmarks, AI practice sets, and deterministic spaced repetition.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    attempts = db.get_attempts()
    sessions = db.get_test_sessions()
    overall = analytics.compute_overall_metrics(attempts, sessions)
    q_all = db.list_questions()
    pyq_count = len(q_all[q_all["source_type"] == "Official PYQ"]) if not q_all.empty else 0

    # Top KPI Metrics with helpful tooltips and status deltas
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Question Bank", f"{len(q_all)} MCQs", help=f"Includes {pyq_count} verified official BPSC PYQs")
    k2.metric("Tests Completed", overall["total_tests"], help="Total mock and drill test sessions recorded")
    k3.metric("Total Attempts", overall["total_attempts"], help="Individual question attempts logged")
    
    acc_val = f"{overall['accuracy']}%" if overall["total_attempts"] > 0 else "N/A"
    acc_delta = "Ready" if overall["accuracy"] >= 70 else ("In Progress" if overall["total_attempts"] > 0 else None)
    k4.metric("Overall Accuracy", acc_val, delta=acc_delta)
    
    k5.metric("Net Score", f"{overall['net_score']:.1f}", help="With official negative marking (-0.33) applied")

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

    # Visual Analytics & Weak Spots
    col_left, col_right = st.columns([3, 2])
    with col_left:
        st.subheader("📊 Syllabus Mastery & Weak Spots")
        if not attempts.empty:
            # Subject Mastery Bar Chart
            try:
                subj_acc = attempts.groupby("subject").apply(
                    lambda g: round((g["is_correct"] == 1).sum() / len(g) * 100)
                ).to_frame(name="Accuracy (%)")
                if not subj_acc.empty:
                    st.caption("Subject-wise Accuracy Breakdown (%)")
                    st.bar_chart(subj_acc, color="#3b82f6", use_container_width=True)
            except Exception:
                pass

            topic_df = analytics.compute_topic_analytics(attempts)
            weak = analytics.identify_weak_areas(topic_df, max_items=5)
            if not weak.empty:
                st.write("**Top Priority Topics for Revision:**")
                st.dataframe(
                    weak[["subject", "topic", "attempts", "accuracy", "sample_size_label", "priority"]].rename(
                        columns={"attempts": "Attempts", "accuracy": "Accuracy (%)", "sample_size_label": "Evidence", "priority": "Urgency"}
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.success("🎉 No critical weak spots detected with low accuracy! Keep practising.")
        else:
            st.info("No test attempts recorded yet. Start a test to reveal your subject mastery breakdown.")

    with col_right:
        st.subheader("🎯 Quick Actions")
        with st.container(border=True):
            st.markdown("**🚀 Start Practice Test**")
            st.caption("Timed drills or full mocks with customizable negative marking.")
            if st.button("Launch Practice Test", type="primary", use_container_width=True):
                st.session_state["nav_page"] = "Practice & Mock Tests"
                st.rerun()

        with st.container(border=True):
            st.markdown("**✨ AI Question Studio**")
            st.caption("Generate exam-grade questions benchmarked against official PYQs.")
            if st.button("Open Question Studio", use_container_width=True):
                st.session_state["nav_page"] = "AI Question Studio"
                st.rerun()

        with st.container(border=True):
            st.markdown("**📕 Error Notebook**")
            st.caption("Analyze incorrect attempts and diagnose recurring mistakes.")
            if st.button("Review My Mistakes", use_container_width=True):
                st.session_state["nav_page"] = "Error Notebook"
                st.rerun()

        with st.container(border=True):
            st.markdown("**📅 Adaptive Revision Plan**")
            st.caption("7-day spaced repetition schedule based on your performance.")
            if st.button("View Revision Schedule", use_container_width=True):
                st.session_state["nav_page"] = "Revision Planner"
                st.rerun()


# -----------------------------------------------------------------------------
# Views: 2. Question Bank
# -----------------------------------------------------------------------------

def show_question_bank() -> None:
    """Browse, filter, search, import, and export the question bank with rich interactive cards."""
    st.title("📖 Question Bank")
    st.caption("Browse, filter, search, and export official PYQs and practice questions.")

    all_questions = db.list_questions()
    if all_questions.empty:
        st.info("Your question bank is empty. Add a question or import a CSV.")
        return

    # Top KPI Summary Cards for Question Bank
    pyqs = all_questions[all_questions["source_type"] == "Official PYQ"]
    ai_qs = all_questions[all_questions["is_ai_generated"] == 1]
    samples = all_questions[all_questions["source_type"] == "Built-in sample"]

    qb1, qb2, qb3, qb4 = st.columns(4)
    qb1.metric("Total Questions", len(all_questions))
    qb2.metric("🏛️ Official PYQs", len(pyqs), help="Authentic questions from 60th to 69th BPSC CCE Prelims")
    qb3.metric("🤖 AI Practice Sets", len(ai_qs), help="Generated practice questions matching BPSC standard")
    qb4.metric("📌 Starter Samples", len(samples), help="Built-in curriculum anchor questions")

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

    # Filter & Search Controls Container
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        exam_filter = c1.selectbox("Filter by Exam", ["All", "BPSC", "UPSC"], key="qb_exam")
        subjects = ["All"] + sorted(all_questions["subject"].dropna().unique().tolist())
        subject_filter = c2.selectbox("Filter by Subject", subjects, key="qb_subj")

        interim = db.list_questions(exam=exam_filter, subject=subject_filter)
        topics = ["All"] + sorted(interim["topic"].dropna().unique().tolist())
        topic_filter = c3.selectbox("Filter by Topic", topics, key="qb_top")
        
        src_choices = ["All", "Official PYQ", "Built-in sample", "AI-generated", "User-added"]
        source_filter = c4.selectbox("Provenance / Source", src_choices, key="qb_src")

        search_query = st.text_input("🔍 Search Keyword in Questions, Topics, or Explanations", placeholder="e.g. Patna, Kunwar Singh, Champaran, Directive Principles...")

    filtered = db.list_questions(exam_filter, subject_filter, topic_filter, source_filter)
    if search_query.strip():
        term = search_query.strip().lower()
        filtered = filtered[
            filtered["question"].str.lower().str.contains(term, na=False)
            | filtered["topic"].str.lower().str.contains(term, na=False)
            | filtered["explanation"].str.lower().str.contains(term, na=False)
        ]

    # Display Mode Toggle: Table View vs Interactive Question Cards
    st.markdown(f"**Showing {len(filtered)} of {len(all_questions)} question(s)**")
    view_mode = st.radio("Display Format", ["🗂️ Interactive Question Cards", "📋 Data Table"], horizontal=True, key="qb_view_mode")

    if view_mode == "📋 Data Table":
        disp_cols = [
            "id", "source_type", "exam_edition", "exam_year", "subject", "topic",
            "question", "correct_option", "difficulty", "answer_key_status"
        ]
        available_cols = [c for c in disp_cols if c in filtered.columns]
        st.dataframe(filtered[available_cols], use_container_width=True, hide_index=True)
    else:
        # Interactive Question Cards View
        page_size = 10
        total_pages = max(1, (len(filtered) - 1) // page_size + 1)
        cur_page = st.number_input(f"Page (1 to {total_pages})", min_value=1, max_value=total_pages, value=1, step=1)
        start_idx = (cur_page - 1) * page_size
        page_items = filtered.iloc[start_idx : start_idx + page_size]

        for _, q in page_items.iterrows():
            qid = int(q["id"])
            is_pyq = q.get("source_type") == "Official PYQ"
            is_ai = bool(q.get("is_ai_generated"))
            badge_class = "badge-pyq" if is_pyq else ("badge-ai" if is_ai else "badge-sample")
            badge_icon = "🏛️" if is_pyq else ("🤖" if is_ai else "📌")
            badge_text = "Official PYQ" if is_pyq else ("AI Practice" if is_ai else "Sample")

            with st.container(border=True):
                # Header with Provenance & Metadata
                h_col1, h_col2 = st.columns([3, 1])
                with h_col1:
                    prov_info = f"<span class='bpsc-badge {badge_class}'>{badge_icon} {badge_text}</span>"
                    if q.get("exam_edition"):
                        prov_info += f" &nbsp;<b>{q['exam_edition']}</b>"
                    if q.get("exam_year"):
                        prov_info += f" ({q['exam_year']})"
                    if q.get("official_qno") and int(q["official_qno"]) > 0:
                        prov_info += f" · Q.{int(q['official_qno'])}"
                    st.markdown(prov_info, unsafe_allow_html=True)
                with h_col2:
                    diff = q.get("difficulty", "Medium")
                    diff_class = f"badge-difficulty-{diff.lower()}"
                    st.markdown(f"<div style='text-align: right;'><span class='bpsc-badge {diff_class}'>{diff}</span></div>", unsafe_allow_html=True)

                st.caption(f"**Subject:** {q['subject']} &nbsp;|&nbsp; **Topic:** {q['topic']}")
                st.markdown(f"**Q.{qid}: {q['question']}**")

                # Options Grid
                o1, o2 = st.columns(2)
                o1.markdown(f"**A.** {q['option_a']}")
                o1.markdown(f"**B.** {q['option_b']}")
                o2.markdown(f"**C.** {q['option_c']}")
                o2.markdown(f"**D.** {q['option_d']}")

                # Expandable Answer & Explanation
                with st.expander(f"🔑 Reveal Correct Answer & Analysis", expanded=False):
                    st.success(f"**Correct Option:** `{q['correct_option']}`")
                    if q.get("explanation"):
                        st.info(f"**Explanation:** {q['explanation']}")
                    if q.get("distractor_notes"):
                        st.caption(f"**Distractor Trap:** {q['distractor_notes']}")
                    if q.get("concept_tested"):
                        st.caption(f"**Core Concept:** {q['concept_tested']}")

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
            st.download_button(
                "⬇️ Export Attempt History to CSV",
                data=att_csv,
                file_name="bpsc_attempts_export.csv",
                mime="text/csv",
            )


# -----------------------------------------------------------------------------
# Views: 3. AI Question Studio
# -----------------------------------------------------------------------------

SUBJECT_SUGGESTIONS: Dict[str, List[str]] = {
    "General Science": [
        "Cell Biology & Human Physiology",
        "Everyday Physics & Optics",
        "Chemical Reactions & Elements",
        "Human Endocrine & Nervous System",
        "Genetics & Biotechnology",
        "Diseases, Vaccines & Public Health",
    ],
    "Current Affairs": [
        "Bihar State Schemes & Policy Initiatives (Saat Nischay-2, Har Ghar Gangajal)",
        "Bihar Economic Survey & State Budget",
        "National & International Summits (G20, BRICS, COP)",
        "Science, Space & Defence (ISRO, DRDO)",
        "GI Tags & Agriculture Milestones of Bihar",
        "Awards, Sports & Personalities",
    ],
    "Bihar Special": [
        "Freedom Movement in Bihar & Babu Kunwar Singh",
        "Bihar Physiography & River Systems",
        "Geological Formations & Mineral Resources of Bihar",
        "Bihar Panchayati Raj Act 2006",
        "Ancient Magadha & Buddhist/Jain Heritage",
    ],
    "Modern History": [
        "Revolt of 1857 in Bihar",
        "Champaran Satyagraha 1917",
        "Non-Cooperation & Civil Disobedience Movement",
        "Quit India Movement in Bihar",
        "Indian National Congress Sessions (Gaya 1922, Patna)",
    ],
    "Indian Polity": [
        "Fundamental Rights & Constitutional Writs",
        "President, Governor & Executive Powers",
        "Panchayati Raj & Local Self-Government",
        "Supreme Court, High Courts & Judicial Review",
        "Constitutional Amendments & Statutory Commissions",
    ],
    "Economy": [
        "Five Year Plans & NITI Aayog",
        "Inflation, Monetary Policy & RBI",
        "Agriculture, Minimum Support Price & Food Security",
        "Public Finance, Taxation & Fiscal Policy",
        "Bihar Industrial Investment Policies",
    ],
    "Geography": [
        "Drainage System of Bihar & India",
        "Physiographic Divisions & Mountain Passes",
        "Indian Monsoon Climatology",
        "Soils & Agricultural Cropping Seasons",
        "Mineral Belts & Industrial Clusters",
    ],
    "Environment": [
        "National Parks & Tiger Reserves of Bihar & India",
        "Wetlands & Ramsar Sites",
        "Biodiversity Hotspots & Wildlife Conservation",
        "Global Climate Treaties & Environmental Conventions",
    ],
    "Ancient & Medieval History": [
        "Indus Valley & Vedic Period",
        "Rise of Magadha & Mauryan Administration",
        "Buddhist & Jain Councils in Bihar",
        "Gupta Golden Age & Nalanda University",
        "Medieval Sultans & Mughals in Bihar",
    ],
    "Other": [
        "General Studies & CSAT",
    ],
}


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
        suggestions = SUBJECT_SUGGESTIONS.get(subject, ["General Topic"])
        preset_key = f"preset_topic_{subject}"
        chosen_preset = c4.selectbox(
            "Topic Preset (or custom)",
            suggestions + ["Custom Topic..."],
            key=preset_key,
        )
        if chosen_preset == "Custom Topic...":
            topic = c4.text_input("Enter Custom Topic", value="", placeholder="e.g. Endocrine system", key=f"custom_topic_text_{subject}")
            if not topic.strip():
                topic = suggestions[0]
        else:
            topic = chosen_preset

        subtopic = c5.text_input(
            "Subtopic / Theme (Optional)",
            placeholder="e.g. Key mechanisms, dates, or provisions",
            key=f"subtopic_input_{subject}",
        )
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
                    # Clean up all previous studio input keys to avoid stale text bleeding across generations
                    for k in list(st.session_state.keys()):
                        if k.startswith("sq_"):
                            del st.session_state[k]

                    # Increment generation batch ID
                    gen_id = st.session_state.get("studio_gen_id", 0) + 1
                    st.session_state["studio_gen_id"] = gen_id

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
                    st.session_state["studio_subject"] = subject
                    st.session_state["studio_topic"] = topic
                    st.success(f"Generated {len(q_set.questions)} question(s) on '{subject} - {topic}' strictly calibrated against {len(q_set.retrieved_exemplars)} genuine BPSC Prelims PYQs!")
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

        gen_id = st.session_state.get("studio_gen_id", 0)
        questions_to_save: List[Dict[str, Any]] = []
        for i, q in enumerate(studio_items):
            with st.expander(f"Question {i+1}: {q['question'][:80]}...", expanded=True):
                q_text = st.text_area(f"Question #{i+1}", value=q["question"], key=f"sq_text_{gen_id}_{i}")
                o1, o2 = st.columns(2)
                oa = o1.text_input("Option A", value=q["option_a"], key=f"sq_oa_{gen_id}_{i}")
                ob = o2.text_input("Option B", value=q["option_b"], key=f"sq_ob_{gen_id}_{i}")
                oc = o1.text_input("Option C", value=q["option_c"], key=f"sq_oc_{gen_id}_{i}")
                od = o2.text_input("Option D", value=q["option_d"], key=f"sq_od_{gen_id}_{i}")

                curr_idx = ["A", "B", "C", "D"].index(q["correct_option"]) if q["correct_option"] in ["A", "B", "C", "D"] else 0
                correct_opt = st.radio("Correct Answer", ["A", "B", "C", "D"], index=curr_idx, horizontal=True, key=f"sq_cor_{gen_id}_{i}")

                exp_text = st.text_area("Explanation", value=q.get("explanation", ""), key=f"sq_exp_{gen_id}_{i}")
                dist_text = st.text_input("Distractor Notes", value=q.get("distractor_notes", ""), key=f"sq_dist_{gen_id}_{i}")
                concept_tested = st.text_input("Concept Tested", value=q.get("concept_tested", ""), key=f"sq_con_{gen_id}_{i}")

                questions_to_save.append({
                    "exam": exam,
                    "subject": q.get("subject") or subject,
                    "topic": q.get("topic") or topic.strip() or "General",
                    "subtopic": q.get("subtopic") or subtopic.strip(),
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
            for k in list(st.session_state.keys()):
                if k.startswith("sq_"):
                    del st.session_state[k]
            st.rerun()

        if col_clear.button("Discard Set"):
            st.session_state["studio_questions"] = None
            for k in list(st.session_state.keys()):
                if k.startswith("sq_"):
                    del st.session_state[k]
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
        total = len(results["items"])
        correct = sum(1 for r in results["items"] if r["is_correct"])
        incorrect = sum(1 for r in results["items"] if not r["is_correct"] and r["selected_option"] != "-")
        unanswered = sum(1 for r in results["items"] if r["selected_option"] == "-")
        accuracy = round(correct / total * 100) if total > 0 else 0

        # Performance Headline Banner
        if accuracy >= 70:
            st.markdown(
                """
                <div style="background: linear-gradient(135deg, #065f46 0%, #047857 100%); color: white; padding: 18px 24px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(6, 95, 70, 0.2);">
                    <h3 style="color: white; margin: 0 0 4px 0;">🎉 Outstanding Performance!</h3>
                    <p style="margin: 0; color: #d1fae5; font-size: 14px;">Strong conceptual grasp and answer selection. Review distractor traps below for complete mastery.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        elif accuracy >= 50:
            st.markdown(
                """
                <div style="background: linear-gradient(135deg, #1e40af 0%, #1d4ed8 100%); color: white; padding: 18px 24px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(30, 64, 175, 0.2);">
                    <h3 style="color: white; margin: 0 0 4px 0;">👍 Solid Practice Drill!</h3>
                    <p style="margin: 0; color: #dbeafe; font-size: 14px;">Good effort. Pay close attention to nuanced distractors and statement elimination below.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div style="background: linear-gradient(135deg, #991b1b 0%, #b91c1c 100%); color: white; padding: 18px 24px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(153, 27, 27, 0.2);">
                    <h3 style="color: white; margin: 0 0 4px 0;">⚠️ Targeted Remediation Needed</h3>
                    <p style="margin: 0; color: #fee2e2; font-size: 14px;">Conceptual gaps detected. Use the 'Explain My Mistake with AI Tutor' button on missed questions below.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        sc1, sc2, sc3, sc4, sc5 = st.columns(5)
        sc1.metric("Net Score", f"{results['total_score']:.2f}", help="With official negative marking penalty applied")
        sc2.metric("Accuracy", f"{accuracy}%")
        sc3.metric("✅ Correct", correct)
        sc4.metric("❌ Incorrect", incorrect)
        sc5.metric("⚠️ Unanswered", unanswered)

        st.caption(f"⏱️ Time spent: {results.get('time_spent', 0):.1f} seconds ({round(results.get('time_spent', 0) / max(1, total), 1)}s per question)")
        st.divider()

        # Detailed Review per Question
        st.subheader("Question-by-Question Review & Distractor Analysis")
        for idx, res in enumerate(results["items"], start=1):
            if res["is_correct"]:
                status = "✅ Correct (+1.0)"
            elif res["selected_option"] == "-":
                status = "⚠️ Skipped (0.0)"
            else:
                status = "❌ Incorrect"

            with st.expander(f"{status} | Q.{idx}: {res['question'][:80]}...", expanded=not res["is_correct"]):
                st.markdown(f"**Question {idx}: {res['question']}**")
                st.caption(f"**Subject:** {res['subject']} &nbsp;|&nbsp; **Topic:** {res['topic']}")

                col_ans1, col_ans2 = st.columns(2)
                with col_ans1:
                    ans_color = "#166534" if res["is_correct"] else "#991b1b"
                    st.markdown(f"<div style='padding: 8px 12px; background: rgba(248, 250, 252, 0.8); border-radius: 8px;'><b>Your Selection:</b> <span style='color: {ans_color}; font-weight: 700;'>{res['selected_option']}. {res['selected_text']}</span></div>", unsafe_allow_html=True)
                with col_ans2:
                    st.markdown(f"<div style='padding: 8px 12px; background: rgba(240, 253, 244, 0.8); border: 1px solid #bbf7d0; border-radius: 8px;'><b>Official Key:</b> <span style='color: #166534; font-weight: 700;'>{res['correct_option']}. {res['correct_text']}</span></div>", unsafe_allow_html=True)

                st.write("")
                if res.get("explanation"):
                    st.info(f"💡 **Detailed Explanation:**\n\n{res['explanation']}")
                if res.get("distractor_notes"):
                    st.warning(f"⚠️ **Distractor Trap Analysis:**\n\n{res['distractor_notes']}")

                # Action: Explain My Mistake with AI Tutor
                if not res["is_correct"] and config.is_gemini_configured():
                    if st.button(f"🔍 Explain My Mistake with AI Tutor", key=f"tutor_ask_{idx}"):
                        st.session_state["tutor_context_question"] = res
                        st.session_state["nav_page"] = "AI Study Tutor"
                        st.rerun()

        st.write("")
        c_btn1, c_btn2 = st.columns([1, 2])
        if c_btn1.button("Start Another Test", type="primary", use_container_width=True):
            st.session_state["test_results"] = None
            st.session_state["active_test"] = None
            st.rerun()
        if c_btn2.button("Review Mistakes in Error Notebook", use_container_width=True):
            st.session_state["test_results"] = None
            st.session_state["active_test"] = None
            st.session_state["nav_page"] = "Error Notebook"
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

        st.caption(f"🎯 **{len(matching_ids)} question(s)** available matching this criteria.")

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

        if st.button("🚀 Start Test", type="primary", use_container_width=True):
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
        total_q = len(q_frame)

        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%); color: white; padding: 14px 20px; border-radius: 12px; margin-bottom: 20px;">
                <span style="font-size: 13px; font-weight: 700; color: #fbbf24; text-transform: uppercase;">Active Session · {active_test['test_mode']}</span>
                <h3 style="color: white; margin: 4px 0 0 0;">Exam Drill in Progress · {total_q} Questions</h3>
                <span style="font-size: 12px; color: #cbd5e1;">Negative Marking: -{active_test['negative_rate']} per incorrect answer</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        answers: Dict[int, str] = {}
        confidences: Dict[int, str] = {}

        with st.form("active_test_form"):
            for i, row in q_frame.iterrows():
                qid = int(row["id"])
                is_pyq = row.get("source_type") == "Official PYQ"
                badge_text = f"🏛️ Official PYQ ({row.get('exam_edition', '')})" if is_pyq else "🤖 Practice MCQ"

                st.markdown(f"#### Question {i + 1} of {total_q}")
                st.caption(f"{badge_text} &nbsp;|&nbsp; **Subject:** {row['subject']} &nbsp;|&nbsp; **Topic:** {row['topic']} &nbsp;|&nbsp; Difficulty: `{row['difficulty']}`")
                st.markdown(f"**{row['question']}**")

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

            submitted = st.form_submit_button("Submit Test & View Full Analysis", type="primary", use_container_width=True)

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

CURATED_CURRENT_AFFAIRS_CAPSULES = [
    {
        "title": "🏆 Bharat Ratna 2024 to Jan Nayak Karpoori Thakur",
        "category": "Awards & Personalities",
        "topic": "Karpoori Thakur Bharat Ratna 2024",
        "summary": "Former Bihar Chief Minister Karpoori Thakur was posthumously awarded the Bharat Ratna (India's highest civilian award) in January 2024 on his centenary birth anniversary. Known as 'Jan Nayak' (People's Hero), he served as Bihar Chief Minister twice (1970-71 and 1977-79). He was a pioneer in implementing the Mungeri Lal Commission recommendations in 1978, which introduced the Karpoori Thakur Formula creating sub-quotas for Extremely Backward Classes (EBCs), backward women, and economically weaker sections decades before central implementations.",
        "key_facts": [
            "Centenary birth anniversary: 24 January 2024.",
            "Served as Bihar Chief Minister twice (December 1970 – June 1971; June 1977 – April 1979).",
            "Pioneered the 'Karpoori Thakur Formula' in 1978 based on the Mungeri Lal Commission report.",
            "Abolished English as a compulsory requirement for matriculation exams in Bihar to benefit rural students.",
        ],
    },
    {
        "title": "📊 Bihar Caste-Based Survey 2023 (Findings & Socio-Economic Report)",
        "category": "State Demographics & Policy",
        "topic": "Bihar Caste Survey 2023",
        "summary": "Bihar became the first state in post-independence India to conduct and release a comprehensive caste-based enumeration and socio-economic survey in October 2023. The total enumerated population of Bihar is 13,07,25,310 (13.07 crore). Extremely Backward Classes (EBCs) constitute 36.01%, Other Backward Classes (OBCs) 27.13%, Scheduled Castes (SC) 19.65%, Scheduled Tribes (ST) 1.68%, and General Category (Unreserved) 15.52%. The findings led to the enactment of the Bihar Reservation of Vacancies in Posts and Services (Amendment) Act, 2023.",
        "key_facts": [
            "Total Population: 13,07,25,310 (13.07 crore).",
            "Social Categories: EBC (36.01%), OBC (27.13%), SC (19.65%), ST (1.68%), General (15.52%).",
            "Religious Breakdown: Hindu (81.99%), Muslim (17.70%), Christian (0.05%), Sikh (0.01%).",
            "Poverty & Livelihood: 34.13% of all families in Bihar (94 lakh families) earn less than ₹6,000 per month.",
        ],
    },
    {
        "title": "🌾 GI Tags of Bihar (Mircha Rice & Agri-Products)",
        "category": "GI Tags & Agriculture",
        "topic": "GI Tags of Bihar",
        "summary": "Bihar holds prestigious Geographical Indication (GI) tags for distinct agricultural and confectionery products. In 2023, 'Mircha Rice' (Marcha Dhan) of West Champaran district received the GI tag for its distinct aroma, black pepper-like appearance, and flaking qualities. Previous celebrated GI tagged items include Mithila Makhana (Fox nut), Shahi Litchi of Muzaffarpur, Zardalu Mango of Bhagalpur, Katarni Rice of Bhagalpur/Banka, Magahi Paan of Magadh, and Silao Khaja of Nalanda.",
        "key_facts": [
            "Mircha Rice (Marcha Chawal): West Champaran (Mainatand, Gaunaha, Narkatiaganj).",
            "Mithila Makhana: Awarded GI tag in 2022 under Agriculture class.",
            "Shahi Litchi: Muzaffarpur, Vaishali, Samastipur; registered in 2018.",
            "Zardalu Mango & Katarni Rice: Bhagalpur and Banka districts.",
            "Magahi Paan: Nawada, Aurangabad, Gaya, and Nalanda.",
        ],
    },
    {
        "title": "💧 Har Ghar Gangajal Project (Gangajal Aapurti Yojana)",
        "category": "Bihar Infrastructure & Schemes",
        "topic": "Har Ghar Gangajal Project",
        "summary": "Under the Jal-Jeevan-Hariyali campaign, the Government of Bihar launched the pioneering 'Gangajal Aapurti Yojana' (Har Ghar Gangajal) in November 2022. It lifts surplus floodwaters of the Ganga river during the four monsoon months from Hathidah (Mokama) and transports it through a 151-km pipeline network to provide clean treated drinking water to water-stressed southern heritage cities: Rajgir, Gaya, Bodh Gaya, and Nawada.",
        "key_facts": [
            "Inaugurated by Chief Minister Nitish Kumar at Rajgir (November 2022).",
            "Beneficiary Cities: Rajgir, Gaya, Bodh Gaya, and Nawada.",
            "Source: Hathidah (Patna district) via 151-km underground pipeline.",
            "Water storage reservoirs built at Tetar (Gaya), Ghoda Katora (Rajgir).",
        ],
    },
    {
        "title": "🌱 Saat Nischay-2 (2020–2025) Key Targets",
        "category": "Bihar Development Agenda",
        "topic": "Saat Nischay-2",
        "summary": "The Government of Bihar launched the second phase of Seven Resolves (Saat Nischay-2) for the period 2020–2025 to achieve inclusive good governance and sustainable growth. The 7 core components are: 1. Yuva Shakti - Bihar ki Pragati; 2. Sashakt Mahila - Saksham Mahila; 3. Har Khet Tak Sinchai Ka Pani; 4. Swachh Gaon - Samriddh Gaon; 5. Swachh Shahar - Viksit Shahar; 6. Sulabh Samparkata; 7. Sabke Liye Atirikt Swasthya Suvidha.",
        "key_facts": [
            "Yuva Shakti: Mega skill centers in all 38 districts, Bihar Skill Development Mission.",
            "Sashakt Mahila: Financial assistance for intermediate and graduate pass unmarried girls; Mukhyamantri Mahila Udyami Yojana.",
            "Har Khet Tak Sinchai: Irrigation water access for every agricultural field.",
            "Swachh Shahar / Gaon: Solid waste management, solar street lights in all wards.",
        ],
    },
    {
        "title": "🐅 Wildlife & Environment: Valmiki & Proposed Kaimur Tiger Reserve",
        "category": "Environment & Biodiversity",
        "topic": "Valmiki & Kaimur Tiger Reserves",
        "summary": "Valmiki National Park & Tiger Reserve in West Champaran is currently the only declared tiger reserve in Bihar, reporting a rising tiger population (54 tigers in recent census). In 2023-2024, the state government constituted a Rhino Task Force to reintroduce one-horned rhinoceroses in Valmiki Tiger Reserve under the National Rhino Conservation Strategy. Additionally, the National Tiger Conservation Authority (NTCA) approved Kaimur Wildlife Sanctuary to be declared Bihar's second tiger reserve.",
        "key_facts": [
            "Valmiki Tiger Reserve: West Champaran, contiguous with Chitwan National Park (Nepal).",
            "Second Tiger Reserve: Proposed in Kaimur Wildlife Sanctuary (spanning Kaimur & Rohtas).",
            "Rhino Task Force: Set up to reintroduce rhinos in VTR.",
            "Gharial breeding sanctuary: Gandak River stretch in Bihar.",
        ],
    },
]


def show_current_affairs() -> None:
    """Dedicated Current Affairs Hub: Instant MCQ generation, real-time research, and high-yield BPSC capsules."""
    st.title("📰 Current Affairs & News Lab")
    st.write(
        "Master high-yield National, International, and Bihar Current Affairs for BPSC CCE and UPSC Prelims. "
        "Generate multi-statement practice MCQs, synthesize live policy developments with Google search grounding, and revise high-yield capsules."
    )

    if not config.is_gemini_configured():
        st.warning("⚠️ Gemini API is not configured. Please add `GEMINI_API_KEY` to enable current affairs synthesis.")
        return

    tab1, tab2, tab3 = st.tabs([
        "⚡ Instant Current Affairs MCQs",
        "🔍 Live Policy & Topic Research",
        "📌 High-Yield BPSC Capsules",
    ])

    # ---------------------------------------------------------
    # TAB 1: Instant Current Affairs MCQ Studio
    # ---------------------------------------------------------
    with tab1:
        st.subheader("Generate BPSC Current Affairs Practice Sets")
        st.write("Current Affairs accounts for 25–30 questions in BPSC Prelims. Generate targeted questions matching recent exam patterns.")

        c_ca1, c_ca2, c_ca3 = st.columns(3)
        ca_category = c_ca1.selectbox(
            "Current Affairs Theme",
            [
                "Bihar State Schemes & Policy Initiatives (Saat Nischay-2, Har Ghar Gangajal)",
                "Bihar Economic Survey & State Budget Highlights",
                "National & International Summits (G20, BRICS, COP)",
                "Science, Space & Defence (ISRO, DRDO)",
                "GI Tags & Agriculture Milestones of Bihar",
                "Awards, Honors, Sports & Personalities",
                "National Appointments & Constitutional Commissions",
            ],
            index=0,
            key="ca_theme_select",
        )
        ca_qtype = c_ca2.selectbox(
            "Question Style",
            ["Statement-based (1 and 2 only, etc.)", "Standard MCQ", "Matching Columns"],
            index=0,
            key="ca_qtype_select",
        )
        ca_count = c_ca3.slider("Number of Questions", min_value=1, max_value=10, value=3, key="ca_count_slider")

        c_ca4, c_ca5 = st.columns(2)
        ca_diff = c_ca4.selectbox("Difficulty", ["Medium", "Hard"], index=0, key="ca_diff_select")
        ca_timeframe = c_ca5.selectbox("Timeframe Focus", ["Last 6 Months (BPSC High-Yield)", "Last 1 Year", "Recent State Initiatives"], key="ca_time_select")

        # Show available official PYQ exemplars
        ca_exemplars = db.retrieve_pyq_exemplars(subject="Current Affairs", topic=ca_category[:20], limit=2)
        if ca_exemplars:
            st.caption(f"🏛️ Strict BPSC Benchmark Active: Will calibrate against {len(ca_exemplars)} genuine Current Affairs PYQs from 68th/69th BPSC Prelims.")

        if st.button("⚡ Generate Current Affairs Questions", type="primary", key="btn_gen_ca"):
            with st.spinner("Generating authenticated Current Affairs questions..."):
                try:
                    for k in list(st.session_state.keys()):
                        if k.startswith("ca_sq_"):
                            del st.session_state[k]
                    gen_id = st.session_state.get("ca_gen_id", 0) + 1
                    st.session_state["ca_gen_id"] = gen_id

                    q_set = ai_service.generate_question_set(
                        exam="BPSC",
                        subject="Current Affairs",
                        topic=ca_category,
                        subtopic=ca_timeframe,
                        count=ca_count,
                        difficulty=ca_diff,
                        question_type=ca_qtype,
                        focus="Tricky distractor elimination",
                        notes_or_context=f"Focus on recent verified civil services developments relevant for BPSC Prelims: {ca_timeframe}.",
                    )
                    st.session_state["ca_questions"] = [q.model_dump() for q in q_set.questions]
                    st.session_state["ca_exemplars"] = q_set.retrieved_exemplars
                    st.success(f"Generated {len(q_set.questions)} Current Affairs question(s) successfully!")
                except Exception as exc:
                    st.error(f"Generation failed: {exc}")

        # Render generated CA questions
        ca_items = st.session_state.get("ca_questions")
        if ca_items:
            st.divider()
            st.subheader(f"Review & Save Generated Current Affairs Questions ({len(ca_items)})")
            ca_gen_id = st.session_state.get("ca_gen_id", 0)
            ca_to_save: List[Dict[str, Any]] = []

            for idx, q in enumerate(ca_items):
                with st.expander(f"Question #{idx+1}: {q['question'][:80]}...", expanded=True):
                    q_text = st.text_area(f"Question Statement", value=q["question"], key=f"ca_sq_text_{ca_gen_id}_{idx}")
                    co1, co2 = st.columns(2)
                    oa = co1.text_input("Option A", value=q["option_a"], key=f"ca_sq_oa_{ca_gen_id}_{idx}")
                    ob = co2.text_input("Option B", value=q["option_b"], key=f"ca_sq_ob_{ca_gen_id}_{idx}")
                    oc = co1.text_input("Option C", value=q["option_c"], key=f"ca_sq_oc_{ca_gen_id}_{idx}")
                    od = co2.text_input("Option D", value=q["option_d"], key=f"ca_sq_od_{ca_gen_id}_{idx}")

                    curr_idx = ["A", "B", "C", "D"].index(q["correct_option"]) if q["correct_option"] in ["A", "B", "C", "D"] else 0
                    cor_opt = st.radio("Correct Answer", ["A", "B", "C", "D"], index=curr_idx, horizontal=True, key=f"ca_sq_cor_{ca_gen_id}_{idx}")
                    exp = st.text_area("Explanation", value=q.get("explanation", ""), key=f"ca_sq_exp_{ca_gen_id}_{idx}")
                    dist = st.text_input("Distractor Notes", value=q.get("distractor_notes", ""), key=f"ca_sq_dist_{ca_gen_id}_{idx}")

                    ca_to_save.append({
                        "exam": "BPSC",
                        "subject": "Current Affairs",
                        "topic": q.get("topic") or ca_category,
                        "subtopic": ca_timeframe,
                        "question": q_text.strip(),
                        "option_a": oa.strip(),
                        "option_b": ob.strip(),
                        "option_c": oc.strip(),
                        "option_d": od.strip(),
                        "correct_option": cor_opt,
                        "explanation": exp.strip(),
                        "distractor_notes": dist.strip(),
                        "concept_tested": q.get("concept_tested", "Current Affairs"),
                        "question_type": ca_qtype,
                        "source_type": "AI-generated",
                        "source_name": "Current Affairs Lab",
                        "source_url": "",
                        "difficulty": ca_diff,
                        "is_ai_generated": 1,
                    })

            col_s, col_d = st.columns([2, 1])
            if col_s.button("💾 Save All to Question Bank", type="primary", key="save_ca_bank"):
                cnt = 0
                for item in ca_to_save:
                    db.add_question(item)
                    cnt += 1
                st.success(f"Saved {cnt} Current Affairs questions to your Question Bank!")
                st.session_state["ca_questions"] = None
                for k in list(st.session_state.keys()):
                    if k.startswith("ca_sq_"):
                        del st.session_state[k]
                st.rerun()

            if col_d.button("Discard Set", key="discard_ca_bank"):
                st.session_state["ca_questions"] = None
                for k in list(st.session_state.keys()):
                    if k.startswith("ca_sq_"):
                        del st.session_state[k]
                st.rerun()

    # ---------------------------------------------------------
    # TAB 2: Live Policy & Topic Research
    # ---------------------------------------------------------
    with tab2:
        st.subheader("Live Policy Research with Google Search Grounding")
        st.write("Research any recent government announcement, scheme, or event to get high-yield exam points with verified source citations.")

        col_rq1, col_rq2 = st.columns([3, 1])
        q_text = col_rq1.text_input(
            "Enter policy, scheme, or current event",
            value="Bihar Industrial Investment Promotion Policy and IT Policy 2024",
            key="ca_research_input",
        )
        bihar_angle = col_rq2.checkbox("Include Bihar angle & state budget", value=True, key="ca_bihar_check")

        if st.button("🔍 Research & Ground with Citations", type="primary", key="btn_ca_research"):
            with st.spinner("Retrieving verified facts and citations..."):
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
            st.divider()
            st.subheader(f"Synthesis: {res['topic']}")
            st.markdown(res["text"])

            if res["citations"]:
                st.markdown("#### 🔗 Retrieved Sources & Grounding Citations")
                for c in res["citations"]:
                    st.markdown(f"- [{c['title']}]({c['url']})")

            c_save, c_gen = st.columns(2)
            if c_save.button("💾 Save Research Notes", key="save_res_btn"):
                db.save_research_note(
                    topic=res["topic"],
                    title=res["topic"],
                    summary=res["text"],
                    key_facts=[],
                    bihar_angle="Included" if bihar_angle else "",
                )
                st.success("Saved to Research Notes!")

            if c_gen.button("✨ Generate 3 MCQs from this Research", key="gen_from_res_btn"):
                with st.spinner("Generating exam MCQs from research notes..."):
                    try:
                        q_set = ai_service.generate_question_set(
                            exam="BPSC",
                            subject="Current Affairs",
                            topic=res["topic"],
                            subtopic="Research Note Synthesis",
                            count=3,
                            difficulty="Medium",
                            question_type="Statement-based (1 and 2 only, etc.)",
                            focus="PYQ-inspired practice",
                            notes_or_context=res["text"],
                        )
                        st.session_state["ca_questions"] = [q.model_dump() for q in q_set.questions]
                        st.session_state["ca_exemplars"] = q_set.retrieved_exemplars
                        st.success("Generated 3 questions! Check the 'Instant Current Affairs MCQs' tab to review and save them.")
                    except Exception as exc:
                        st.error(f"Generation error: {exc}")

    # ---------------------------------------------------------
    # TAB 3: High-Yield BPSC Capsules (Ready Bank)
    # ---------------------------------------------------------
    with tab3:
        st.subheader("High-Yield BPSC Current Affairs Capsules")
        st.write("Curated, syllabus-linked facts on the highest-yield topics for the upcoming 71st BPSC CCE Prelims.")

        for cap in CURATED_CURRENT_AFFAIRS_CAPSULES:
            with st.expander(f"{cap['title']} · *{cap['category']}*", expanded=False):
                st.markdown(f"**Executive Summary:** {cap['summary']}")
                st.markdown("**Key Examination Facts to Remember:**")
                for fact in cap["key_facts"]:
                    st.markdown(f"- {fact}")

                if st.button(f"🎯 Generate 3 Questions on: {cap['topic']}", key=f"btn_cap_{cap['topic']}"):
                    with st.spinner(f"Generating questions on {cap['topic']}..."):
                        try:
                            context_str = cap["summary"] + "\nKey Facts:\n" + "\n".join(cap["key_facts"])
                            q_set = ai_service.generate_question_set(
                                exam="BPSC",
                                subject="Current Affairs",
                                topic=cap["topic"],
                                subtopic=cap["category"],
                                count=3,
                                difficulty="Hard",
                                question_type="Statement-based (1 and 2 only, etc.)",
                                focus="Tricky distractor elimination",
                                notes_or_context=context_str,
                            )
                            st.session_state["ca_questions"] = [q.model_dump() for q in q_set.questions]
                            st.session_state["ca_exemplars"] = q_set.retrieved_exemplars
                            st.success(f"Generated 3 questions on {cap['topic']}! Switch to 'Instant Current Affairs MCQs' tab to review and save.")
                        except Exception as exc:
                            st.error(f"Generation error: {exc}")


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
    inject_custom_css()
    init_session_state()

    # Sidebar Navigation & Branding Header
    st.sidebar.markdown(
        f"""
        <div class="sidebar-brand-card">
            <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #fbbf24; font-weight: 700;">Government Examination Lab</div>
            <div style="font-size: 18px; font-weight: 800; margin: 4px 0;">🏛️ BPSC QUESTION LAB</div>
            <div style="font-size: 12px; color: #cbd5e1;">v{APP_VERSION} · BPSC CCE & UPSC</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    pages = [
        "Dashboard",
        "Question Bank",
        "AI Question Studio",
        "Current Affairs Lab",
        "Practice & Mock Tests",
        "AI Study Tutor",
        "AI Performance Coach",
        "Error Notebook",
        "Revision Planner",
        "Settings & Data",
    ]

    # Handle programmatic redirects
    default_page = st.session_state.get("nav_page", "Dashboard")
    if default_page not in pages:
        default_page = "Dashboard"

    selected_page = st.sidebar.radio("Navigate", pages, index=pages.index(default_page))
    st.session_state["nav_page"] = selected_page

    st.sidebar.markdown(
        """
        <div class="sidebar-target-box">
            <b style="color: #1e3a8a;">🎯 Target: 71st BPSC Prelims</b><br>
            <span style="font-size: 12px; color: #475569;">
            • 150 MCQs · 120 Mins · Negative: -0.33<br>
            • Focus: Bihar History, Geography, Polity, Science, Current Affairs
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Route to selected page
    if selected_page == "Dashboard":
        show_dashboard()
    elif selected_page == "Question Bank":
        show_question_bank()
    elif selected_page == "AI Question Studio":
        show_question_studio()
    elif selected_page in ["Current Affairs Lab", "Current Affairs & Sources"]:
        show_current_affairs()
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
    elif selected_page == "Settings & Data":
        show_settings()


if __name__ == "__main__":
    main()
