"""BPSC Question Lab v2.0 - AI-Powered Exam Preparation Platform.

An adaptive, evidence-based study and revision environment for BPSC CCE & UPSC Prelims.
Integrates official Google Gemini SDK, deterministic analytics, metacognitive calibration,
adaptive spaced repetition, interactive OMR mock engine, and Supabase cloud compatibility.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
import importlib

import ai_service
import analytics
import config
import db
import ocr_engine
import pdf_extractor
import revision_engine
import schemas
import supabase_client

# Force-reload local modules to guarantee Streamlit hot-reloading captures newly pulled modules
try:
    importlib.reload(db)
    importlib.reload(analytics)
    importlib.reload(config)
    importlib.reload(ai_service)
    importlib.reload(ocr_engine)
    importlib.reload(pdf_extractor)
    importlib.reload(revision_engine)
    importlib.reload(schemas)
except Exception:
    pass

# Defensive runtime fallbacks on db module to prevent AttributeError if Streamlit daemon cached an older module object
if not hasattr(db, "count_questions"):
    def _fallback_count_questions(source_type: str = "All", conn_factory: Any = None) -> int:
        connector = conn_factory or db.connect_db
        with connector() as conn:
            if source_type != "All":
                row = conn.execute("SELECT COUNT(*) FROM questions WHERE source_type = ?", (source_type,)).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM questions").fetchone()
            return int(row[0]) if row else 0
    db.count_questions = _fallback_count_questions

if not hasattr(db, "get_question_bank_summary"):
    def _fallback_get_question_bank_summary(conn_factory: Any = None) -> Dict[str, Any]:
        connector = conn_factory or db.connect_db
        try:
            with connector() as conn:
                total = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
                pyq = conn.execute("SELECT COUNT(*) FROM questions WHERE source_type = 'Official PYQ'").fetchone()[0]
                mock = conn.execute("SELECT COUNT(*) FROM questions WHERE source_type = 'Mock question'").fetchone()[0]
                ai = conn.execute("SELECT COUNT(*) FROM questions WHERE source_type = 'AI-generated'").fetchone()[0]
                sample = conn.execute("SELECT COUNT(*) FROM questions WHERE source_type = 'Built-in sample'").fetchone()[0]
                subjs = conn.execute("SELECT COUNT(DISTINCT subject) FROM questions WHERE subject != ''").fetchone()[0]
                sources = conn.execute("SELECT COUNT(DISTINCT source_name) FROM questions WHERE source_name != ''").fetchone()[0]
                return {
                    "total_questions": int(total),
                    "pyq_count": int(pyq),
                    "mock_count": int(mock),
                    "ai_count": int(ai),
                    "sample_count": int(sample),
                    "distinct_subjects": int(subjs),
                    "distinct_sources": int(sources),
                }
        except Exception:
            return {"total_questions": 0, "pyq_count": 0, "mock_count": 0, "ai_count": 0, "sample_count": 0, "distinct_subjects": 0, "distinct_sources": 0}
    db.get_question_bank_summary = _fallback_get_question_bank_summary

if not hasattr(db, "get_distinct_subjects"):
    def _fallback_get_distinct_subjects(exam: str = "All", source_type: str = "All", conn_factory: Any = None) -> List[str]:
        connector = conn_factory or db.connect_db
        query = "SELECT DISTINCT subject FROM questions WHERE subject != ''"
        params: List[Any] = []
        if exam != "All":
            query += " AND exam IN (?, 'Both')"
            params.append(exam)
        if source_type != "All":
            query += " AND source_type = ?"
            params.append(source_type)
        query += " ORDER BY subject"
        with connector() as conn:
            rows = conn.execute(query, params).fetchall()
            return [r[0] for r in rows if r[0]]
    db.get_distinct_subjects = _fallback_get_distinct_subjects

if not hasattr(db, "get_distinct_topics"):
    def _fallback_get_distinct_topics(subject: Optional[str] = None, exam: str = "All", source_type: str = "All", conn_factory: Any = None) -> List[str]:
        connector = conn_factory or db.connect_db
        query = "SELECT DISTINCT topic FROM questions WHERE topic != ''"
        params: List[Any] = []
        if subject and subject != "All":
            query += " AND subject = ?"
            params.append(subject)
        if exam != "All":
            query += " AND exam IN (?, 'Both')"
            params.append(exam)
        if source_type != "All":
            query += " AND source_type = ?"
            params.append(source_type)
        query += " ORDER BY topic"
        with connector() as conn:
            rows = conn.execute(query, params).fetchall()
            return [r[0] for r in rows if r[0]]
    db.get_distinct_topics = _fallback_get_distinct_topics

if not hasattr(db, "get_distinct_editions"):
    def _fallback_get_distinct_editions(source_type: str = "All", conn_factory: Any = None) -> List[str]:
        connector = conn_factory or db.connect_db
        with connector() as conn:
            if source_type != "All":
                rows = conn.execute("SELECT DISTINCT exam_edition FROM questions WHERE source_type = ? AND exam_edition != '' ORDER BY exam_edition", (source_type,)).fetchall()
            else:
                rows = conn.execute("SELECT DISTINCT exam_edition FROM questions WHERE exam_edition != '' ORDER BY exam_edition").fetchall()
            return [r[0] for r in rows if r[0]]
    db.get_distinct_editions = _fallback_get_distinct_editions

if not hasattr(db, "get_subject_counts"):
    def _fallback_get_subject_counts(source_type: str = "All", conn_factory: Any = None) -> Dict[str, int]:
        connector = conn_factory or db.connect_db
        with connector() as conn:
            if source_type != "All":
                rows = conn.execute("SELECT subject, COUNT(*) FROM questions WHERE source_type = ? GROUP BY subject ORDER BY COUNT(*) DESC", (source_type,)).fetchall()
            else:
                rows = conn.execute("SELECT subject, COUNT(*) FROM questions GROUP BY subject ORDER BY COUNT(*) DESC").fetchall()
            return {r[0]: int(r[1]) for r in rows if r[0]}
    db.get_subject_counts = _fallback_get_subject_counts

if not hasattr(db, "get_difficulty_counts"):
    def _fallback_get_difficulty_counts(source_type: str = "All", conn_factory: Any = None) -> Dict[str, int]:
        connector = conn_factory or db.connect_db
        with connector() as conn:
            if source_type != "All":
                rows = conn.execute("SELECT difficulty, COUNT(*) FROM questions WHERE source_type = ? GROUP BY difficulty", (source_type,)).fetchall()
            else:
                rows = conn.execute("SELECT difficulty, COUNT(*) FROM questions GROUP BY difficulty").fetchall()
            return {r[0]: int(r[1]) for r in rows if r[0]}
    db.get_difficulty_counts = _fallback_get_difficulty_counts

if not hasattr(db, "get_pinned_question_ids"):
    def _fallback_get_pinned_question_ids() -> Set[int]:
        with db.connect_db() as conn:
            rows = conn.execute("SELECT question_id FROM pinned_notebook").fetchall()
            return {int(r["question_id"]) for r in rows}
    db.get_pinned_question_ids = _fallback_get_pinned_question_ids

if not hasattr(db, "get_pinned_questions_df"):
    def _fallback_get_pinned_questions_df(conn_factory: Any = None) -> pd.DataFrame:
        connector = conn_factory or db.connect_db
        with connector() as conn:
            return pd.read_sql_query("""
                SELECT q.*, p.pinned_at, p.note as pin_notes
                FROM questions q
                JOIN pinned_notebook p ON q.id = p.question_id
                ORDER BY p.pinned_at DESC
            """, conn)
    db.get_pinned_questions_df = _fallback_get_pinned_questions_df

APP_VERSION = "2.0.0"

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

NAV_PAGES = [
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


# -----------------------------------------------------------------------------
# Custom UI Styling & Helper Utilities
# -----------------------------------------------------------------------------

def inject_custom_css() -> None:
    """Inject modern, responsive CSS styling for cards, badges, and OMR palette."""
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400;1,600&family=Outfit:wght@500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

    /* Global Typography & Smoothing */
    html, body, [class*="css"], .stApp {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif !important;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }

    h1, h2, h3, h4, h5, h6 {
        font-family: 'Outfit', 'Plus Jakarta Sans', sans-serif !important;
        letter-spacing: -0.02em !important;
        font-weight: 700 !important;
    }

    code, kbd, samp, pre {
        font-family: 'JetBrains Mono', monospace !important;
    }

    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 3.5rem;
        max-width: 1250px;
    }

    /* Custom Sleek Scrollbar */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    ::-webkit-scrollbar-track {
        background: transparent;
    }
    ::-webkit-scrollbar-thumb {
        background: rgba(148, 163, 184, 0.35);
        border-radius: 999px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(148, 163, 184, 0.6);
    }

    /* Breathtaking Hero Banner */
    .bpsc-hero {
        background: radial-gradient(circle at 10% 20%, rgba(99, 102, 241, 0.22) 0%, transparent 45%),
                    radial-gradient(circle at 90% 80%, rgba(245, 158, 11, 0.18) 0%, transparent 45%),
                    linear-gradient(135deg, #090d16 0%, #0f172a 45%, #1e1b4b 100%);
        color: #ffffff;
        padding: 28px 32px;
        border-radius: 20px;
        margin-bottom: 24px;
        border: 1px solid rgba(255, 255, 255, 0.12);
        box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.15);
        position: relative;
        overflow: hidden;
    }

    .bpsc-hero::after {
        content: "";
        position: absolute;
        top: 0;
        right: 0;
        bottom: 0;
        left: 0;
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.03) 0%, transparent 100%);
        pointer-events: none;
    }

    .bpsc-hero-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: linear-gradient(135deg, rgba(245, 158, 11, 0.22) 0%, rgba(217, 119, 6, 0.12) 100%);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.45);
        padding: 5px 14px;
        border-radius: 9999px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.6px;
        text-transform: uppercase;
        margin-bottom: 10px;
        box-shadow: 0 0 14px rgba(245, 158, 11, 0.18);
    }

    .bpsc-hero-title {
        color: #ffffff;
        margin: 8px 0 6px 0;
        font-size: 28px;
        font-weight: 800;
        letter-spacing: -0.025em;
        background: linear-gradient(135deg, #ffffff 40%, #cbd5e1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .bpsc-hero-desc {
        color: #cbd5e1;
        margin: 0;
        font-size: 14.5px;
        line-height: 1.55;
        max-width: 900px;
    }

    .bpsc-hero-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 16px;
    }

    .bpsc-hero-chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(255, 255, 255, 0.08);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.15);
        color: #e2e8f0;
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
    }

    /* Glassmorphism KPI Metrics */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0.02) 100%);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border: 1px solid rgba(255, 255, 255, 0.09);
        border-radius: 16px;
        padding: 18px 20px;
        position: relative;
        overflow: hidden;
        transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.07);
    }

    [data-testid="stMetric"]::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #6366f1, #8b5cf6, #3b82f6);
        opacity: 0.8;
        transition: height 0.25s ease, opacity 0.25s ease;
    }

    [data-testid="stMetric"]:hover {
        transform: translateY(-3px);
        border-color: rgba(99, 102, 241, 0.4);
        box-shadow: 0 14px 28px -6px rgba(99, 102, 241, 0.2);
    }

    [data-testid="stMetric"]:hover::before {
        height: 4px;
        opacity: 1;
    }

    [data-testid="stMetricLabel"] {
        font-size: 0.78rem !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.06em !important;
        opacity: 0.85 !important;
    }

    [data-testid="stMetricValue"] {
        font-family: 'Outfit', sans-serif !important;
        font-size: 1.85rem !important;
        font-weight: 800 !important;
        letter-spacing: -0.025em !important;
    }

    /* Specific Accent Colors for Dashboard Metrics */
    [data-testid="column"]:nth-child(1) [data-testid="stMetric"]::before {
        background: linear-gradient(90deg, #3b82f6, #06b6d4);
    }
    [data-testid="column"]:nth-child(2) [data-testid="stMetric"]::before {
        background: linear-gradient(90deg, #8b5cf6, #d946ef);
    }
    [data-testid="column"]:nth-child(3) [data-testid="stMetric"]::before {
        background: linear-gradient(90deg, #6366f1, #3b82f6);
    }
    [data-testid="column"]:nth-child(4) [data-testid="stMetric"]::before {
        background: linear-gradient(90deg, #10b981, #14b8a6);
    }
    [data-testid="column"]:nth-child(5) [data-testid="stMetric"]::before {
        background: linear-gradient(90deg, #f59e0b, #f97316);
    }
    [data-testid="column"]:nth-child(6) [data-testid="stMetric"]::before {
        background: linear-gradient(90deg, #f43f5e, #ec4899);
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }

    .sidebar-brand-card {
        background: radial-gradient(circle at 10% 20%, rgba(99, 102, 241, 0.25) 0%, transparent 60%),
                    linear-gradient(135deg, #090d16 0%, #1e1b4b 60%, #0f172a 100%);
        border: 1px solid rgba(245, 158, 11, 0.35);
        border-radius: 18px;
        padding: 20px 18px;
        margin-bottom: 20px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4), 0 0 18px rgba(245, 158, 11, 0.12);
    }

    .sidebar-brand-card .brand-sub {
        font-size: 10.5px;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        color: #fbbf24;
        font-weight: 800;
    }

    .sidebar-brand-card .brand-name {
        font-family: 'Outfit', sans-serif;
        font-size: 19px;
        font-weight: 800;
        margin: 4px 0 2px 0;
        letter-spacing: -0.01em;
        color: #ffffff;
    }

    .sidebar-brand-card .brand-ver {
        font-size: 12px;
        color: #94a3b8;
        display: flex;
        align-items: center;
        gap: 6px;
    }

    .sidebar-target-box {
        background: linear-gradient(135deg, rgba(30, 58, 138, 0.22) 0%, rgba(15, 23, 42, 0.35) 100%);
        border: 1px solid rgba(59, 130, 246, 0.35);
        border-left: 4px solid #3b82f6;
        padding: 14px 16px;
        border-radius: 12px;
        font-size: 13px;
        margin-top: 16px;
        line-height: 1.45;
    }

    /* Button Upgrades */
    button[kind="primary"] {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        letter-spacing: 0.02em !important;
        padding: 0.55rem 1.3rem !important;
        box-shadow: 0 4px 14px 0 rgba(79, 70, 229, 0.38) !important;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }

    button[kind="primary"]:hover {
        transform: translateY(-2px) scale(1.008) !important;
        box-shadow: 0 8px 24px 0 rgba(79, 70, 229, 0.55) !important;
    }

    button[kind="primary"]:active {
        transform: translateY(0px) scale(0.99) !important;
    }

    button[kind="secondary"] {
        border-radius: 12px !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        background: rgba(255, 255, 255, 0.03) !important;
        font-weight: 600 !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }

    button[kind="secondary"]:hover {
        border-color: rgba(99, 102, 241, 0.5) !important;
        background: rgba(99, 102, 241, 0.08) !important;
        transform: translateY(-1px) !important;
    }

    /* Modern Pill Tabs */
    div[data-testid="stTabs"] button[role="tab"] {
        border-radius: 12px !important;
        padding: 10px 20px !important;
        font-weight: 600 !important;
        font-size: 0.92rem !important;
        transition: all 0.2s ease !important;
        border: 1px solid transparent !important;
        background: transparent !important;
    }

    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.16) 0%, rgba(139, 92, 246, 0.16) 100%) !important;
        color: #818cf8 !important;
        border: 1px solid rgba(99, 102, 241, 0.4) !important;
        box-shadow: 0 4px 14px rgba(99, 102, 241, 0.12) !important;
    }

    div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        display: none !important;
    }

    /* Expanders */
    div[data-testid="stExpander"] {
        border-radius: 14px !important;
        border: 1px solid rgba(255, 255, 255, 0.09) !important;
        background: rgba(255, 255, 255, 0.02) !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
        margin-bottom: 12px;
    }

    div[data-testid="stExpander"]:hover {
        border-color: rgba(99, 102, 241, 0.35) !important;
        box-shadow: 0 4px 16px -2px rgba(0, 0, 0, 0.08) !important;
    }

    /* Options / Radio Cards in Exam & CBT Engine */
    div[data-testid="stRadio"] > div {
        gap: 10px;
    }

    div[data-testid="stRadio"] label {
        background: rgba(255, 255, 255, 0.035);
        border: 1px solid rgba(255, 255, 255, 0.09);
        border-radius: 12px;
        padding: 12px 18px;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        cursor: pointer;
        width: 100%;
    }

    div[data-testid="stRadio"] label:hover {
        background: rgba(99, 102, 241, 0.08);
        border-color: rgba(99, 102, 241, 0.4);
        transform: translateX(3px);
    }

    /* Glowing Badges & Tags */
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
        background-color: rgba(16, 185, 129, 0.14);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.35);
        box-shadow: 0 0 10px rgba(16, 185, 129, 0.15);
    }

    .badge-mock {
        background-color: rgba(245, 158, 11, 0.14);
        color: #f59e0b;
        border: 1px solid rgba(245, 158, 11, 0.35);
        box-shadow: 0 0 10px rgba(245, 158, 11, 0.15);
    }

    .badge-ai {
        background-color: rgba(139, 92, 246, 0.14);
        color: #a78bfa;
        border: 1px solid rgba(139, 92, 246, 0.35);
        box-shadow: 0 0 10px rgba(139, 92, 246, 0.15);
    }

    .badge-sample {
        background-color: rgba(59, 130, 246, 0.14);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.35);
        box-shadow: 0 0 10px rgba(59, 130, 246, 0.15);
    }

    .badge-verified {
        background-color: rgba(245, 158, 11, 0.14);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.35);
        box-shadow: 0 0 10px rgba(245, 158, 11, 0.15);
    }

    .badge-difficulty-easy {
        background-color: rgba(34, 197, 94, 0.14);
        color: #4ade80;
        border: 1px solid rgba(34, 197, 94, 0.35);
    }

    .badge-difficulty-medium {
        background-color: rgba(245, 158, 11, 0.14);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.35);
    }

    .badge-difficulty-hard {
        background-color: rgba(239, 68, 68, 0.14);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.35);
    }

    /* Interactive CBT Exam Cockpit Card */
    .cbt-cockpit-card {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.6) 0%, rgba(30, 27, 75, 0.4) 100%);
        border: 1px solid rgba(99, 102, 241, 0.25);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.3);
    }

    .cbt-timer-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.35);
        padding: 3px 10px;
        border-radius: 999px;
        font-weight: 700;
        font-size: 12px;
    }

    .cbt-marking-pill {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: rgba(239, 68, 68, 0.12);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
        padding: 3px 10px;
        border-radius: 999px;
        font-weight: 700;
        font-size: 12px;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def format_duration(seconds: float) -> str:
    """Format seconds into mm:ss or hh:mm:ss string."""
    total_sec = max(0, int(round(seconds)))
    hrs, rem = divmod(total_sec, 3600)
    mins, secs = divmod(rem, 60)
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def get_question_options_map(question_id: int) -> Dict[str, str]:
    """Retrieve full A/B/C/D option dictionary for a given question_id."""
    try:
        df = db.get_questions_by_ids([question_id])
        if not df.empty:
            row = df.iloc[0]
            return {
                "A": str(row.get("option_a", "") or ""),
                "B": str(row.get("option_b", "") or ""),
                "C": str(row.get("option_c", "") or ""),
                "D": str(row.get("option_d", "") or ""),
            }
    except Exception:
        pass
    return {"A": "", "B": "", "C": "", "D": ""}


def _resolve_question_options(question_id: Optional[int], fallback_row: Optional[Any] = None) -> Dict[str, str]:
    """Safely retrieve all 4 options (A-D) so AI Tutor & Diagnosis never lose context."""
    opts = {"A": "", "B": "", "C": "", "D": ""}
    if fallback_row is not None:
        if isinstance(fallback_row, dict) and isinstance(fallback_row.get("options"), dict):
            for k in ["A", "B", "C", "D"]:
                opts[k] = str(fallback_row["options"].get(k, "") or "")
            if any(opts.values()):
                return opts
        for k, col in [("A", "option_a"), ("B", "option_b"), ("C", "option_c"), ("D", "option_d")]:
            val = fallback_row.get(col, "") if hasattr(fallback_row, "get") else ""
            if val is not None and str(val).strip():
                opts[k] = str(val).strip()
        if any(opts.values()):
            return opts

    if question_id is not None and int(question_id) > 0:
        opts = get_question_options_map(int(question_id))
    return opts


def get_pinned_questions_df() -> pd.DataFrame:
    """Safely retrieve all pinned questions with their metadata using fast indexed join."""
    return db.get_pinned_questions_df()


def get_saved_research_notes() -> pd.DataFrame:
    """Safely fetch saved research notes from the local SQLite database."""
    try:
        with db.connect_db() as conn:
            return pd.read_sql_query(
                "SELECT * FROM research_notes ORDER BY id DESC", conn
            )
    except Exception:
        return pd.DataFrame()


def compute_confidence_calibration(attempts: pd.DataFrame) -> Dict[str, Any]:
    """Compute metacognitive calibration metrics from attempt confidence ratings."""
    if attempts.empty or "confidence_rating" not in attempts.columns:
        return {
            "high_conf_total": 0,
            "high_conf_accuracy": 0.0,
            "blind_spots": 0,
            "guess_total": 0,
            "guess_net_score": 0.0,
            "breakdown": pd.DataFrame(),
        }

    df = attempts[attempts["selected_option"] != "-"].copy()
    if df.empty:
        return {
            "high_conf_total": 0,
            "high_conf_accuracy": 0.0,
            "blind_spots": 0,
            "guess_total": 0,
            "guess_net_score": 0.0,
            "breakdown": pd.DataFrame(),
        }

    df["confidence_rating"] = df["confidence_rating"].fillna("Medium").replace("", "Medium")
    high_df = df[df["confidence_rating"] == "High"]
    guess_df = df[df["confidence_rating"] == "Guess"]

    high_total = len(high_df)
    high_acc = round(high_df["is_correct"].mean() * 100, 1) if high_total > 0 else 0.0
    blind_spots = int((high_df["is_correct"] == 0).sum()) if high_total > 0 else 0

    guess_total = len(guess_df)
    guess_net = float(guess_df["score"].sum()) if (guess_total > 0 and "score" in guess_df.columns) else 0.0

    rows = []
    for level in ["High", "Medium", "Guess"]:
        sub = df[df["confidence_rating"] == level]
        if not sub.empty:
            cnt = len(sub)
            corr = int(sub["is_correct"].sum())
            wrong = cnt - corr
            acc = round((corr / cnt) * 100, 1)
            net = round(float(sub["score"].sum()), 2) if "score" in sub.columns else float(corr)
            rows.append({
                "Confidence Level": level,
                "Attempts": cnt,
                "Correct": corr,
                "Incorrect": wrong,
                "Accuracy (%)": acc,
                "Net Marks": net,
            })

    return {
        "high_conf_total": high_total,
        "high_conf_accuracy": high_acc,
        "blind_spots": blind_spots,
        "guess_total": guess_total,
        "guess_net_score": round(guess_net, 2),
        "breakdown": pd.DataFrame(rows),
    }


def navigate_to(page_name: str) -> None:
    """Programmatically route to a target navigation view without widget conflicts."""
    if page_name in NAV_PAGES:
        st.session_state["nav_page"] = page_name
        st.session_state["_nav_radio_widget"] = page_name
        st.rerun()


# -----------------------------------------------------------------------------
# App Initialization & State Management
# -----------------------------------------------------------------------------

def init_session_state() -> None:
    """Initialize Streamlit session state variables."""
    db.init_db()
    defaults: Dict[str, Any] = {
        "nav_page": "Dashboard",
        "active_test": None,
        "test_results": None,
        "studio_questions": None,
        "studio_exemplars": [],
        "ca_questions": None,
        "ca_exemplars": [],
        "tutor_history": [],
        "tutor_context_question": None,
        "authenticated_user": None,
        "target_exam_name": "71st / 72nd BPSC CCE Prelims",
        "extracted_mock_preview": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# -----------------------------------------------------------------------------
# Views: 1. Dashboard
# -----------------------------------------------------------------------------

def show_dashboard() -> None:
    """Overview dashboard with key deterministic metrics, confidence telemetry, and study tools."""
    qb_stats = db.get_question_bank_summary()
    total_q_count = qb_stats["total_questions"]
    pyq_count = qb_stats["pyq_count"]

    st.markdown(
        f"""
        <div class="bpsc-hero">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px;">
                <span class="bpsc-hero-badge">🎯 71st / 72nd BPSC CCE Prelims Target Tracker</span>
                <span style="font-size: 11px; color: #94a3b8; font-weight: 700; letter-spacing: 0.6px; text-transform: uppercase;">
                    Target: Sept 2025 · 150 MCQs · 120 Mins · -0.33 Marking
                </span>
            </div>
            <h2 class="bpsc-hero-title">BPSC Question Lab v2.0</h2>
            <p class="bpsc-hero-desc">
                Adaptive, evidence-based preparation platform with authentic 10-year PYQ benchmarks, interactive CBT OMR examination simulation, and metacognitive confidence calibration.
            </p>
            <div class="bpsc-hero-chips">
                <span class="bpsc-hero-chip">🏛️ {pyq_count} Authentic 10-Yr BPSC PYQs (60th to 70th CCE)</span>
                <span class="bpsc-hero-chip">🎛️ Dual-Mode CBT & OMR Simulation</span>
                <span class="bpsc-hero-chip">🧠 Metacognitive Calibration</span>
                <span class="bpsc-hero-chip">⚡ Gemini AI Grounded Reasoning</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    attempts = db.get_attempts()
    sessions = db.get_test_sessions()
    overall = analytics.compute_overall_metrics(attempts, sessions)
    pinned_df = get_pinned_questions_df()
    calibration = compute_confidence_calibration(attempts)

    # Top KPI Metrics
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Question Bank", total_q_count)
    k2.metric("Tests Completed", overall["total_tests"])
    k3.metric("Total Attempts", overall["total_attempts"])
    k4.metric(
        "Overall Accuracy",
        f"{overall['accuracy']}%" if overall["total_attempts"] > 0 else "N/A",
    )
    k5.metric("Net Score", f"{overall['net_score']:.2f}")
    k6.metric(
        "High-Conf Blind Spots",
        calibration["blind_spots"],
        help="Incorrect answers where you rated your confidence as 'High'.",
    )

    # Cloud & AI System Status Pills
    s1, s2 = st.columns(2)
    with s1:
        if config.is_gemini_configured():
            st.success(f"🤖 Gemini AI: Connected (`{config.get_gemini_model()}`)")
        else:
            st.warning(
                "🤖 Gemini AI: Not configured. Set `GEMINI_API_KEY` in `.streamlit/secrets.toml` or `.env`."
            )
    with s2:
        if config.is_supabase_configured():
            user = st.session_state.get("authenticated_user")
            if user:
                st.success(f"☁️ Supabase Cloud: Logged in as {user.get('email', 'User')}")
            else:
                st.info("☁️ Supabase Cloud: Ready (Login under Settings to sync data)")
        else:
            st.info(
                f"💾 Local SQLite Mode · {len(pinned_df)} Pinned Question(s) in Revision Vault"
            )

    st.divider()

    # Topic Analytics & Quick Actions
    col_left, col_right = st.columns([3, 2])
    with col_left:
        st.subheader("📊 Syllabus Mastery & Weak Spots")
        if not attempts.empty:
            topic_df = analytics.compute_topic_analytics(attempts)
            weak = analytics.identify_weak_areas(topic_df, max_items=6)
            if not weak.empty:
                st.dataframe(
                    weak[
                        [
                            "subject",
                            "topic",
                            "attempts",
                            "accuracy",
                            "sample_size_label",
                            "priority",
                        ]
                    ].rename(
                        columns={
                            "subject": "Subject",
                            "topic": "Topic",
                            "attempts": "Attempts",
                            "accuracy": "Accuracy (%)",
                            "sample_size_label": "Evidence",
                            "priority": "Urgency",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.success(
                    "No critical weak spots detected with low accuracy! Keep practising to expand coverage."
                )

            # Subject Mastery Breakdown Bar Chart
            with st.expander("📈 View Subject-Wise Accuracy & Question Bank Coverage", expanded=False):
                try:
                    subj_acc = attempts.groupby("subject").apply(
                        lambda g: round((g["is_correct"] == 1).sum() / len(g) * 100)
                    ).to_frame(name="Accuracy (%)")
                    if not subj_acc.empty:
                        st.bar_chart(subj_acc, color="#3b82f6", use_container_width=True)
                except Exception:
                    pass
        else:
            st.info(
                "No test attempts recorded yet. Start a practice test to unlock syllabus diagnostics."
            )

    with col_right:
        st.subheader("🎯 Rapid Launchpad")
        if st.button("🚀 Start Practice / Mock Test", type="primary", use_container_width=True):
            navigate_to("Practice & Mock Tests")

        c_q1, c_q2 = st.columns(2)
        if c_q1.button("✨ AI Question Studio", use_container_width=True):
            navigate_to("AI Question Studio")
        if c_q2.button("📰 Current Affairs Lab", use_container_width=True):
            navigate_to("Current Affairs Lab")

        c_q3, c_q4 = st.columns(2)
        if c_q3.button("📕 Error Notebook", use_container_width=True):
            navigate_to("Error Notebook")
        if c_q4.button("📅 Revision Planner", use_container_width=True):
            navigate_to("Revision Planner")

        # Instant 5-Question Quick Drill
        if not q_all.empty:
            st.markdown("##### ⚡ 5-Minute Express Drill")
            if st.button("Launch 5-Q Mixed BPSC Drill (-0.33 Marking)", use_container_width=True):
                all_ids = q_all["id"].astype(int).tolist()
                chosen = random.sample(all_ids, k=min(5, len(all_ids)))
                st.session_state["active_test"] = {
                    "session_id": str(uuid.uuid4())[:8],
                    "question_ids": chosen,
                    "exam": "BPSC",
                    "test_mode": "Timed Drill (1 min/Q)",
                    "ui_style": "Interactive OMR Palette",
                    "instant_feedback": False,
                    "negative_rate": 0.33,
                    "start_time": time.time(),
                    "current_index": 0,
                    "answers": {},
                    "confidences": {},
                    "marked_review": [],
                    "question_times": {},
                    "last_q_timestamp": time.time(),
                }
                st.session_state["test_results"] = None
                navigate_to("Practice & Mock Tests")

    # Recent Test Sessions History
    if not sessions.empty:
        st.divider()
        st.subheader("🕒 Recent Test Sessions")
        disp_sess = sessions.head(8).copy()
        cols_to_show = [
            c
            for c in [
                "session_id",
                "exam",
                "test_mode",
                "total_questions",
                "correct_count",
                "incorrect_count",
                "unanswered_count",
                "total_score",
                "time_spent_seconds",
                "completed_at",
            ]
            if c in disp_sess.columns
        ]
        st.dataframe(disp_sess[cols_to_show], use_container_width=True, hide_index=True)


# -----------------------------------------------------------------------------
# Views: 2. Question Bank & Mock Test Architecture
# -----------------------------------------------------------------------------

def _render_question_card_view(q: pd.Series | Dict[str, Any], show_actions: bool = True, key_prefix: str = "qb") -> None:
    """Helper to render a standardized, elegant question card across all question views."""
    qid = int(q["id"]) if "id" in q and pd.notna(q["id"]) else 0
    is_pinned = db.is_question_pinned(qid) if qid > 0 else False
    stype = str(q.get("source_type", ""))
    
    if stype == "Official PYQ":
        badge = "🏛️ Official Verified PYQ"
        b_cls = "badge-pyq"
    elif stype == "Mock question":
        badge = "📝 Mock Question"
        b_cls = "badge-mock"
    elif q.get("is_ai_generated"):
        badge = "🤖 AI Practice"
        b_cls = "badge-ai"
    else:
        badge = "📌 Practice Sample"
        b_cls = "badge-sample"

    provenance_line = f"<span class='lab-badge {b_cls}'>{badge}</span> "
    provenance_line += f"<b>{q.get('subject', 'General')}</b> → <i>{q.get('topic', 'General')}</i> · Difficulty: <b>{q.get('difficulty', 'Medium')}</b>"
    if q.get("source_name"):
        provenance_line += f" · <code>{q['source_name']}</code>"
    elif q.get("exam_edition"):
        provenance_line += f" · {q['exam_edition']}"
    if q.get("exam_year") and pd.notna(q.get("exam_year")) and str(q["exam_year"]).strip():
        try:
            provenance_line += f" ({int(float(q['exam_year']))})"
        except Exception:
            pass
    if q.get("paper_set"):
        provenance_line += f" · {q['paper_set']}"
    if q.get("official_qno") and pd.notna(q.get("official_qno")):
        try:
            q_num = int(q["official_qno"])
            if q_num > 0:
                provenance_line += f" · Q.{q_num}"
        except Exception:
            pass

    with st.container(border=True):
        st.markdown(f"#### Question #{qid if qid > 0 else '•'}: {q['question']}")
        st.markdown(provenance_line, unsafe_allow_html=True)
        st.write(
            f"- **A.** {q['option_a']}\n"
            f"- **B.** {q['option_b']}\n"
            f"- **C.** {q['option_c']}\n"
            f"- **D.** {q['option_d']}"
        )
        with st.expander("Reveal Correct Option & Explanation", expanded=False):
            st.info(
                f"**Correct Option:** `{q['correct_option']}`\n\n"
                f"**Explanation:** {q.get('explanation', 'No explanation recorded.')}"
            )
            if q.get("distractor_notes"):
                st.caption(f"**Distractor Analysis:** {q['distractor_notes']}")

        if show_actions and qid > 0:
            b1, b2 = st.columns([1, 1])
            pin_lbl = "📌 Unpin Question" if is_pinned else "📍 Pin for Revision"
            if b1.button(pin_lbl, key=f"{key_prefix}_pin_{qid}"):
                if is_pinned:
                    db.unpin_question(qid)
                else:
                    db.pin_question(qid, note=f"Pinned from Question Bank ({q.get('topic', '')})")
                st.rerun()

            if config.is_gemini_configured() and b2.button("🎓 Discuss with AI Tutor", key=f"{key_prefix}_tutor_{qid}"):
                opts_map = {
                    "A": str(q["option_a"]),
                    "B": str(q["option_b"]),
                    "C": str(q["option_c"]),
                    "D": str(q["option_d"]),
                }
                st.session_state["tutor_context_question"] = {
                    "question_id": qid,
                    "question": q["question"],
                    "options": opts_map,
                    "selected_option": "-",
                    "selected_text": f"Exploring {stype or 'Question Bank'}",
                    "correct_option": q["correct_option"],
                    "correct_text": opts_map.get(q["correct_option"], ""),
                    "explanation": q.get("explanation", ""),
                    "subject": q["subject"],
                    "topic": q["topic"],
                }
                navigate_to("AI Study Tutor")


def show_question_bank() -> None:
    """Browse, filter, search, upload mock PDFs with AI OCR, and manage questions."""
    st.title("📖 Question Bank & Mock Test Architecture")
    st.caption("Organized repository for Official PYQs, Extracted Mock Tests, AI Practice Drills, and PDF OCR extractions.")

    tab_mocks, tab_upload_pdf, tab_pyqs, tab_all, tab_add_csv = st.tabs([
        "📝 Mock Questions Bank",
        "📄 Upload Mock PDF & OCR Extractor",
        "🏛️ 10-Year Official PYQ Bank",
        "🔍 All Questions Vault",
        "➕ Add Manually & CSV Import",
    ])

    # =========================================================================
    # Tab 1: Mock Questions Bank (Dedicated Mock Question Section)
    # =========================================================================
    with tab_mocks:
        st.subheader("📝 Mock Questions Bank")
        st.write("Curated test series questions, coaching institute mock papers, and PDF extractions sorted by syllabus subject.")

        mock_total = db.count_questions(source_type="Mock question")

        if mock_total == 0:
            st.info(
                "ℹ️ **No mock questions in the database yet.**\n\n"
                "You can upload OCR text PDFs or scanned image test papers in the **'📄 Upload Mock PDF & OCR Extractor'** "
                "tab. The AI will extract all questions, answers, and explanations, and automatically sort them into standard subjects!"
            )
        else:
            mock_names = ["All Mock Tests"] + db.get_mock_test_names()
            mock_subjects = ["All"] + db.get_distinct_subjects(source_type="Mock question")
            diff_counts = db.get_difficulty_counts(source_type="Mock question")

            # Top KPI metrics for Mock Questions
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Mock Questions", f"{mock_total:,}")
            m2.metric("Mock Test Series", max(0, len(mock_names) - 1))
            m3.metric("Subjects Covered", max(0, len(mock_subjects) - 1))
            m4.metric("Medium / Hard", f"{diff_counts.get('Medium', 0)} / {diff_counts.get('Hard', 0)}")

            # Subject Distribution Chips
            subj_counts = db.get_subject_counts(source_type="Mock question")
            if subj_counts:
                st.markdown("##### 🧭 Subject Breakdown in Mock Database")
                s_cols = st.columns(min(5, len(subj_counts) or 1))
                for idx, (s_name, s_val) in enumerate(subj_counts.items()):
                    s_cols[idx % len(s_cols)].metric(s_name, f"{s_val} Qs")
                st.divider()

            # Filter Controls for Mock Questions
            fc1, fc2, fc3, fc4, fc5 = st.columns([1.5, 1.2, 1.2, 1.0, 1.5])
            selected_mock = fc1.selectbox("Mock Test Series", mock_names, key="mock_filter_series")
            selected_subject = fc2.selectbox("Subject", mock_subjects, key="mock_filter_subject")

            mock_topics = ["All"] + db.get_distinct_topics(
                subject=selected_subject if selected_subject != "All" else None,
                source_type="Mock question",
            )
            selected_topic = fc3.selectbox("Topic", mock_topics, key="mock_filter_topic")

            selected_diff = fc4.selectbox("Difficulty", ["All", "Easy", "Medium", "Hard"], key="mock_filter_diff")
            search_mock_kw = fc5.text_input("Search Mock Questions", placeholder="e.g. Fundamental Rights, Bihar...", key="mock_kw")

            # Apply indexed query filters
            filtered_mock = db.list_mock_questions(
                subject=selected_subject,
                topic=selected_topic,
                mock_name=selected_mock,
            )
            if selected_diff != "All" and "difficulty" in filtered_mock.columns:
                filtered_mock = filtered_mock[filtered_mock["difficulty"] == selected_diff]
            if search_mock_kw.strip():
                kw = search_mock_kw.strip().lower()
                filtered_mock = filtered_mock[
                    filtered_mock["question"].str.lower().str.contains(kw, na=False)
                    | filtered_mock["topic"].str.lower().str.contains(kw, na=False)
                    | filtered_mock["explanation"].str.lower().str.contains(kw, na=False)
                ]

            # Action bar: Practice Mock Test
            act_col1, act_col2 = st.columns([3, 1])
            act_col1.caption(f"Showing **{len(filtered_mock)}** of **{mock_total}** mock question(s).")
            if not filtered_mock.empty and act_col2.button("🎯 Practice Filtered Mock Set", type="primary", use_container_width=True, key="btn_mock_practice"):
                f_ids = filtered_mock["id"].astype(int).tolist()
                chosen = random.sample(f_ids, k=min(25, len(f_ids)))
                st.session_state["active_test"] = {
                    "session_id": str(uuid.uuid4())[:8],
                    "question_ids": chosen,
                    "exam": "BPSC",
                    "test_mode": f"Mock Test Drill ({selected_mock if selected_mock != 'All Mock Tests' else 'Mixed Mock'})",
                    "ui_style": "Interactive OMR Palette",
                    "instant_feedback": True,
                    "negative_rate": 0.33,
                    "start_time": time.time(),
                    "current_index": 0,
                    "answers": {},
                    "confidences": {},
                    "marked_review": [],
                    "question_times": {},
                    "last_q_timestamp": time.time(),
                }
                st.session_state["test_results"] = None
                navigate_to("Practice & Mock Tests")

            # Data Table (bounded preview to prevent WebSocket freezing with 7,500+ items)
            disp_mock_cols = ["id", "source_name", "subject", "topic", "question", "correct_option", "difficulty", "answer_key_status"]
            avail_m_cols = [c for c in disp_mock_cols if c in filtered_mock.columns]
            st.dataframe(filtered_mock[avail_m_cols].head(150), use_container_width=True, hide_index=True)
            if len(filtered_mock) > 150:
                st.caption(f"⚡ Showing first 150 rows in the preview grid for high performance. Browse all {len(filtered_mock)} questions via the cards below.")

            # Paginated Cards
            with st.expander("🔍 Browse Detailed Mock Question Cards (Paginated)", expanded=True):
                if filtered_mock.empty:
                    st.info("No mock questions match the selected filters.")
                else:
                    m_page_size = 10
                    m_total_pages = max(1, (len(filtered_mock) + m_page_size - 1) // m_page_size)
                    mp_col1, mp_col2 = st.columns([1, 3])
                    m_page_num = mp_col1.number_input(
                        f"Page (1 to {m_total_pages})", min_value=1, max_value=m_total_pages, value=1, step=1, key="mock_page_ctrl"
                    )
                    m_start_idx = (m_page_num - 1) * m_page_size
                    m_page_slice = filtered_mock.iloc[m_start_idx : m_start_idx + m_page_size]

                    for _, q_row in m_page_slice.iterrows():
                        _render_question_card_view(q_row, show_actions=True, key_prefix="mock_bank")

            # Question Bank Deduplication & Integrity Scanner
            with st.expander("🛡️ Question Bank Deduplication & Integrity Scanner", expanded=False):
                st.caption("Scan all questions in your database to ensure no question is repeated twice or thrice.")
                sc_col1, sc_col2 = st.columns([2, 1])
                if sc_col1.button("🔍 Scan for Duplicate Questions Now", key="btn_scan_dupes_mock"):
                    st.session_state["dupe_scan_run"] = True

                if st.session_state.get("dupe_scan_run"):
                    with db.connect_db() as conn:
                        dupe_rows = conn.execute("""
                            SELECT normalized_stem, COUNT(*) as cnt, GROUP_CONCAT(id) as id_list
                            FROM questions
                            WHERE normalized_stem != ''
                            GROUP BY normalized_stem
                            HAVING cnt > 1
                        """).fetchall()
                    total_excess = sum(int(r["cnt"]) - 1 for r in dupe_rows)
                    found_dupes = {r["normalized_stem"]: [int(x) for x in r["id_list"].split(",")] for r in dupe_rows}

                    if total_excess == 0:
                        st.success("✅ **Integrity Verified:** Zero duplicate questions detected! Every question in your database is 100% unique.")
                    else:
                        st.warning(f"⚠️ Found **{total_excess}** duplicate question occurrence(s) across {len(found_dupes)} unique question stems.")
                        if sc_col2.button("🧹 Clean All Duplicates (Keep 1 Copy)", type="primary", key="btn_clean_dupes_act"):
                            removed_cnt, _ = db.find_and_remove_duplicate_questions()
                            st.success(f"Cleaned {removed_cnt} duplicate question(s) from database!")
                            st.session_state["dupe_scan_run"] = False
                            st.rerun()

            # Manage / Delete Uploaded Mock Series Expander
            with st.expander("⚙️ Manage & Delete Uploaded Mock Test Batches", expanded=False):
                st.caption("Safely purge an uploaded mock test paper if you wish to re-upload or clear obsolete tests.")
                del_names = db.get_mock_test_names()
                if not del_names:
                    st.write("No uploaded mock batches available.")
                else:
                    del_col1, del_col2 = st.columns([3, 1])
                    to_delete = del_col1.selectbox("Select Mock Test to Delete", del_names, key="sel_del_mock")
                    if del_col2.button("🗑️ Delete Mock Test", type="secondary", key="btn_del_mock"):
                        deleted_cnt = db.delete_mock_test(to_delete)
                        st.success(f"Deleted {deleted_cnt} question(s) associated with '{to_delete}'.")
                        st.rerun()

    # =========================================================================
    # Tab 2: Upload Mock PDF & OCR Extractor (OCR & Scanned PDF Pipeline)
    # =========================================================================
    with tab_upload_pdf:
        st.subheader("📄 Upload Mock PDF & Automated OCR Extractor")
        st.write(
            "Upload any mock examination paper PDF (both digital OCR text PDFs and scanned image PDFs are supported). "
            "Antigravity AI extracts all multiple-choice questions, identifies options & answer keys, and **automatically sorts each question into its relevant syllabus subject**."
        )

        # Multi-Engine OCR Detection & Status Badges
        avail_ocr_subsystems = ocr_engine.get_available_ocr_engines()
        ocr_badges = []
        for eng in avail_ocr_subsystems:
            if eng["available"]:
                ocr_badges.append(
                    f"<span class='lab-badge' style='background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.35); font-weight: 600;'>✅ {eng['name']}</span>"
                )
            else:
                ocr_badges.append(
                    f"<span class='lab-badge' style='background: rgba(148, 163, 184, 0.12); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.25);'>⚪ {eng['name']} (Standby)</span>"
                )

        st.markdown(
            f"""
            <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; padding: 12px 16px; margin-bottom: 14px;">
                <div style="font-weight: 700; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;">
                    <span style="font-size: 1.1rem;">⚡</span> Multi-Engine Cascaded Local OCR Engine (RapidOCR / PaddleOCR / Pytesseract)
                </div>
                <div style="font-size: 0.88rem; color: #cbd5e1; margin-bottom: 8px;">
                    Processes scanned test papers through parallel local OCR first to save ~85% API tokens and reduce Gemini load.
                    Runs continuously in the background even if you close the tab or your computer sleeps, with instant cancellation support.
                </div>
                <div><b>Active OCR Engines:</b> {' '.join(ocr_badges)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Check for active background job or restored completed job
        active_bg_job = db.get_active_ocr_job()
        latest_bg_job = db.get_latest_completed_or_active_job()

        # If a background job just completed and user hasn't previewed it yet, restore it
        if st.session_state.get("extracted_mock_preview") is None and latest_bg_job and latest_bg_job["status"] == "completed":
            if st.session_state.get("dismissed_ocr_job_id") != latest_bg_job["job_id"]:
                job_stats = latest_bg_job.get("stats", {})
                job_stats["job_id"] = latest_bg_job["job_id"]
                st.session_state["extracted_mock_preview"] = {
                    "questions": latest_bg_job.get("extracted_questions", []),
                    "stats": job_stats,
                }

        # 1. If a job is currently RUNNING in background: show live progress panel & CANCEL button
        if active_bg_job is not None:
            st.markdown(
                f"""
                <div style="background: rgba(59, 130, 246, 0.08); border: 2px solid rgba(59, 130, 246, 0.4); border-radius: 10px; padding: 18px 22px; margin-bottom: 20px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <div style="font-size: 1.15rem; font-weight: 700; color: #60a5fa;">
                            ⚙️ Background PDF OCR in Progress: {active_bg_job['mock_title']}
                        </div>
                        <span class="lab-badge" style="background: rgba(59, 130, 246, 0.2); color: #93c5fd; border: 1px solid rgba(59, 130, 246, 0.4);">
                            RUNNING IN BACKGROUND
                        </span>
                    </div>
                    <div style="font-size: 0.9rem; color: #cbd5e1; margin-bottom: 4px;">
                        🛡️ <b>Sleep & Reload Resilient:</b> You can safely reload the page, close this tab, or put your computer to sleep.
                        The extraction runs continuously in the background on the server until finished or cancelled.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Live progress bar and page metrics
            curr_progress = max(0.02, min(1.0, float(active_bg_job.get("progress", 0.05))))
            st.progress(curr_progress)

            p_col1, p_col2 = st.columns([3, 1])
            p_col1.write(f"⏳ **Status:** {active_bg_job.get('progress_msg', 'Processing mock pages...')}")

            if p_col2.button("⏹️ Cancel Extraction", type="secondary", use_container_width=True, key="btn_cancel_running_ocr"):
                db.request_cancel_ocr_job(active_bg_job["job_id"])
                st.warning("Cancellation requested. Halting background extraction...")
                time.sleep(1)
                st.rerun()

            # Auto-poll while extraction is running
            time.sleep(2)
            st.rerun()

        # 2. If the previous job was CANCELLED by user: show notification and dismiss action
        elif latest_bg_job and latest_bg_job["status"] == "cancelled" and st.session_state.get("dismissed_ocr_job_id") != latest_bg_job["job_id"]:
            st.warning(f"⚠️ Extraction of **'{latest_bg_job['mock_title']}'** was cancelled by user. Partial questions were discarded.")
            if st.button("Dismiss & Start New PDF Upload", key="btn_dismiss_cancelled_job"):
                db.clear_ocr_job(latest_bg_job["job_id"])
                st.session_state["dismissed_ocr_job_id"] = latest_bg_job["job_id"]
                st.rerun()

        # 3. If the previous job FAILED: show error and dismiss action
        elif latest_bg_job and latest_bg_job["status"] == "failed" and st.session_state.get("dismissed_ocr_job_id") != latest_bg_job["job_id"]:
            st.error(f"❌ Extraction error on **'{latest_bg_job['mock_title']}'**: {latest_bg_job.get('error_msg', 'Unknown error')}")
            if st.button("Dismiss & Try Again", key="btn_dismiss_failed_job"):
                db.clear_ocr_job(latest_bg_job["job_id"])
                st.session_state["dismissed_ocr_job_id"] = latest_bg_job["job_id"]
                st.rerun()

        # 4. Normal PDF Upload Form (shown when no job is currently processing)
        if active_bg_job is None:
            up_col1, up_col2 = st.columns([3, 2])

            dup_handling_mode = "🛡️ Extract only new unique questions (Skip duplicates)"
            pdf_file_hash = ""
            is_already_uploaded = False

            with up_col1:
                uploaded_pdf = st.file_uploader(
                    "Upload Mock Test PDF (OCR or Scanned)",
                    type=["pdf"],
                    key="mock_pdf_uploader",
                    help="Supports multi-page OCR text PDFs and scanned image PDFs. No practical file size limit (up to 2GB).",
                )
                suggested_title = ""
                if uploaded_pdf is not None:
                    suggested_title = Path(uploaded_pdf.name).stem.replace("_", " ").title()
                    pdf_bytes_check = uploaded_pdf.getvalue()
                    pdf_file_hash = hashlib.sha256(pdf_bytes_check).hexdigest()
                    is_already_uploaded, prev_meta = db.is_pdf_already_uploaded(uploaded_pdf.name, pdf_file_hash)

                    if is_already_uploaded and prev_meta:
                        st.warning(
                            f"⚠️ **Duplicate File Detected:** `'**{uploaded_pdf.name}**'` has already been uploaded previously!\n\n"
                            f"- **Recorded Mock Title:** `{prev_meta.get('mock_title', uploaded_pdf.name)}`\n"
                            f"- **Uploaded On:** {prev_meta.get('uploaded_at', 'Previously')}\n"
                            f"- **Questions in DB:** {prev_meta.get('questions_count', 0)} question(s)\n\n"
                            "Select how to handle this file to prevent duplicate questions:"
                        )
                        dup_handling_mode = st.radio(
                            "Duplicate File Handling",
                            [
                                "🛡️ Extract only new unique questions (Skip questions already in database)",
                                "🔄 Re-extract & Replace existing test (Purge older questions from this test and refresh)",
                                "⛔ Cancel processing (Do not extract to avoid duplicate questions)",
                            ],
                            key="pdf_dup_handling_mode",
                        )

                mock_test_title = st.text_input(
                    "Mock Test Title / Institute Name*",
                    value=suggested_title or "Drishti IAS BPSC Prelims Mock 01",
                    placeholder="e.g. Drishti IAS BPSC Prelims Mock 01",
                    help="This title will be tagged as the source of all extracted questions.",
                )

            with up_col2:
                target_exam_pdf = st.selectbox("Target Exam Syllabus", ["BPSC", "UPSC", "Both"], index=0, key="pdf_target_exam")
                
                ocr_strat_selection = st.selectbox(
                    "OCR Processing Pipeline",
                    [
                        "⚡ Auto Cascaded (Local OCR First → Gemini Vision Fallback)",
                        "👁️ Gemini Multimodal Vision Only (Direct Cloud Vision)",
                        "💻 Local OCR Only (RapidOCR / Pytesseract)",
                    ],
                    index=0,
                    help="Recommended: Auto Cascaded saves ~85% Gemini API tokens by running local OCR first on scanned images, with automatic fallback to Gemini Vision if scanned quality is degraded.",
                    key="pdf_ocr_pipeline_choice",
                )
                strat_code_map = {
                    "⚡ Auto Cascaded (Local OCR First → Gemini Vision Fallback)": "auto",
                    "👁️ Gemini Multimodal Vision Only (Direct Cloud Vision)": "vision_only",
                    "💻 Local OCR Only (RapidOCR / Pytesseract)": "local_only",
                }
                active_ocr_strategy = strat_code_map.get(ocr_strat_selection, "auto")

                pref_engine_code = "auto"
                if active_ocr_strategy != "vision_only":
                    pref_engine_label = st.selectbox(
                        "Preferred Local Engine",
                        [
                            "Auto Priority (RapidOCR → PaddleOCR → Pytesseract)",
                            "RapidOCR (Fastest ONNX CPU)",
                            "PaddleOCR (Deep Learning)",
                            "Pytesseract (Google Tesseract)",
                        ],
                        index=0,
                        key="pdf_pref_local_engine",
                    )
                    pref_code_map = {
                        "Auto Priority (RapidOCR → PaddleOCR → Pytesseract)": "auto",
                        "RapidOCR (Fastest ONNX CPU)": "rapidocr",
                        "PaddleOCR (Deep Learning)": "paddleocr",
                        "Pytesseract (Google Tesseract)": "pytesseract",
                    }
                    pref_engine_code = pref_code_map.get(pref_engine_label, "auto")

                page_scope = st.radio("Page Processing Scope", ["Process All Pages", "Custom Page Range"], horizontal=True, key="pdf_scope")
                p_start, p_end = None, None
                if page_scope == "Custom Page Range":
                    pr_c1, pr_c2 = st.columns(2)
                    p_start = pr_c1.number_input("Start Page", min_value=1, value=1, step=1, key="pdf_p_start")
                    p_end = pr_c2.number_input("End Page", min_value=1, value=15, step=1, key="pdf_p_end")

                chunk_batch_size = st.slider(
                    "Batch Size (Pages per AI Chunk)",
                    min_value=2,
                    max_value=6,
                    value=4,
                    help="Smaller chunk sizes (3-5 pages) avoid AI token truncation and allow smooth real-time progress updates.",
                )

            is_cancel_selected = dup_handling_mode.startswith("⛔")
            extract_clicked = st.button(
                "🚀 Extract, OCR & Sort Mock Questions (Background)",
                type="primary",
                use_container_width=True,
                disabled=(uploaded_pdf is None or is_cancel_selected),
                key="btn_run_pdf_extraction",
            )

            if is_cancel_selected and uploaded_pdf is not None:
                st.info("ℹ️ Processing cancelled to prevent duplicate questions. To proceed, select 'Skip questions already in database' or choose another PDF.")

            if extract_clicked and uploaded_pdf is not None and not is_cancel_selected:
                if not config.is_gemini_configured():
                    st.error("Gemini AI is not configured. Please add your GEMINI_API_KEY in `.streamlit/secrets.toml` or `.env` to enable AI OCR & subject classification.")
                else:
                    pdf_bytes = uploaded_pdf.getvalue()
                    new_job_id = pdf_extractor.start_background_extraction_job(
                        pdf_bytes=pdf_bytes,
                        filename=uploaded_pdf.name,
                        mock_title=mock_test_title.strip() or "Uploaded Mock Test",
                        target_exam=target_exam_pdf,
                        page_start=p_start,
                        page_end=p_end,
                        chunk_size=chunk_batch_size,
                        ocr_strategy=active_ocr_strategy,
                        preferred_local_engine=pref_engine_code,
                    )
                    st.success(f"🚀 Started background OCR extraction for '{uploaded_pdf.name}'! You can safely reload the page or put your computer to sleep.")
                    time.sleep(1)
                    st.rerun()

        # Render Extracted Preview & Database Save Action with Deduplication
        if st.session_state.get("extracted_mock_preview") is not None:
            prev_info = st.session_state["extracted_mock_preview"]
            ext_questions = prev_info.get("questions", [])
            ext_stats = prev_info.get("stats", {})

            st.markdown("---")
            st.subheader(f"📊 Extraction Preview: {ext_stats.get('mock_title', 'Mock Test')}")

            if not ext_questions:
                st.warning("No multiple-choice questions were found in the selected pages of this document. Check the page range or ensure the pages contain questions.")
                if st.button("Clear Preview", key="btn_clear_empty_prev"):
                    st.session_state["extracted_mock_preview"] = None
                    st.rerun()
            else:
                # 1. Deduplicate against existing question bank
                unique_qs, duplicate_qs = db.filter_duplicate_questions(ext_questions)

                # 2. Key Telemetry Metrics
                k1, k2, k3, k4, k5 = st.columns(5)
                k1.metric("Total Questions Parsed", len(ext_questions))
                k2.metric("✨ New Unique Questions", len(unique_qs), help="Questions not currently in your Question Bank")
                k3.metric("🛡️ Duplicates Filtered", len(duplicate_qs), help="Questions already present in your database or repeated in this document")
                k4.metric("Pipeline Mode", ext_stats.get("ocr_strategy", "auto").title())
                t_saved = ext_stats.get("tokens_saved_estimate", 0)
                k5.metric("⚡ Est. Tokens Saved", f"~{t_saved:,}" if t_saved > 0 else "N/A", help="Estimated API input tokens saved by running local OCR / text extraction instead of multimodal image encoding")

                # Telemetry breakdown of cascade execution
                loc_pages = ext_stats.get("local_ocr_pages", 0)
                vis_pages = ext_stats.get("vision_fallback_pages", 0)
                dig_pages = ext_stats.get("digital_text_pages", 0)
                engs_used = ext_stats.get("local_engines_used", [])

                telemetry_items = []
                if loc_pages > 0:
                    telemetry_items.append(f"⚡ **{loc_pages} page(s)** processed via **Local OCR** ({', '.join(engs_used) if engs_used else 'RapidOCR / Pytesseract'})")
                if dig_pages > 0:
                    telemetry_items.append(f"📄 **{dig_pages} page(s)** processed via **Digital Text Extraction**")
                if vis_pages > 0:
                    telemetry_items.append(f"👁️ **{vis_pages} page(s)** verified via **Gemini Multimodal Vision Fallback** (ensuring zero accuracy loss)")

                if telemetry_items:
                    st.caption(" • ".join(telemetry_items))

                if len(duplicate_qs) > 0:
                    st.info(
                        f"🛡️ **Deduplication Active:** **{len(duplicate_qs)}** question(s) already exist in your Question Bank or were repeated in this PDF. "
                        "They will **NOT** be inserted again, ensuring your question bank never has questions repeated twice or thrice."
                    )
                    with st.expander(f"🔍 Inspect {len(duplicate_qs)} Filtered Duplicate Question(s)", expanded=False):
                        for dq in duplicate_qs[:25]:
                            st.write(f"- **{dq.get('question', '')[:90]}...** — *{dq.get('duplicate_reason', 'Duplicate')}*")
                        if len(duplicate_qs) > 25:
                            st.caption(f"... and {len(duplicate_qs) - 25} more duplicate questions safely filtered out.")

                # 3. Subject Sorting Distribution Grid
                st.markdown("#### 🧭 Automatic Subject Distribution (New Unique Questions)")
                u_subj_counts: Dict[str, int] = {}
                for q in unique_qs:
                    s_name = q.get("subject", "Other")
                    u_subj_counts[s_name] = u_subj_counts.get(s_name, 0) + 1

                if u_subj_counts:
                    dist_cols = st.columns(min(5, len(u_subj_counts)))
                    for d_idx, (s_name, s_count) in enumerate(u_subj_counts.items()):
                        dist_cols[d_idx % len(dist_cols)].metric(s_name, f"{s_count} Qs")
                elif len(unique_qs) == 0:
                    st.warning("⚠️ **All questions in this PDF already exist in your Question Bank!** Zero duplicate questions will be inserted.")

                # 4. Preview Data Table
                if unique_qs:
                    prev_df = pd.DataFrame(unique_qs)
                    cols_to_preview = ["subject", "topic", "question", "correct_option", "difficulty", "explanation"]
                    avail_prev_cols = [c for c in cols_to_preview if c in prev_df.columns]
                    st.dataframe(prev_df[avail_prev_cols], use_container_width=True, hide_index=True)

                    with st.expander(f"🔍 Inspect All {len(unique_qs)} Unique Question Cards Before Saving", expanded=False):
                        for idx, q_dict in enumerate(unique_qs):
                            _render_question_card_view(q_dict, show_actions=False, key_prefix=f"prev_{idx}")

                # 5. Save or Discard Actions
                sv_col1, sv_col2 = st.columns([3, 1])
                btn_save_text = f"💾 Add {len(unique_qs)} Unique Questions to Mock Database" if unique_qs else "💾 No New Questions to Add (All Duplicate)"
                if sv_col1.button(btn_save_text, type="primary", use_container_width=True, disabled=len(unique_qs) == 0, key="btn_save_extracted_to_db"):
                    # Check if user chose to replace/purge existing mock test questions
                    if st.session_state.get("pdf_dup_handling_mode", "").startswith("🔄"):
                        db.delete_mock_test(ext_stats.get("mock_title", ""))

                    saved_count = 0
                    for q_item in unique_qs:
                        db.add_question(q_item, skip_if_duplicate=True)
                        saved_count += 1

                    # Record uploaded file in the registry
                    fname = ext_stats.get("filename", ext_stats.get("mock_title", "mock.pdf"))
                    fhash = ext_stats.get("file_hash", "")
                    fbytes_len = ext_stats.get("file_bytes_len", 0)
                    db.record_uploaded_pdf(
                        filename=fname,
                        file_hash=fhash,
                        mock_title=ext_stats.get("mock_title", ""),
                        questions_count=saved_count,
                        file_size_bytes=fbytes_len,
                    )

                    # Clear background job from database if tracked
                    if ext_stats.get("job_id"):
                        db.clear_ocr_job(ext_stats["job_id"])
                    st.session_state["extracted_mock_preview"] = None
                    st.success(f"✨ Successfully added **{saved_count}** unique mock questions! (Prevented {len(duplicate_qs)} duplicates from repeating).")
                    st.rerun()

                if sv_col2.button("❌ Discard Preview", use_container_width=True, key="btn_discard_prev"):
                    if ext_stats.get("job_id"):
                        db.clear_ocr_job(ext_stats["job_id"])
                    st.session_state["extracted_mock_preview"] = None
                    st.rerun()

    # =========================================================================
    # Tab 3: 10-Year Official PYQ Bank
    # =========================================================================
    with tab_pyqs:
        pyq_subset = db.list_questions(source_type="Official PYQ")
        st.subheader(f"🏛️ 10-Year BPSC Official PYQ Vault ({len(pyq_subset)} Authentic Questions · 60th to 70th CCE)")
        st.write("Browse and filter authentic BPSC questions from official examination papers across the last 10 years.")

        if not pyq_subset.empty:
            ed_counts = pyq_subset["exam_edition"].value_counts().to_dict()
            p_row1 = st.columns(5)
            ed_keys_1 = [
                ("70th BPSC (2024)", "70th BPSC CCE Prelims"),
                ("69th BPSC (2023)", "69th BPSC CCE Prelims"),
                ("68th BPSC (2023)", "68th BPSC CCE Prelims"),
                ("67th BPSC (2022)", "67th BPSC CCE Re-Exam"),
                ("66th BPSC (2020)", "66th BPSC CCE Prelims"),
            ]
            for idx, (short_l, full_e) in enumerate(ed_keys_1):
                p_row1[idx].metric(short_l, f"{ed_counts.get(full_e, 0)} Qs")

            p_row2 = st.columns(4)
            ed_keys_2 = [
                ("65th BPSC (2019)", "65th BPSC CCE Prelims"),
                ("64th BPSC (2018)", "64th BPSC CCE Prelims"),
                ("63rd BPSC (2018)", "63rd BPSC CCE Prelims"),
                ("60-62nd BPSC (2017)", "60th-62nd BPSC CCE Prelims"),
            ]
            for idx, (short_l, full_e) in enumerate(ed_keys_2):
                p_row2[idx].metric(short_l, f"{ed_counts.get(full_e, 0)} Qs")

            st.divider()

            # PYQ Specific Filters
            pyq_c1, pyq_c2, pyq_c3, pyq_c4 = st.columns([1.5, 1.2, 1.2, 1.5])
            pyq_editions = ["All 10-Year Editions"] + sorted([e for e in pyq_subset["exam_edition"].dropna().unique().tolist() if e.strip()])
            sel_pyq_ed = pyq_c1.selectbox("Exam Edition", pyq_editions, key="pyq_tab_ed")

            pyq_subjs = ["All"] + sorted(pyq_subset["subject"].dropna().unique().tolist())
            sel_pyq_subj = pyq_c2.selectbox("Subject", pyq_subjs, key="pyq_tab_subj")

            interim_pyq = pyq_subset if sel_pyq_subj == "All" else pyq_subset[pyq_subset["subject"] == sel_pyq_subj]
            pyq_topics = ["All"] + sorted(interim_pyq["topic"].dropna().unique().tolist())
            sel_pyq_topic = pyq_c3.selectbox("Topic", pyq_topics, key="pyq_tab_top")

            pyq_kw = pyq_c4.text_input("Search PYQs", placeholder="e.g. Kunwar Singh, Champaran...", key="pyq_tab_kw")

            f_pyq = pyq_subset.copy()
            if sel_pyq_ed != "All 10-Year Editions":
                f_pyq = f_pyq[f_pyq["exam_edition"] == sel_pyq_ed]
            if sel_pyq_subj != "All":
                f_pyq = f_pyq[f_pyq["subject"] == sel_pyq_subj]
            if sel_pyq_topic != "All":
                f_pyq = f_pyq[f_pyq["topic"] == sel_pyq_topic]
            if pyq_kw.strip():
                kw_p = pyq_kw.strip().lower()
                f_pyq = f_pyq[
                    f_pyq["question"].str.lower().str.contains(kw_p, na=False)
                    | f_pyq["topic"].str.lower().str.contains(kw_p, na=False)
                    | f_pyq["explanation"].str.lower().str.contains(kw_p, na=False)
                ]

            p_act1, p_act2 = st.columns([3, 1])
            p_act1.caption(f"Showing **{len(f_pyq)}** authentic PYQs.")
            if not f_pyq.empty and p_act2.button("🎯 Practice Filtered PYQs", type="primary", use_container_width=True, key="btn_pyq_drill"):
                p_ids = f_pyq["id"].astype(int).tolist()
                chosen_p = random.sample(p_ids, k=min(25, len(p_ids)))
                st.session_state["active_test"] = {
                    "session_id": str(uuid.uuid4())[:8],
                    "question_ids": chosen_p,
                    "exam": "BPSC",
                    "test_mode": f"Official PYQ Drill ({sel_pyq_ed if sel_pyq_ed != 'All 10-Year Editions' else '10-Year Multi-Edition'})",
                    "ui_style": "Interactive OMR Palette",
                    "instant_feedback": True,
                    "negative_rate": 0.33,
                    "start_time": time.time(),
                    "current_index": 0,
                    "answers": {},
                    "confidences": {},
                    "marked_review": [],
                    "question_times": {},
                    "last_q_timestamp": time.time(),
                }
                st.session_state["test_results"] = None
                navigate_to("Practice & Mock Tests")

            # PYQ table & cards (bounded preview for high performance)
            disp_pyq_cols = ["id", "exam_edition", "exam_year", "paper_set", "official_qno", "subject", "topic", "question", "correct_option", "answer_key_status"]
            avail_pyq_cols = [c for c in disp_pyq_cols if c in f_pyq.columns]
            st.dataframe(f_pyq[avail_pyq_cols].head(150), use_container_width=True, hide_index=True)
            if len(f_pyq) > 150:
                st.caption(f"⚡ Showing first 150 rows in the preview grid for high performance. Browse all {len(f_pyq)} questions via the cards below.")

            with st.expander("🔍 Browse Official PYQ Cards (Paginated)", expanded=True):
                if f_pyq.empty:
                    st.info("No PYQs match the current filters.")
                else:
                    pyq_page_size = 10
                    pyq_total_pages = max(1, (len(f_pyq) + pyq_page_size - 1) // pyq_page_size)
                    pyqp_col1, _ = st.columns([1, 3])
                    pyq_page_num = pyqp_col1.number_input(
                        f"Page (1 to {pyq_total_pages})", min_value=1, max_value=pyq_total_pages, value=1, step=1, key="pyq_page_ctrl"
                    )
                    pyq_start_idx = (pyq_page_num - 1) * pyq_page_size
                    pyq_slice = f_pyq.iloc[pyq_start_idx : pyq_start_idx + pyq_page_size]

                    for _, q_row in pyq_slice.iterrows():
                        _render_question_card_view(q_row, show_actions=True, key_prefix="pyq_bank")
        else:
            st.info("No Official PYQs loaded in database.")

    # =========================================================================
    # Tab 4: All Questions Vault (Unified Browser)
    # =========================================================================
    with tab_all:
        st.subheader("🔍 All Questions Vault")
        st.write("Unified cross-category browser covering Official PYQs, Mock Questions, AI Drills, and Practice Sets.")

        total_vault_count = db.count_questions()
        if total_vault_count == 0:
            st.info("Your question bank is empty. Add a question or import a CSV.")
        else:
            c1, c2, c3, c4, c5, c6, c7 = st.columns([1, 1.2, 1.2, 1.3, 1.1, 0.9, 1.4])
            exam_filter = c1.selectbox("Exam", ["All", "BPSC", "UPSC"], key="qb_exam")
            subjects = ["All"] + db.get_distinct_subjects(exam=exam_filter)
            subject_filter = c2.selectbox("Subject", subjects, key="qb_subj")

            topics = ["All"] + db.get_distinct_topics(subject=subject_filter if subject_filter != "All" else None, exam=exam_filter)
            topic_filter = c3.selectbox("Topic", topics, key="qb_top")

            editions_list = ["All"] + db.get_distinct_editions()
            edition_filter = c4.selectbox("Exam Edition", editions_list, key="qb_ed")

            src_choices = ["All", "Official PYQ", "Mock question", "Built-in sample", "AI-generated", "User-added"]
            source_filter = c5.selectbox("Provenance", src_choices, key="qb_src")
            diff_filter = c6.selectbox("Difficulty", ["All", "Easy", "Medium", "Hard"], key="qb_diff")
            search_query = c7.text_input("Search Keyword", placeholder="e.g. Patna, Kunwar Singh...", key="all_kw")

            only_pinned = st.checkbox("📌 Show Pinned Questions Only", value=False, key="qb_only_pinned")

            filtered = db.list_questions(exam_filter, subject_filter, topic_filter, source_filter)
            if edition_filter != "All" and "exam_edition" in filtered.columns:
                filtered = filtered[filtered["exam_edition"] == edition_filter]
            if diff_filter != "All" and "difficulty" in filtered.columns:
                filtered = filtered[filtered["difficulty"] == diff_filter]

            if only_pinned and not filtered.empty:
                pinned_ids = db.get_pinned_question_ids()
                filtered = filtered[filtered["id"].astype(int).isin(pinned_ids)]

            if search_query.strip():
                term = search_query.strip().lower()
                filtered = filtered[
                    filtered["question"].str.lower().str.contains(term, na=False)
                    | filtered["topic"].str.lower().str.contains(term, na=False)
                    | filtered["explanation"].str.lower().str.contains(term, na=False)
                ]

            act_c1, act_c2 = st.columns([3, 1])
            act_c1.caption(f"Showing **{len(filtered)}** of **{total_vault_count}** total question(s).")
            if not filtered.empty and act_c2.button("🎯 Practice Filtered Set", use_container_width=True, key="btn_all_practice"):
                f_ids = filtered["id"].astype(int).tolist()
                chosen = random.sample(f_ids, k=min(15, len(f_ids)))
                st.session_state["active_test"] = {
                    "session_id": str(uuid.uuid4())[:8],
                    "question_ids": chosen,
                    "exam": exam_filter if exam_filter != "All" else "BPSC",
                    "test_mode": "Filtered Question Bank Drill",
                    "ui_style": "Interactive OMR Palette",
                    "instant_feedback": True,
                    "negative_rate": 0.33,
                    "start_time": time.time(),
                    "current_index": 0,
                    "answers": {},
                    "confidences": {},
                    "marked_review": [],
                    "question_times": {},
                    "last_q_timestamp": time.time(),
                }
                st.session_state["test_results"] = None
                navigate_to("Practice & Mock Tests")

            disp_cols = [
                "id",
                "source_type",
                "source_name",
                "exam_edition",
                "exam_year",
                "subject",
                "topic",
                "question",
                "correct_option",
                "difficulty",
                "answer_key_status",
            ]
            available_cols = [c for c in disp_cols if c in filtered.columns]
            st.dataframe(filtered[available_cols].head(150), use_container_width=True, hide_index=True)
            if len(filtered) > 150:
                st.caption(f"⚡ Showing first 150 rows in the preview grid for high performance. Browse all {len(filtered)} questions via the cards below.")

            with st.expander("🔍 Browse Detailed Question Cards (Paginated)", expanded=True):
                if filtered.empty:
                    st.info("No questions match the current filters.")
                else:
                    page_size = 10
                    total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
                    p_col1, p_col2 = st.columns([1, 3])
                    page_num = p_col1.number_input(
                        f"Page (1 to {total_pages})", min_value=1, max_value=total_pages, value=1, step=1, key="all_page_ctrl"
                    )
                    start_idx = (page_num - 1) * page_size
                    page_slice = filtered.iloc[start_idx : start_idx + page_size]

                    for _, q_row in page_slice.iterrows():
                        _render_question_card_view(q_row, show_actions=True, key_prefix="all_bank")

            st.divider()
            col_exp1, col_exp2 = st.columns(2)
            with col_exp1:
                csv_bytes = filtered.to_csv(index=False).encode("utf-8")
                st.download_button(
                    f"⬇️ Export Current View ({len(filtered)} Qs) to CSV",
                    data=csv_bytes,
                    file_name="bpsc_question_bank_export.csv",
                    mime="text/csv",
                    use_container_width=True,
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
                        use_container_width=True,
                    )

    # =========================================================================
    # Tab 5: Add Manually & CSV Import
    # =========================================================================
    with tab_add_csv:
        st.subheader("➕ Add Questions Manually or Bulk Import CSV")
        top_col1, top_col2 = st.columns(2)

        with top_col1:
            with st.container(border=True):
                st.markdown("#### 📥 Import Questions from CSV")
                upload = st.file_uploader(
                    "Upload CSV file",
                    type=["csv"],
                    help="Template columns: exam, subject, topic, question, option_a, option_b, option_c, option_d, correct_option",
                    key="tab_csv_uploader",
                )
                if upload is not None and st.button("Import Uploaded CSV", type="primary", key="btn_import_csv"):
                    inserted, problems = db.import_csv(upload)
                    st.success(f"Successfully imported {inserted} question(s).")
                    for prob in problems[:10]:
                        st.warning(prob)
                    if len(problems) > 10:
                        st.caption(f"{len(problems) - 10} additional messages not shown.")
                    st.rerun()

        with top_col2:
            with st.container(border=True):
                st.markdown("#### ➕ Add Custom Question Manually")
                with st.form("manual_add_question_form", clear_on_submit=True):
                    mc1, mc2, mc3 = st.columns(3)
                    m_exam = mc1.selectbox("Exam", ["BPSC", "UPSC"], index=0)
                    m_subj = mc2.selectbox("Subject", db.SUBJECTS, index=0)
                    m_diff = mc3.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=1)

                    mc4, mc5, mc6 = st.columns(3)
                    m_topic = mc4.text_input("Topic*", placeholder="e.g. Champaran Satyagraha")
                    m_src = mc5.selectbox("Source Type", ["User-added", "Official PYQ", "Mock question", "Built-in sample"], index=0)
                    m_edition = mc6.text_input("Exam Edition / Source Title", placeholder="e.g. 69th BPSC Prelims")

                    m_qtext = st.text_area("Question Stem*", placeholder="Enter the full question text...")
                    mo1, mo2 = st.columns(2)
                    m_oa = mo1.text_input("Option A*")
                    m_ob = mo2.text_input("Option B*")
                    m_oc = mo1.text_input("Option C*")
                    m_od = mo2.text_input("Option D*")

                    mc_cor, mc_year = st.columns([2, 1])
                    m_cor = mc_cor.radio("Correct Option*", ["A", "B", "C", "D"], horizontal=True)
                    m_year = mc_year.number_input("Exam Year (optional)", min_value=1990, max_value=2030, value=2025)
                    m_exp = st.text_area("Detailed Explanation", placeholder="Why is this option correct and why are others wrong?")

                    if st.form_submit_button("💾 Save Question to Bank", type="primary"):
                        if not (m_qtext.strip() and m_oa.strip() and m_ob.strip() and m_oc.strip() and m_od.strip()):
                            st.error("Please fill in the question stem and all four options (A, B, C, D).")
                        else:
                            db.add_question({
                                "exam": m_exam,
                                "subject": m_subj,
                                "topic": m_topic.strip() or "General",
                                "question": m_qtext.strip(),
                                "option_a": m_oa.strip(),
                                "option_b": m_ob.strip(),
                                "option_c": m_oc.strip(),
                                "option_d": m_od.strip(),
                                "correct_option": m_cor,
                                "explanation": m_exp.strip(),
                                "source_type": m_src,
                                "source_name": m_edition.strip(),
                                "exam_edition": m_edition.strip(),
                                "exam_year": int(m_year) if m_src == "Official PYQ" else None,
                                "difficulty": m_diff,
                                "is_ai_generated": 0,
                            })
                            st.success("Question added to your Question Bank!")
                            st.rerun()


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
        "Indian National Congress Sessions (Gaya 1922, Bankipore 1912)",
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
        "Wetlands & Ramsar Sites (Kabartal, Nagi-Nakti)",
        "Biodiversity Hotspots & Wildlife Conservation",
        "Global Climate Treaties & Environmental Conventions",
    ],
    "Ancient & Medieval History": [
        "Indus Valley & Vedic Period",
        "Rise of Magadha & Mauryan Administration",
        "Buddhist & Jain Councils in Bihar",
        "Gupta Golden Age & Nalanda/Vikramshila University",
        "Medieval Sultans, Sher Shah Suri & Mughals in Bihar",
    ],
    "Other": [
        "General Mental Ability & Quantitative Aptitude",
    ],
}


def show_question_studio() -> None:
    """Dedicated studio to generate, inspect, edit, and save authentic-style questions."""
    st.title("✨ AI Question Studio")
    st.write(
        "Generate authentic, syllabus-aligned practice questions for BPSC and UPSC Prelims. "
        "Questions are calibrated against verified PYQ benchmarks and never falsified as official PYQs."
    )

    if not config.is_gemini_configured():
        st.warning(
            "⚠️ Gemini API is not configured. Please add `GEMINI_API_KEY` to your environment to enable AI generation."
        )
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
            topic = c4.text_input(
                "Enter Custom Topic",
                value="",
                placeholder="e.g. Endocrine system",
                key=f"custom_topic_text_{subject}",
            )
            if not topic.strip():
                topic = suggestions[0]
        else:
            topic = chosen_preset

        subtopic = c5.text_input(
            "Subtopic / Theme (Optional)",
            placeholder="e.g. Key mechanisms, dates, or constitutional articles",
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
            index=1,
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
            placeholder="Paste excerpts from NCERTs, Bihar Economic Survey, or lecture notes here...",
            height=100,
        )

        available_exemplars = db.retrieve_pyq_exemplars(
            subject=subject,
            topic=topic.strip() or "General",
            exam=exam,
            limit=5,
        )
        if available_exemplars:
            exemplar_editions = ", ".join(
                sorted(
                    {
                        ex.get("exam_edition", "BPSC PYQ")
                        for ex in available_exemplars
                        if ex.get("exam_edition")
                    }
                )
            )
            st.caption(
                f"🏛️ **Strict BPSC Benchmark Active**: Retrieved **{len(available_exemplars)}** genuine PYQ benchmark(s) "
                f"({exemplar_editions}) to calibrate authentic exam depth, multi-statement phrasing, and distractor plausibility."
            )
            with st.expander(f"🔍 Inspect {len(available_exemplars)} Retrieved BPSC Benchmark PYQs", expanded=False):
                for e_idx, ex in enumerate(available_exemplars, 1):
                    st.markdown(f"**Benchmark #{e_idx}** ({ex.get('exam_edition', 'BPSC PYQ')} · `{ex.get('subject', '')}` → `{ex.get('topic', '')}`)")
                    st.write(f"*{ex.get('question', '')}*")
                    st.caption(f"Official Answer: `{ex.get('correct_option', '')}` · Concept: {ex.get('concept_tested', 'Syllabus core')}")
                    if e_idx < len(available_exemplars):
                        st.divider()

        if st.button("✨ Generate Calibrated Questions", type="primary"):
            with st.spinner("Retrieving BPSC PYQs and generating calibrated exam questions..."):
                try:
                    for k in list(st.session_state.keys()):
                        if k.startswith("sq_"):
                            del st.session_state[k]

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
                    st.success(
                        f"Generated {len(q_set.questions)} question(s) on '{subject} - {topic}' strictly calibrated against "
                        f"{len(q_set.retrieved_exemplars)} genuine BPSC Prelims PYQs!"
                    )
                except Exception as exc:
                    st.error(f"Generation error: {exc}")

    # 2. Preview, Edit & Save Area
    studio_items = st.session_state.get("studio_questions")
    if studio_items:
        st.subheader("2. Review, Edit & Practice Generated Set")

        exemplars = st.session_state.get("studio_exemplars", [])
        if exemplars:
            with st.expander(
                f"🏛️ View {len(exemplars)} Genuine BPSC Prelims PYQ Benchmarks Used for Generation",
                expanded=False,
            ):
                for ex in exemplars:
                    st.markdown(
                        f"**{ex.get('exam_edition', 'BPSC PYQ')}** (Q.{ex.get('official_qno', '-')}) · *{ex.get('subject')} · {ex.get('topic')}*"
                    )
                    st.markdown(f"> **{ex.get('question')}**")
                    st.caption(
                        f"Correct: **{ex.get('correct_option')}** · {ex.get('explanation', '')[:160]}..."
                    )
                    st.divider()

        st.info(
            "💡 Edit any stem, option, or explanation below before saving to your Question Bank or launching an instant drill."
        )

        gen_id = st.session_state.get("studio_gen_id", 0)
        questions_to_save: List[Dict[str, Any]] = []
        for i, q in enumerate(studio_items):
            with st.expander(f"Question {i+1}: {q['question'][:85]}...", expanded=True):
                q_text = st.text_area(
                    f"Question #{i+1}", value=q["question"], key=f"sq_text_{gen_id}_{i}"
                )
                o1, o2 = st.columns(2)
                oa = o1.text_input("Option A", value=q["option_a"], key=f"sq_oa_{gen_id}_{i}")
                ob = o2.text_input("Option B", value=q["option_b"], key=f"sq_ob_{gen_id}_{i}")
                oc = o1.text_input("Option C", value=q["option_c"], key=f"sq_oc_{gen_id}_{i}")
                od = o2.text_input("Option D", value=q["option_d"], key=f"sq_od_{gen_id}_{i}")

                curr_idx = (
                    ["A", "B", "C", "D"].index(q["correct_option"])
                    if q["correct_option"] in ["A", "B", "C", "D"]
                    else 0
                )
                correct_opt = st.radio(
                    "Correct Answer",
                    ["A", "B", "C", "D"],
                    index=curr_idx,
                    horizontal=True,
                    key=f"sq_cor_{gen_id}_{i}",
                )

                exp_text = st.text_area(
                    "Explanation", value=q.get("explanation", ""), key=f"sq_exp_{gen_id}_{i}"
                )
                dist_text = st.text_input(
                    "Distractor Notes",
                    value=q.get("distractor_notes", ""),
                    key=f"sq_dist_{gen_id}_{i}",
                )
                concept_tested = st.text_input(
                    "Concept Tested",
                    value=q.get("concept_tested", ""),
                    key=f"sq_con_{gen_id}_{i}",
                )

                questions_to_save.append(
                    {
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
                    }
                )

        col_save, col_save_practice, col_clear = st.columns([2, 2, 1])
        if col_save.button("💾 Save All to Question Bank", type="primary", use_container_width=True):
            for item in questions_to_save:
                db.add_question(item)
            st.success(f"Saved {len(questions_to_save)} questions into your Question Bank!")
            st.session_state["studio_questions"] = None
            for k in list(st.session_state.keys()):
                if k.startswith("sq_"):
                    del st.session_state[k]
            st.rerun()

        if col_save_practice.button("🚀 Save & Practice This Set Now", use_container_width=True):
            new_ids = []
            for item in questions_to_save:
                qid = db.add_question(item)
                if qid:
                    new_ids.append(int(qid))
            st.session_state["studio_questions"] = None
            for k in list(st.session_state.keys()):
                if k.startswith("sq_"):
                    del st.session_state[k]
            if new_ids:
                st.session_state["active_test"] = {
                    "session_id": str(uuid.uuid4())[:8],
                    "question_ids": new_ids,
                    "exam": exam if exam != "Both" else "BPSC",
                    "test_mode": "AI Studio Custom Drill",
                    "ui_style": "Interactive OMR Palette",
                    "instant_feedback": True,
                    "negative_rate": 0.33,
                    "start_time": time.time(),
                    "current_index": 0,
                    "answers": {},
                    "confidences": {},
                    "marked_review": [],
                    "question_times": {},
                    "last_q_timestamp": time.time(),
                }
                st.session_state["test_results"] = None
                navigate_to("Practice & Mock Tests")

        if col_clear.button("🗑️ Discard", use_container_width=True):
            st.session_state["studio_questions"] = None
            for k in list(st.session_state.keys()):
                if k.startswith("sq_"):
                    del st.session_state[k]
            st.rerun()


# -----------------------------------------------------------------------------
# Views: 4. Practice & Mock Tests (Overhauled with Interactive OMR & Metacognition)
# -----------------------------------------------------------------------------

def finalize_test_submission(
    active_test: Dict[str, Any],
    q_frame: pd.DataFrame,
    answers: Dict[int, str],
    confidences: Dict[int, str],
    question_times: Optional[Dict[int, float]] = None,
) -> None:
    """Grade test session, record attempts with per-question timing, and store full option maps."""
    total_time_spent = max(0.1, round(time.time() - active_test["start_time"], 1))
    results_items = []
    correct_cnt = 0
    incorrect_cnt = 0
    unanswered_cnt = 0
    total_score = 0.0
    question_times = question_times or {}
    fallback_per_q_time = round(total_time_spent / max(1, len(q_frame)), 1)

    for _, row in q_frame.iterrows():
        qid = int(row["id"])
        chosen = answers.get(qid, "-")
        correct = str(row["correct_option"]).strip()
        is_correct = chosen == correct
        confidence = confidences.get(qid, "Medium")
        q_time = round(question_times.get(qid, fallback_per_q_time), 1)

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

        db.record_attempt(
            question_id=qid,
            selected_option=chosen,
            correct_option=correct,
            test_session_id=active_test["session_id"],
            time_spent_seconds=q_time,
            confidence_rating=confidence,
            score=q_score,
        )

        opts = {
            "A": str(row["option_a"]),
            "B": str(row["option_b"]),
            "C": str(row["option_c"]),
            "D": str(row["option_d"]),
        }
        results_items.append(
            {
                "question_id": qid,
                "question": row["question"],
                "options": opts,
                "selected_option": chosen,
                "selected_text": opts.get(chosen, "Not answered"),
                "is_correct": is_correct,
                "correct_option": correct,
                "correct_text": opts.get(correct, ""),
                "explanation": row.get("explanation", ""),
                "distractor_notes": row.get("distractor_notes", ""),
                "subject": row["subject"],
                "topic": row["topic"],
                "confidence": confidence,
                "time_spent": q_time,
                "score": q_score,
            }
        )

    db.record_test_session(
        session_id=active_test["session_id"],
        exam=active_test["exam"],
        test_mode=active_test["test_mode"],
        total_questions=len(q_frame),
        correct_count=correct_cnt,
        incorrect_count=incorrect_cnt,
        unanswered_count=unanswered_cnt,
        negative_mark_rate=active_test["negative_rate"],
        total_score=round(total_score, 2),
        time_spent_seconds=total_time_spent,
    )

    st.session_state["test_results"] = {
        "session_id": active_test["session_id"],
        "test_mode": active_test["test_mode"],
        "negative_rate": active_test["negative_rate"],
        "items": results_items,
        "total_score": round(total_score, 2),
        "time_spent": total_time_spent,
    }
    st.session_state["active_test"] = None


def show_practice() -> None:
    """Examination engine supporting interactive OMR palette, full sheet mode, and metacognitive scorecards."""
    st.title("📝 Practice & Mock Tests")
    st.caption(
        "Interactive OMR Question Palette, BPSC 1/3rd negative marking simulation, confidence calibration, and instant mistake remediation."
    )

    results = st.session_state.get("test_results")
    active_test = st.session_state.get("active_test")

    # -------------------------------------------------------------------------
    # A. Display Test Scorecard & Metacognitive Review if Test Just Finished
    # -------------------------------------------------------------------------
    if results is not None:
        items = results["items"]
        total = len(items)
        correct = sum(1 for r in items if r["is_correct"])
        incorrect = sum(1 for r in items if not r["is_correct"] and r["selected_option"] != "-")
        unanswered = sum(1 for r in items if r["selected_option"] == "-")
        attempted = correct + incorrect
        accuracy = round(correct / attempted * 100, 1) if attempted > 0 else 0.0
        penalty_lost = round(incorrect * float(results.get("negative_rate", 0.0)), 2)

        # Performance Headline Banner
        if accuracy >= 70:
            st.markdown(
                """
                <div style="background: radial-gradient(circle at 10% 20%, rgba(16, 185, 129, 0.25) 0%, transparent 60%), linear-gradient(135deg, #064e3b 0%, #047857 60%, #022c22 100%); color: white; padding: 22px 28px; border-radius: 18px; margin-bottom: 22px; border: 1px solid rgba(16, 185, 129, 0.45); box-shadow: 0 10px 30px -5px rgba(6, 78, 59, 0.4);">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                        <span style="background: rgba(16, 185, 129, 0.3); border: 1px solid #10b981; color: #a7f3d0; font-size: 11px; font-weight: 700; padding: 2px 10px; border-radius: 999px; text-transform: uppercase;">Top Tier Calibrated</span>
                    </div>
                    <h3 style="color: white; margin: 0 0 4px 0; font-family: 'Outfit', sans-serif; font-size: 24px;">🎉 Outstanding Performance!</h3>
                    <p style="margin: 0; color: #d1fae5; font-size: 14.5px;">Exceptional conceptual precision and distractor resistance. Review distractor traps and calibration telemetry below.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        elif accuracy >= 50:
            st.markdown(
                """
                <div style="background: radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.25) 0%, transparent 60%), linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 60%, #0f172a 100%); color: white; padding: 22px 28px; border-radius: 18px; margin-bottom: 22px; border: 1px solid rgba(59, 130, 246, 0.45); box-shadow: 0 10px 30px -5px rgba(30, 58, 138, 0.4);">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                        <span style="background: rgba(59, 130, 246, 0.3); border: 1px solid #60a5fa; color: #bfdbfe; font-size: 11px; font-weight: 700; padding: 2px 10px; border-radius: 999px; text-transform: uppercase;">On Track</span>
                    </div>
                    <h3 style="color: white; margin: 0 0 4px 0; font-family: 'Outfit', sans-serif; font-size: 24px;">👍 Solid Practice Drill!</h3>
                    <p style="margin: 0; color: #dbeafe; font-size: 14.5px;">Good performance. Pay close attention to nuanced distractors and elimination techniques below.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div style="background: radial-gradient(circle at 10% 20%, rgba(239, 68, 68, 0.25) 0%, transparent 60%), linear-gradient(135deg, #7f1d1d 0%, #b91c1c 60%, #450a0a 100%); color: white; padding: 22px 28px; border-radius: 18px; margin-bottom: 22px; border: 1px solid rgba(239, 68, 68, 0.45); box-shadow: 0 10px 30px -5px rgba(127, 29, 29, 0.4);">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                        <span style="background: rgba(239, 68, 68, 0.3); border: 1px solid #f87171; color: #fecaca; font-size: 11px; font-weight: 700; padding: 2px 10px; border-radius: 999px; text-transform: uppercase;">Needs Remediation</span>
                    </div>
                    <h3 style="color: white; margin: 0 0 4px 0; font-family: 'Outfit', sans-serif; font-size: 24px;">⚠️ Targeted Remediation Needed</h3>
                    <p style="margin: 0; color: #fee2e2; font-size: 14.5px;">Conceptual gaps detected. Use the 'Explain My Mistake with AI Tutor' button on missed questions below.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        sc1, sc2, sc3, sc4, sc5, sc6 = st.columns(6)
        sc1.metric("Net Score", f"{results['total_score']:.2f} / {total}")
        sc2.metric("Attempt Accuracy", f"{accuracy}%")
        sc3.metric("Correct (+1.0)", correct)
        sc4.metric("Incorrect", f"{incorrect} (-{penalty_lost:.2f})")
        sc5.metric("Skipped", unanswered)
        sc6.metric("Total Time", format_duration(results.get("time_spent", 0.0)))

        # Metacognitive Confidence Breakdown on Scorecard
        with st.expander("🧠 Metacognitive Confidence & Negative-Marking Calibration", expanded=True):
            conf_rows = []
            for c_lvl in ["High", "Medium", "Guess"]:
                c_sub = [r for r in items if r.get("confidence", "Medium") == c_lvl and r["selected_option"] != "-"]
                if c_sub:
                    c_corr = sum(1 for r in c_sub if r["is_correct"])
                    c_wrong = len(c_sub) - c_corr
                    c_net = round(sum(float(r.get("score", 0.0)) for r in c_sub), 2)
                    conf_rows.append({
                        "Confidence Tier": c_lvl,
                        "Attempted": len(c_sub),
                        "Correct": c_corr,
                        "Wrong": c_wrong,
                        "Accuracy (%)": round(c_corr / len(c_sub) * 100, 1),
                        "Net Score Impact": f"{c_net:+0.2f}",
                    })
            if conf_rows:
                st.dataframe(pd.DataFrame(conf_rows), use_container_width=True, hide_index=True)
                blind_spots = [
                    r for r in items if not r["is_correct"] and r["selected_option"] != "-" and r.get("confidence") == "High"
                ]
                if blind_spots:
                    st.warning(
                        f"⚠️ **Blind Spot Alert:** You answered **{len(blind_spots)}** question(s) incorrectly despite marking **High Confidence**. Review these first below!"
                    )

        st.divider()

        # Filterable Detailed Review per Question
        rev_filter = st.radio(
            "Filter Question Review:",
            ["All Questions", "❌ Incorrect Only", "⚠️ High-Confidence Mistakes", "⏭️ Unanswered Only"],
            horizontal=True,
        )

        for idx, res in enumerate(items, start=1):
            if rev_filter == "❌ Incorrect Only" and (res["is_correct"] or res["selected_option"] == "-"):
                continue
            if rev_filter == "⚠️ High-Confidence Mistakes" and (
                res["is_correct"] or res["selected_option"] == "-" or res.get("confidence") != "High"
            ):
                continue
            if rev_filter == "⏭️ Unanswered Only" and res["selected_option"] != "-":
                continue

            status = (
                "✅ Correct"
                if res["is_correct"]
                else ("⚠️ Unanswered" if res["selected_option"] == "-" else "❌ Incorrect")
            )
            conf_badge = f"Confidence: {res.get('confidence', 'Medium')} · ⏱️ {res.get('time_spent', 0)}s"
            with st.expander(
                f"{status} | Q.{idx} ({res['subject']} · {res['topic']}) — {res['question'][:70]}...",
                expanded=not res["is_correct"],
            ):
                st.caption(conf_badge)
                st.markdown(f"**{res['question']}**")
                opts_dict = res.get("options") or get_question_options_map(int(res["question_id"]))
                for opt_k in ["A", "B", "C", "D"]:
                    prefix = ""
                    if opt_k == res["correct_option"]:
                        prefix = "✅ "
                    elif opt_k == res["selected_option"] and not res["is_correct"]:
                        prefix = "❌ "
                    st.write(f"{prefix}**{opt_k}.** {opts_dict.get(opt_k, '')}")

                col_ans1, col_ans2 = st.columns(2)
                with col_ans1:
                    ans_color = "#166534" if res["is_correct"] else "#991b1b"
                    st.markdown(
                        f"<div style='padding: 8px 12px; background: rgba(248, 250, 252, 0.8); border-radius: 8px;'><b>Your Selection:</b> <span style='color: {ans_color}; font-weight: 700;'>{res['selected_option']}. {res['selected_text']}</span></div>",
                        unsafe_allow_html=True,
                    )
                with col_ans2:
                    st.markdown(
                        f"<div style='padding: 8px 12px; background: rgba(240, 253, 244, 0.8); border: 1px solid #bbf7d0; border-radius: 8px;'><b>Official Key:</b> <span style='color: #166534; font-weight: 700;'>{res['correct_option']}. {res['correct_text']}</span></div>",
                        unsafe_allow_html=True,
                    )

                if res.get("explanation"):
                    st.info(f"💡 **Detailed Explanation:**\n\n{res['explanation']}")
                if res.get("distractor_notes"):
                    st.warning(f"⚠️ **Distractor Trap Analysis:**\n\n{res['distractor_notes']}")

                act1, act2 = st.columns(2)
                qid = int(res["question_id"])
                is_pinned = db.is_question_pinned(qid)
                if act1.button(
                    "📌 Unpin from Vault" if is_pinned else "📍 Pin Question to Revision Vault",
                    key=f"res_pin_{idx}_{qid}",
                ):
                    if is_pinned:
                        db.unpin_question(qid)
                    else:
                        db.pin_question(qid, note=f"Pinned after test session {results.get('session_id', '')}")
                    st.rerun()

                if not res["is_correct"] and config.is_gemini_configured():
                    if act2.button(
                        "🔍 Explain My Mistake with AI Tutor",
                        key=f"tutor_ask_{idx}",
                        type="primary",
                    ):
                        res["options"] = opts_dict
                        st.session_state["tutor_context_question"] = res
                        navigate_to("AI Study Tutor")

        b_new, b_retry = st.columns(2)
        if b_new.button("🚀 Configure Another Test", type="primary", use_container_width=True):
            st.session_state["test_results"] = None
            st.session_state["active_test"] = None
            st.rerun()
        wrong_ids = [int(r["question_id"]) for r in items if not r["is_correct"]]
        if wrong_ids and b_retry.button(
            f"🔁 Immediately Retry {len(wrong_ids)} Missed/Skipped Question(s)",
            use_container_width=True,
        ):
            st.session_state["active_test"] = {
                "session_id": str(uuid.uuid4())[:8],
                "question_ids": wrong_ids,
                "exam": "BPSC",
                "test_mode": "Immediate Mistake Retry",
                "ui_style": "Interactive OMR Palette",
                "instant_feedback": True,
                "negative_rate": float(results.get("negative_rate", 0.33)),
                "start_time": time.time(),
                "current_index": 0,
                "answers": {},
                "confidences": {},
                "marked_review": [],
                "question_times": {},
                "last_q_timestamp": time.time(),
            }
            st.session_state["test_results"] = None
            st.rerun()
        return

    # -------------------------------------------------------------------------
    # B. Active Test Interface (Interactive OMR Palette OR Full-Sheet Form)
    # -------------------------------------------------------------------------
    if active_test:
        q_frame = db.get_questions_by_ids(active_test["question_ids"])
        if q_frame.empty:
            st.error("Unable to load questions for this test session.")
            st.session_state["active_test"] = None
            return

        ui_style = active_test.get("ui_style", "Interactive OMR Palette")
        elapsed = time.time() - active_test["start_time"]
        target_seconds = len(q_frame) * 60

        # Header Bar with Live Clock & Abort Button
        hdr1, hdr2, hdr3 = st.columns([3, 1.5, 1])
        hdr1.subheader(f"📝 {active_test['test_mode']} · {len(q_frame)} Questions")
        if "Timed" in active_test["test_mode"] or "Mock" in active_test["test_mode"]:
            rem_sec = target_seconds - elapsed
            if rem_sec > 0:
                hdr2.metric("⏳ Remaining Time", format_duration(rem_sec))
            else:
                hdr2.warning(f"⏰ Overtime: +{format_duration(abs(rem_sec))}")
        else:
            hdr2.metric("⏱️ Elapsed Time", format_duration(elapsed))

        if hdr3.button("🛑 Abort Test", use_container_width=True):
            st.session_state["active_test"] = None
            st.rerun()

        # Mode 1: Interactive OMR Palette (One-by-One Question Navigation)
        if ui_style == "Interactive OMR Palette":
            answers: Dict[int, str] = active_test.setdefault("answers", {})
            confidences: Dict[int, str] = active_test.setdefault("confidences", {})
            marked_review: List[int] = active_test.setdefault("marked_review", [])
            q_times: Dict[int, float] = active_test.setdefault("question_times", {})
            curr_idx: int = int(active_test.get("current_index", 0))
            curr_idx = max(0, min(curr_idx, len(q_frame) - 1))

            row = q_frame.iloc[curr_idx]
            qid = int(row["id"])

            def update_q_timer(current_qid: int) -> None:
                now = time.time()
                last_ts = active_test.get("last_q_timestamp", now)
                q_times[current_qid] = q_times.get(current_qid, 0.0) + max(0.0, now - last_ts)
                active_test["last_q_timestamp"] = now

            col_q, col_omr = st.columns([2.7, 1.3])

            with col_q:
                with st.container(border=True):
                    if row.get("source_type") == "Official PYQ":
                        q_badge_cls = "badge-pyq"
                        q_badge_text = "🏛️ Official PYQ"
                    elif row.get("source_type") == "Mock question":
                        q_badge_cls = "badge-mock"
                        q_badge_text = "📝 Mock Question"
                    else:
                        q_badge_cls = "badge-ai"
                        q_badge_text = "🤖 Practice MCQ"
                    diff_val = row.get("difficulty", "Medium")
                    diff_cls = f"badge-difficulty-{diff_val.lower()}"

                    st.markdown(
                        f"""
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
                            <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 6px;">
                                <span class="bpsc-badge {q_badge_cls}">{q_badge_text}</span>
                                <span class="bpsc-badge {diff_cls}">{diff_val}</span>
                                <span style="font-size: 12.5px; font-weight: 600; color: #94a3b8; margin-left: 4px;">
                                    {row['subject']} &rarr; {row['topic']}
                                </span>
                            </div>
                            <div style="display: flex; gap: 8px; align-items: center;">
                                <span class="cbt-marking-pill">Penalty: -{active_test['negative_rate']}</span>
                                <span style="font-size: 12px; font-weight: 700; color: #e2e8f0; background: rgba(255,255,255,0.06); padding: 3px 10px; border-radius: 999px;">
                                    Q. {curr_idx + 1} / {len(q_frame)}
                                </span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"#### {row['question']}")

                    opts = {
                        "A": str(row["option_a"]),
                        "B": str(row["option_b"]),
                        "C": str(row["option_c"]),
                        "D": str(row["option_d"]),
                    }
                    saved_ans = answers.get(qid, "-")
                    opt_keys = ["A", "B", "C", "D"]
                    default_idx = opt_keys.index(saved_ans) if saved_ans in opt_keys else None

                    selected_val = st.radio(
                        "Choose your answer:",
                        options=opt_keys,
                        format_func=lambda k: f"{k}. {opts[k]}",
                        index=default_idx,
                        key=f"omr_ans_{active_test['session_id']}_{qid}",
                    )
                    if selected_val:
                        answers[qid] = selected_val

                    c_conf, c_clr, c_rev = st.columns([2, 1, 1.2])
                    saved_conf = confidences.get(qid, "High")
                    conf_opts = ["High", "Medium", "Guess"]
                    if hasattr(st, "segmented_control"):
                        chosen_conf = c_conf.segmented_control(
                            "Confidence Level",
                            options=conf_opts,
                            default=saved_conf if saved_conf in conf_opts else "High",
                            key=f"omr_conf_{active_test['session_id']}_{qid}",
                        )
                    else:
                        chosen_conf = c_conf.radio(
                            "Confidence Level",
                            options=conf_opts,
                            index=conf_opts.index(saved_conf) if saved_conf in conf_opts else 0,
                            horizontal=True,
                            key=f"omr_conf_{active_test['session_id']}_{qid}",
                        )
                    confidences[qid] = chosen_conf or "Medium"

                    if c_clr.button("Clear Response", key=f"clr_{qid}", use_container_width=True):
                        answers.pop(qid, None)
                        st.session_state.pop(f"omr_ans_{active_test['session_id']}_{qid}", None)
                        st.rerun()

                    is_marked = qid in marked_review
                    rev_label = "🟣 Marked for Review" if is_marked else "🔖 Mark for Review"
                    if c_rev.button(rev_label, key=f"rev_{qid}", use_container_width=True):
                        if is_marked:
                            marked_review.remove(qid)
                        else:
                            marked_review.append(qid)
                        st.rerun()

                    # Optional Instant Tutor Hint / Explanation in Learning Mode
                    if active_test.get("instant_feedback") and answers.get(qid, "-") != "-":
                        user_pick = answers[qid]
                        real_cor = str(row["correct_option"]).strip()
                        if user_pick == real_cor:
                            st.success(f"✅ Correct! Official Answer is **{real_cor}**.")
                        else:
                            st.error(f"❌ Incorrect. You selected **{user_pick}**, but the correct answer is **{real_cor}**.")
                        if row.get("explanation"):
                            st.info(f"**Explanation:** {row['explanation']}")

                # Prev / Next Navigation Bar
                nav1, nav2, nav3 = st.columns([1, 1, 1.5])
                if nav1.button("⬅️ Previous", disabled=(curr_idx == 0), use_container_width=True):
                    update_q_timer(qid)
                    active_test["current_index"] = curr_idx - 1
                    st.rerun()
                if nav2.button("Next ➡️", disabled=(curr_idx >= len(q_frame) - 1), use_container_width=True):
                    update_q_timer(qid)
                    active_test["current_index"] = curr_idx + 1
                    st.rerun()
                if nav3.button("✅ Submit Full Test & View Scorecard", type="primary", use_container_width=True):
                    update_q_timer(qid)
                    finalize_test_submission(active_test, q_frame, answers, confidences, q_times)
                    st.rerun()

            with col_omr:
                with st.container(border=True):
                    st.markdown("##### 🎛️ OMR Question Palette")
                    ans_cnt = sum(1 for k in q_frame["id"].astype(int) if answers.get(k, "-") != "-")
                    rem_cnt = len(q_frame) - ans_cnt
                    st.caption(
                        f"🟢 Answered: **{ans_cnt}** · ⚪ Unanswered: **{rem_cnt}** · 🟣 Review: **{len(marked_review)}**"
                    )
                    st.progress(ans_cnt / max(1, len(q_frame)))

                    # Render 5-column OMR jump grid
                    grid_cols = st.columns(5)
                    for idx_btn, q_row in q_frame.iterrows():
                        btn_qid = int(q_row["id"])
                        has_ans = answers.get(btn_qid, "-") != "-"
                        in_rev = btn_qid in marked_review
                        prefix = "🟣" if in_rev else ("🟢" if has_ans else "⚪")
                        btn_type = "primary" if idx_btn == curr_idx else "secondary"
                        if grid_cols[idx_btn % 5].button(
                            f"{prefix}{idx_btn + 1}",
                            key=f"jump_{idx_btn}",
                            type=btn_type,
                            use_container_width=True,
                        ):
                            update_q_timer(qid)
                            active_test["current_index"] = idx_btn
                            st.rerun()
            return

        # Mode 2: Classic Full-Sheet Form Mode (All questions on a single page)
        answers_sheet: Dict[int, str] = {}
        confidences_sheet: Dict[int, str] = {}

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
                answers_sheet[qid] = selection or "-"
                confidences_sheet[qid] = conf
                st.divider()

            submitted = st.form_submit_button("Submit Test & View Analysis", type="primary")

        if submitted:
            finalize_test_submission(active_test, q_frame, answers_sheet, confidences_sheet)
            st.rerun()
        return

    # -------------------------------------------------------------------------
    # C. Configuration for Starting a New Test Session
    # -------------------------------------------------------------------------
    pyq_total_count = db.count_questions(source_type="Official PYQ")
    if pyq_total_count > 0:
        with st.container(border=True):
            p_col_txt, p_col_btn = st.columns([3, 1.2])
            with p_col_txt:
                st.markdown("##### 🏛️ Quick Launch: 10-Year Authentic BPSC PYQ Mock Drill")
                st.caption(
                    f"Test your preparation against **{pyq_total_count}** authentic official questions (60th to 70th CCE) "
                    "with real BPSC -0.33 negative marking and Interactive OMR Palette."
                )
            with p_col_btn:
                if st.button("🎯 Launch 15-Q PYQ Mock", type="primary", use_container_width=True):
                    pyq_ids = db.get_question_ids(source_type="Official PYQ")
                    chosen = random.sample(pyq_ids, k=min(15, len(pyq_ids)))
                    st.session_state["active_test"] = {
                        "session_id": str(uuid.uuid4())[:8],
                        "question_ids": chosen,
                        "exam": "BPSC",
                        "test_mode": "10-Year Authentic PYQ Benchmark Mock",
                        "ui_style": "Interactive OMR Palette",
                        "instant_feedback": False,
                        "negative_rate": 0.33,
                        "start_time": time.time(),
                        "current_index": 0,
                        "answers": {},
                        "confidences": {},
                        "marked_review": [],
                        "question_times": {},
                        "last_q_timestamp": time.time(),
                    }
                    st.session_state["test_results"] = None
                    st.rerun()

    with st.container(border=True):
        st.subheader("Configure Custom Practice or Mock Session")
        f1, f2, f3, f4 = st.columns(4)
        exam = f1.selectbox("Exam", ["All", "BPSC", "UPSC"], key="p_exam")
        subjects = ["All"] + db.get_distinct_subjects(exam=exam)
        subject = f2.selectbox("Subject", subjects, key="p_subj")
        topics = ["All"] + db.get_distinct_topics(subject=subject if subject != "All" else None, exam=exam)
        topic = f3.selectbox("Topic", topics, key="p_top")
        src_types = [
            "All Questions",
            "Official PYQs Only",
            "Mock Questions Only",
            "AI Practice Sets",
            "Starter Samples",
            "Pinned Questions Only",
        ]
        src_choice = f4.selectbox("Question Provenance", src_types, key="p_src")

        src_map = {
            "All Questions": "All",
            "Official PYQs Only": "Official PYQ",
            "Mock Questions Only": "Mock question",
            "AI Practice Sets": "AI-generated",
            "Starter Samples": "Built-in sample",
            "Pinned Questions Only": "All",
        }

        chosen_ed = "All"
        if src_choice == "Official PYQs Only":
            ed_opts = ["All 10-Year Editions"] + db.get_distinct_editions()
            sel_ed = st.selectbox("Filter Specific BPSC Exam Edition (Optional)", ed_opts, key="p_ed_sub")
            if sel_ed != "All 10-Year Editions":
                chosen_ed = sel_ed

        chosen_mock = "All"
        if src_choice == "Mock Questions Only":
            mock_opts = ["All Mock Tests"] + db.get_mock_test_names()
            if len(mock_opts) > 2:
                sel_m = st.selectbox("Filter Specific Mock Test (Optional)", mock_opts, key="p_mock_sub")
                if sel_m != "All Mock Tests":
                    chosen_mock = sel_m

        matching_ids = db.get_question_ids(
            exam=exam,
            subject=subject,
            topic=topic,
            source_type=src_map[src_choice],
            exam_edition=chosen_ed,
            source_name=chosen_mock,
        )
        if src_choice == "Pinned Questions Only":
            pinned_set = db.get_pinned_question_ids()
            matching_ids = [qid for qid in matching_ids if qid in pinned_set]

        if not matching_ids:
            st.warning("No questions match these filters. Adjust filters or generate new questions in AI Studio.")
            return

        c_cnt, c_mode, c_neg = st.columns(3)
        count = c_cnt.slider(
            "Questions in test",
            min_value=1,
            max_value=min(50, len(matching_ids)),
            value=min(10, len(matching_ids)),
        )
        test_mode = c_mode.selectbox(
            "Test Mode",
            ["Practice (Untimed)", "Timed Drill (1 min/Q)", "Full Mock Exam"],
        )
        negative_rate = c_neg.selectbox(
            "Negative Marking",
            [0.33, 0.25, 0.0],
            format_func=lambda x: "None (0.0)" if x == 0.0 else f"-{x} marks per wrong answer (BPSC/UPSC Standard)",
        )

        u1, u2 = st.columns(2)
        ui_style = u1.radio(
            "Examination Interface Style",
            ["Interactive OMR Palette", "Classic Full-Sheet Form"],
            horizontal=True,
        )
        instant_fb = u2.checkbox(
            "Enable Instant Answer & Explanation Reveal (Study Mode)",
            value=(test_mode == "Practice (Untimed)"),
        )

        if st.button("🚀 Start Test Session", type="primary", use_container_width=True):
            selected_ids = random.sample(matching_ids, k=count)
            st.session_state["active_test"] = {
                "session_id": str(uuid.uuid4())[:8],
                "question_ids": selected_ids,
                "exam": exam if exam != "All" else "BPSC",
                "test_mode": test_mode,
                "ui_style": ui_style,
                "instant_feedback": instant_fb,
                "negative_rate": negative_rate,
                "start_time": time.time(),
                "current_index": 0,
                "answers": {},
                "confidences": {},
                "marked_review": [],
                "question_times": {},
                "last_q_timestamp": time.time(),
            }
            st.rerun()


# -----------------------------------------------------------------------------
# Views: 5. AI Study Tutor (Complete Options Context Passing)
# -----------------------------------------------------------------------------

def show_ai_tutor() -> None:
    """Conversational study tutor with pedagogical modes and complete option-context analysis."""
    st.title("🎓 AI Study Tutor")
    st.write("Master core concepts, dissect tricky distractors, generate mnemonics, and test active recall.")

    if not config.is_gemini_configured():
        st.warning("⚠️ Gemini API is not configured. Please add `GEMINI_API_KEY` to enable the AI Tutor.")
        return

    ctx_q = st.session_state.get("tutor_context_question")
    if ctx_q:
        opts_map = ctx_q.get("options") or (
            get_question_options_map(int(ctx_q["question_id"])) if ctx_q.get("question_id") else {}
        )
        ctx_q["options"] = opts_map
        with st.container(border=True):
            c_hdr, c_detach = st.columns([4, 1])
            c_hdr.info(f"📍 **Active Question Context:** {ctx_q.get('subject', '')} · {ctx_q.get('topic', '')}")
            if c_detach.button("✖ Detach Question", use_container_width=True):
                st.session_state["tutor_context_question"] = None
                st.rerun()
            st.markdown(f"**{ctx_q['question']}**")
            if opts_map:
                st.caption(
                    f"**A.** {opts_map.get('A', '')} | **B.** {opts_map.get('B', '')} | "
                    f"**C.** {opts_map.get('C', '')} | **D.** {opts_map.get('D', '')}"
                )
            st.caption(
                f"Your Answer: `{ctx_q.get('selected_option', '-')}` · Correct Option: `{ctx_q.get('correct_option', '')}`"
            )

    c_mode, c_clear = st.columns([4, 1])
    mode = c_mode.selectbox(
        "Pedagogical Mode",
        [
            "Explain my mistake",
            "Explain why each option is right or wrong",
            "Explain from first principles",
            "Give a short BPSC exam-oriented explanation",
            "Give me a memory aid, comparison table or timeline",
            "Explain the difference between two easily confused concepts",
            "Give me a hint without revealing the answer",
            "Teach using a simple example or analogy",
            "Ask me follow-up questions to test understanding",
        ],
    )
    if c_clear.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state["tutor_history"] = []
        st.session_state["tutor_context_question"] = None
        st.rerun()

    # Quick Prompt Chips
    p1, p2, p3 = st.columns(3)
    quick_prompt = None
    if p1.button("🔍 Break down all 4 options (A, B, C, D)", use_container_width=True):
        quick_prompt = "Break down each of the four options (A, B, C, and D) and explain why each distractor is right or wrong."
    if p2.button("🧠 Give me a high-retention mnemonic / table", use_container_width=True):
        quick_prompt = "Create a high-retention mnemonic or comparison table for this topic for BPSC Prelims revision."
    if p3.button("🎯 Quiz me with 1 follow-up trap question", use_container_width=True):
        quick_prompt = "Ask me one tricky statement-based follow-up question on this exact concept to test if I truly understood it."

    user_query = st.chat_input("Ask a question, compare two concepts, or request a syllabus deep-dive...")
    active_query = user_query or quick_prompt

    # Display Chat History
    for msg in st.session_state["tutor_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if active_query or (ctx_q and not st.session_state["tutor_history"]):
        prompt_query = (
            active_query
            or f"Why was my answer ({ctx_q.get('selected_option', '-')}) wrong compared to {ctx_q.get('correct_option', '')}, and how do I master this concept?"
        )
        st.session_state["tutor_history"].append({"role": "user", "content": prompt_query})
        with st.chat_message("user"):
            st.markdown(prompt_query)

        with st.chat_message("assistant"):
            with st.spinner("AI Tutor is analyzing..."):
                try:
                    full_options = ctx_q.get("options") if ctx_q else None
                    ans = ai_service.tutor_query(
                        mode=mode,
                        user_query=prompt_query,
                        question_text=ctx_q["question"] if ctx_q else "",
                        options=full_options,
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
    """Diagnostic report generator that synthesizes deterministic test metrics and confidence calibration."""
    st.title("🏆 AI Performance Coach")
    st.caption(
        "Evidence-based diagnostic report evaluating your test history, error taxonomy, and confidence calibration."
    )

    attempts = db.get_attempts()
    sessions = db.get_test_sessions()
    if attempts.empty:
        st.info("No attempts recorded yet. Complete a few practice tests to generate your performance diagnostic.")
        return

    overall = analytics.compute_overall_metrics(attempts, sessions)
    topic_df = analytics.compute_topic_analytics(attempts)
    error_counts = analytics.compute_error_distribution(attempts)
    calibration = compute_confidence_calibration(attempts)

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Tests Tracked", overall["total_tests"])
    col2.metric("Total Attempted", overall["total_attempts"])
    col3.metric("Measured Accuracy", f"{overall['accuracy']}%")
    col4.metric("High-Conf Accuracy", f"{calibration['high_conf_accuracy']}%")
    col5.metric("Net Guess Impact", f"{calibration['guess_net_score']:+0.2f}")

    if not calibration["breakdown"].empty:
        with st.expander("🧠 View Metacognitive Confidence Calibration Matrix", expanded=True):
            st.dataframe(calibration["breakdown"], use_container_width=True, hide_index=True)

    if st.button("🔍 Generate AI Diagnostic Report", type="primary"):
        with st.spinner("Performance Coach is evaluating test data..."):
            try:
                summary_stats = {
                    "total_attempts": overall["total_attempts"],
                    "accuracy": overall["accuracy"],
                    "total_tests": overall["total_tests"],
                    "topic_stats": topic_df.head(8).to_dict("records"),
                    "error_counts": error_counts,
                    "high_confidence_blind_spots": calibration["blind_spots"],
                    "guess_net_score": calibration["guess_net_score"],
                }
                recent_incorrect = attempts[attempts["is_correct"] == 0].head(10).to_dict("records")
                report: schemas.DiagnosticReport = ai_service.generate_performance_coach_report(
                    summary_stats, recent_incorrect
                )
                st.session_state["coach_report"] = report.model_dump()
                st.success("Performance Diagnostic Report ready!")
            except Exception as exc:
                st.error(f"Coach error: {exc}")

    saved_report = st.session_state.get("coach_report")
    if saved_report:
        st.divider()
        st.subheader("📋 Executive Diagnostic Summary")
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
# Views: 7. Error Notebook & Pinned Vault
# -----------------------------------------------------------------------------

def show_error_notebook() -> None:
    """Persistent mistake diagnosis, error pattern analytics, and pinned question revision vault."""
    st.title("📕 Error Notebook & Revision Vault")
    st.write(
        "Diagnose every incorrect attempt with full option context, classify root causes, and drill your Pinned Questions Vault."
    )

    attempts = db.get_attempts()
    pinned_df = get_pinned_questions_df()

    tab_mistakes, tab_pinned, tab_patterns = st.tabs([
        f"❌ Incorrect Attempts ({len(attempts[attempts['is_correct'] == 0]) if not attempts.empty else 0})",
        f"📌 Pinned Questions Vault ({len(pinned_df)})",
        "📊 Error Taxonomy & Patterns",
    ])

    # ---------------------------------------------------------
    # TAB 1: Incorrect Attempts & AI Mistake Diagnosis
    # ---------------------------------------------------------
    with tab_mistakes:
        if attempts.empty:
            st.info("No test attempts recorded yet. Mistakes from tests will appear here automatically.")
        else:
            incorrect = attempts[attempts["is_correct"] == 0].copy()
            if incorrect.empty:
                st.success("🎉 Zero incorrect attempts recorded so far!")
            else:
                c_hdr1, c_hdr2, c_hdr3 = st.columns([2, 1.5, 1.5])
                c_hdr1.metric("Total Recorded Mistakes", len(incorrect))
                unclassified_cnt = int((incorrect["error_type"] == "Unclassified").sum())
                c_hdr2.metric("Unclassified Mistakes", unclassified_cnt)

                if c_hdr3.button("🎯 Practice My Mistakes", type="primary", use_container_width=True):
                    missed_ids = [int(x) for x in incorrect["question_id"].unique()]
                    selected_ids = random.sample(missed_ids, k=min(10, len(missed_ids)))
                    st.session_state["active_test"] = {
                        "session_id": str(uuid.uuid4())[:8],
                        "question_ids": selected_ids,
                        "exam": "BPSC",
                        "test_mode": "Mistake Remediation Drill",
                        "ui_style": "Interactive OMR Palette",
                        "instant_feedback": True,
                        "negative_rate": 0.33,
                        "start_time": time.time(),
                        "current_index": 0,
                        "answers": {},
                        "confidences": {},
                        "marked_review": [],
                        "question_times": {},
                        "last_q_timestamp": time.time(),
                    }
                    st.session_state["test_results"] = None
                    navigate_to("Practice & Mock Tests")

                st.divider()

                f_col1, f_col2 = st.columns(2)
                err_filter = f_col1.selectbox("Filter by Mistake Reason", ["All"] + db.ERROR_TYPES)
                subj_choices = ["All"] + sorted(incorrect["subject"].dropna().unique().tolist())
                subj_filter = f_col2.selectbox("Filter by Subject", subj_choices)

                filtered = incorrect
                if err_filter != "All":
                    filtered = filtered[filtered["error_type"] == err_filter]
                if subj_filter != "All":
                    filtered = filtered[filtered["subject"] == subj_filter]

                st.caption(f"Showing {len(filtered)} mistake(s).")

                for _, row in filtered.head(25).iterrows():
                    att_id = int(row["attempt_id"])
                    qid = int(row["question_id"])
                    is_pinned = db.is_question_pinned(qid)
                    opts_map = get_question_options_map(qid)

                    pin_label = "📌 Unpin" if is_pinned else "📍 Pin for Revision"
                    conf_str = f" · Confidence: {row.get('confidence_rating', 'Medium')}" if "confidence_rating" in row else ""
                    with st.expander(
                        f"[{row['error_type']}] {row['subject']} · {row['topic']} ({row['attempted_at'][:16]}{conf_str})",
                        expanded=(row["error_type"] == "Unclassified"),
                    ):
                        st.markdown(f"**Question:** {row['question']}")
                        if any(opts_map.values()):
                            st.caption(
                                f"**A.** {opts_map.get('A', '')} | **B.** {opts_map.get('B', '')} | "
                                f"**C.** {opts_map.get('C', '')} | **D.** {opts_map.get('D', '')}"
                            )
                        ans_display = (
                            "Not answered"
                            if row["selected_option"] == "-"
                            else f"{row['selected_option']} ({opts_map.get(row['selected_option'], '')})"
                        )
                        cor_display = f"{row['correct_option']} ({opts_map.get(row['correct_option'], '')})"
                        st.write(f"**Your Answer:** {ans_display} · **Correct Answer:** {cor_display}")
                        if row.get("explanation"):
                            st.info(f"**Explanation:** {row['explanation']}")

                        ec1, ec2 = st.columns([1, 2])
                        current_err_idx = (
                            db.ERROR_TYPES.index(row["error_type"])
                            if row["error_type"] in db.ERROR_TYPES
                            else 0
                        )
                        err_type = ec1.selectbox(
                            "Classify Mistake",
                            db.ERROR_TYPES,
                            index=current_err_idx,
                            key=f"nb_err_{att_id}",
                        )
                        err_note = ec2.text_input(
                            "Personal Study Note",
                            value=str(row["error_notes"] or ""),
                            key=f"nb_note_{att_id}",
                        )

                        btn_col1, btn_col2, btn_col3 = st.columns(3)
                        if btn_col1.button("💾 Save Classification", key=f"save_err_{att_id}", use_container_width=True):
                            db.save_error_classification(att_id, err_type, err_note)
                            st.success("Classification saved!")
                            st.rerun()

                        if btn_col2.button(pin_label, key=f"pin_{att_id}", use_container_width=True):
                            if is_pinned:
                                db.unpin_question(qid)
                            else:
                                db.pin_question(qid, note=err_note)
                            st.rerun()

                        if config.is_gemini_configured() and btn_col3.button(
                            "🤖 Diagnose with AI", key=f"ai_diag_{att_id}", use_container_width=True
                        ):
                            with st.spinner("Diagnosing mistake with full option context..."):
                                try:
                                    diag = ai_service.diagnose_mistake(
                                        question_text=row["question"],
                                        options=opts_map,
                                        correct_option=row["correct_option"],
                                        selected_option=row["selected_option"],
                                        explanation=row.get("explanation", ""),
                                        subject=row["subject"],
                                        topic=row["topic"],
                                    )
                                    st.markdown(f"**AI Diagnosis:** {diag.diagnosis}")
                                    st.markdown(f"**Core Concept Recap:** {diag.concept_recap}")
                                    st.markdown(f"**Next Action:** {diag.next_step_action}")
                                    db.save_error_classification(
                                        att_id, diag.suggested_error_type, diag.next_step_action
                                    )
                                except Exception as exc:
                                    st.error(f"Diagnosis failed: {exc}")

    # ---------------------------------------------------------
    # TAB 2: Pinned Questions Vault
    # ---------------------------------------------------------
    with tab_pinned:
        if pinned_df.empty:
            st.info(
                "No questions are currently pinned. Pin tricky questions from the Question Bank, Test Scorecard, or Error Notebook to build your high-priority revision vault."
            )
        else:
            p_hdr1, p_hdr2 = st.columns([3, 1])
            p_hdr1.write(f"You have **{len(pinned_df)}** pinned question(s) ready for rapid revision.")
            if p_hdr2.button("🚀 Drill Pinned Vault", type="primary", use_container_width=True):
                p_ids = pinned_df["id"].astype(int).tolist()
                st.session_state["active_test"] = {
                    "session_id": str(uuid.uuid4())[:8],
                    "question_ids": p_ids[:25],
                    "exam": "BPSC",
                    "test_mode": "Pinned Vault Revision Drill",
                    "ui_style": "Interactive OMR Palette",
                    "instant_feedback": True,
                    "negative_rate": 0.33,
                    "start_time": time.time(),
                    "current_index": 0,
                    "answers": {},
                    "confidences": {},
                    "marked_review": [],
                    "question_times": {},
                    "last_q_timestamp": time.time(),
                }
                st.session_state["test_results"] = None
                navigate_to("Practice & Mock Tests")

            for _, prow in pinned_df.iterrows():
                pqid = int(prow["id"])
                with st.container(border=True):
                    st.markdown(f"#### Q.#{pqid} ({prow['subject']} · {prow['topic']}): {prow['question']}")
                    st.write(
                        f"- **A.** {prow['option_a']}\n"
                        f"- **B.** {prow['option_b']}\n"
                        f"- **C.** {prow['option_c']}\n"
                        f"- **D.** {prow['option_d']}"
                    )
                    with st.expander("Show Answer & Explanation"):
                        st.success(f"**Correct Option:** `{prow['correct_option']}`")
                        st.write(prow.get("explanation", ""))
                    if st.button("📌 Unpin from Vault", key=f"vault_unpin_{pqid}"):
                        db.unpin_question(pqid)
                        st.rerun()

    # ---------------------------------------------------------
    # TAB 3: Error Taxonomy & Patterns
    # ---------------------------------------------------------
    with tab_patterns:
        if attempts.empty or attempts[attempts["is_correct"] == 0].empty:
            st.info("Record and classify mistakes to see your error taxonomy distribution.")
        else:
            err_dist = analytics.compute_error_distribution(attempts)
            err_rows = [{"Error Type": k, "Count": v} for k, v in err_dist.items() if v > 0]
            if err_rows:
                st.subheader("Mistake Root-Cause Distribution")
                st.dataframe(pd.DataFrame(err_rows), use_container_width=True, hide_index=True)


# -----------------------------------------------------------------------------
# Views: 8. Revision Planner
# -----------------------------------------------------------------------------

def show_revision_planner() -> None:
    """Adaptive 7-day revision schedule with spaced repetition intervals and direct drill triggers."""
    st.title("📅 Adaptive Revision Planner")
    st.write("Evidence-driven 7-day study schedule based on accuracy, error recurrence, and spaced repetition.")

    attempts = db.get_attempts()
    topic_stats = db.get_topic_stats()

    with st.container(border=True):
        st.subheader("Configure Target Exam & Study Rhythm")
        c1, c2, c3 = st.columns(3)
        exam_target_date = c1.date_input("Target Exam Date", value=date.today() + timedelta(days=90))
        daily_minutes = c2.slider(
            "Daily Revision Budget (minutes)", min_value=30, max_value=240, value=90, step=15
        )
        preferred_subj = c3.multiselect("Focus Subjects (Optional)", db.SUBJECTS, default=[])

    days_left = (exam_target_date - date.today()).days
    st.caption(f"⏳ **{max(0, days_left)} days** remaining until target examination date ({exam_target_date}).")

    retention = analytics.measure_revision_outcome(attempts)
    if retention["retried_topics_count"] > 0:
        st.success(
            f"📈 Revision Effectiveness: Retried topics showed an average accuracy gain of "
            f"**{retention['average_gain']:+0.1f}%** across {retention['retried_topics_count']} topics!"
        )

    plan = revision_engine.generate_adaptive_weekly_plan(
        stats=topic_stats,
        attempts=attempts,
        target_exam_date=exam_target_date,
        daily_available_minutes=daily_minutes,
        preferred_subjects=preferred_subj,
    )

    st.subheader("7-Day Adaptive Schedule")
    for idx, item in enumerate(plan):
        with st.container(border=True):
            r_left, r_right = st.columns([3.5, 1])
            with r_left:
                st.markdown(f"### {item['day']} ({item['date']}) · {item['subject']}: {item['topic']}")
                st.write(item["task"])
                st.caption(f"**Rationale:** {item['basis']} · ⏱️ Est: **{item['estimated_minutes']} mins**")
            with r_right:
                matching_ids = db.get_question_ids(
                    exam="All", subject=item["subject"], topic=item["topic"]
                )
                if not matching_ids:
                    matching_ids = db.get_question_ids(exam="All", subject=item["subject"], topic="All")
                if matching_ids:
                    if st.button(
                        f"🎯 Drill {item['subject']}",
                        key=f"rev_drill_{idx}",
                        use_container_width=True,
                    ):
                        chosen = random.sample(matching_ids, k=min(10, len(matching_ids)))
                        st.session_state["active_test"] = {
                            "session_id": str(uuid.uuid4())[:8],
                            "question_ids": chosen,
                            "exam": "BPSC",
                            "test_mode": f"Revision Drill: {item['topic']}",
                            "ui_style": "Interactive OMR Palette",
                            "instant_feedback": True,
                            "negative_rate": 0.33,
                            "start_time": time.time(),
                            "current_index": 0,
                            "answers": {},
                            "confidences": {},
                            "marked_review": [],
                            "question_times": {},
                            "last_q_timestamp": time.time(),
                        }
                        st.session_state["test_results"] = None
                        navigate_to("Practice & Mock Tests")

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
        "title": "🐅 Wildlife & Environment: Valmiki & Kaimur Tiger Reserve + Nagi-Nakti Ramsar Sites",
        "category": "Environment & Biodiversity",
        "topic": "Valmiki & Kaimur Tiger Reserves and Bihar Ramsar Sites",
        "summary": "Valmiki National Park & Tiger Reserve in West Champaran is Bihar's first tiger reserve (54 tigers). The NTCA approved Kaimur Wildlife Sanctuary as Bihar's second tiger reserve. Furthermore, in 2024, Nagi and Nakti Bird Sanctuaries in Jamui district were designated as Ramsar Sites of International Importance, joining Kabartal (Kanwar Lake) in Begusarai to bring Bihar's total Ramsar wetlands count to 3.",
        "key_facts": [
            "Valmiki Tiger Reserve: West Champaran, contiguous with Chitwan National Park (Nepal).",
            "Second Tiger Reserve: Approved in Kaimur Wildlife Sanctuary (Kaimur & Rohtas).",
            "Bihar Ramsar Sites (Total 3): Kabartal (Begusarai, 2020), Nagi Bird Sanctuary & Nakti Bird Sanctuary (Jamui, 2024).",
            "National Dolphin Research Centre (NDRC): Inaugurated in Patna (2024).",
        ],
    },
]


def show_current_affairs() -> None:
    """Dedicated Current Affairs Hub: Instant MCQ generation, live grounded research, capsules, and saved vault."""
    st.title("📰 Current Affairs & News Lab")
    st.write(
        "Master high-yield National, International, and Bihar Current Affairs for BPSC CCE and UPSC Prelims. "
        "Generate multi-statement practice MCQs, synthesize live policy developments with Google Search grounding, and manage your Research Vault."
    )

    if not config.is_gemini_configured():
        st.warning("⚠️ Gemini API is not configured. Please add `GEMINI_API_KEY` to enable current affairs synthesis.")
        return

    tab1, tab2, tab3, tab4 = st.tabs([
        "⚡ Instant Current Affairs MCQs",
        "🔍 Live Policy & Topic Research",
        "📌 High-Yield BPSC Capsules",
        "🗂️ Saved Research Vault",
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
        ca_timeframe = c_ca5.selectbox(
            "Timeframe Focus",
            ["Last 6 Months (BPSC High-Yield)", "Last 1 Year", "Recent State Initiatives"],
            key="ca_time_select",
        )

        ca_exemplars = db.retrieve_pyq_exemplars(subject="Current Affairs", topic=ca_category[:20], limit=4)
        if ca_exemplars:
            st.caption(
                f"🏛️ **Strict BPSC Benchmark Active**: Calibrating against **{len(ca_exemplars)}** authentic Current Affairs PYQ benchmarks."
            )
            with st.expander(f"🔍 Inspect {len(ca_exemplars)} Retrieved Current Affairs Benchmarks", expanded=False):
                for c_idx, cex in enumerate(ca_exemplars, 1):
                    st.markdown(f"**Benchmark #{c_idx}** ({cex.get('exam_edition', 'BPSC PYQ')}) — *{cex.get('question', '')}*")
                    st.caption(f"Official Answer: `{cex.get('correct_option', '')}` · Focus: {cex.get('topic', '')}")
                    if c_idx < len(ca_exemplars):
                        st.divider()

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
                        notes_or_context=f"Focus on verified civil services developments relevant for BPSC Prelims: {ca_timeframe}.",
                    )
                    st.session_state["ca_questions"] = [q.model_dump() for q in q_set.questions]
                    st.session_state["ca_exemplars"] = q_set.retrieved_exemplars
                    st.success(f"Generated {len(q_set.questions)} Current Affairs question(s) successfully!")
                except Exception as exc:
                    st.error(f"Generation failed: {exc}")

        ca_items = st.session_state.get("ca_questions")
        if ca_items:
            st.divider()
            st.subheader(f"Review & Save Generated Current Affairs Questions ({len(ca_items)})")
            ca_gen_id = st.session_state.get("ca_gen_id", 0)
            ca_to_save: List[Dict[str, Any]] = []

            for idx, q in enumerate(ca_items):
                with st.expander(f"Question #{idx+1}: {q['question'][:80]}...", expanded=True):
                    q_text = st.text_area(
                        "Question Statement", value=q["question"], key=f"ca_sq_text_{ca_gen_id}_{idx}"
                    )
                    co1, co2 = st.columns(2)
                    oa = co1.text_input("Option A", value=q["option_a"], key=f"ca_sq_oa_{ca_gen_id}_{idx}")
                    ob = co2.text_input("Option B", value=q["option_b"], key=f"ca_sq_ob_{ca_gen_id}_{idx}")
                    oc = co1.text_input("Option C", value=q["option_c"], key=f"ca_sq_oc_{ca_gen_id}_{idx}")
                    od = co2.text_input("Option D", value=q["option_d"], key=f"ca_sq_od_{ca_gen_id}_{idx}")

                    curr_idx = (
                        ["A", "B", "C", "D"].index(q["correct_option"])
                        if q["correct_option"] in ["A", "B", "C", "D"]
                        else 0
                    )
                    cor_opt = st.radio(
                        "Correct Answer",
                        ["A", "B", "C", "D"],
                        index=curr_idx,
                        horizontal=True,
                        key=f"ca_sq_cor_{ca_gen_id}_{idx}",
                    )
                    exp = st.text_area(
                        "Explanation", value=q.get("explanation", ""), key=f"ca_sq_exp_{ca_gen_id}_{idx}"
                    )
                    dist = st.text_input(
                        "Distractor Notes", value=q.get("distractor_notes", ""), key=f"ca_sq_dist_{ca_gen_id}_{idx}"
                    )

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
                for item in ca_to_save:
                    db.add_question(item)
                st.success(f"Saved {len(ca_to_save)} Current Affairs questions to your Question Bank!")
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
        st.write(
            "Research any recent government announcement, scheme, or economic survey highlight to get exam-ready points with source citations."
        )

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
            if c_save.button("💾 Save to Research Vault", key="save_res_btn"):
                db.save_research_note(
                    topic=res["topic"],
                    title=res["topic"],
                    summary=res["text"],
                    key_facts=[],
                    bihar_angle="Included" if bihar_angle else "",
                )
                st.success("Saved to Research Vault! View anytime under the 'Saved Research Vault' tab.")

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
                        st.success(
                            "Generated 3 questions! Check the 'Instant Current Affairs MCQs' tab to review and save them."
                        )
                    except Exception as exc:
                        st.error(f"Generation error: {exc}")

    # ---------------------------------------------------------
    # TAB 3: High-Yield BPSC Capsules
    # ---------------------------------------------------------
    with tab3:
        st.subheader("High-Yield BPSC Current Affairs Capsules")
        st.write("Curated, syllabus-linked facts on the highest-yield topics for BPSC CCE Prelims.")

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
                            st.success(
                                f"Generated 3 questions on {cap['topic']}! Switch to 'Instant Current Affairs MCQs' tab to review and save."
                            )
                        except Exception as exc:
                            st.error(f"Generation error: {exc}")

    # ---------------------------------------------------------
    # TAB 4: Saved Research Vault
    # ---------------------------------------------------------
    with tab4:
        st.subheader("🗂️ Saved Research Notes Vault")
        notes_df = get_saved_research_notes()
        if notes_df.empty:
            st.info(
                "No saved research notes yet. Use the 'Live Policy & Topic Research' tab to research topics and save them here."
            )
        else:
            st.caption(f"Stored Research Dossiers: **{len(notes_df)}**")
            for idx, nrow in notes_df.iterrows():
                ntitle = nrow.get("title") or nrow.get("topic") or f"Research Note #{idx+1}"
                nsummary = nrow.get("summary", "")
                created = str(nrow.get("created_at", ""))[:16]
                with st.expander(f"📄 {ntitle} ({created})", expanded=False):
                    st.markdown(nsummary)
                    if st.button(
                        f"✨ Generate 3 MCQs from '{ntitle[:35]}'",
                        key=f"vault_gen_{idx}",
                    ):
                        with st.spinner("Generating questions from saved research note..."):
                            try:
                                q_set = ai_service.generate_question_set(
                                    exam="BPSC",
                                    subject="Current Affairs",
                                    topic=ntitle,
                                    subtopic="Saved Research Vault",
                                    count=3,
                                    difficulty="Medium",
                                    question_type="Statement-based (1 and 2 only, etc.)",
                                    focus="PYQ-inspired practice",
                                    notes_or_context=nsummary,
                                )
                                st.session_state["ca_questions"] = [q.model_dump() for q in q_set.questions]
                                st.session_state["ca_exemplars"] = q_set.retrieved_exemplars
                                st.success(
                                    "Generated 3 questions! Switch to the 'Instant Current Affairs MCQs' tab to review and save."
                                )
                            except Exception as exc:
                                st.error(f"Generation error: {exc}")


# -----------------------------------------------------------------------------
# Views: 10. Settings & Data Management
# -----------------------------------------------------------------------------

def show_settings() -> None:
    """Manage API keys, check model health, cloud sync with Supabase, and export backups."""
    st.title("⚙️ Settings & Data Management")
    st.write("Configure external services, test Google Gemini SDK connectivity, and backup your local database.")

    # 1. Gemini AI API Configuration Status
    st.subheader("1. Google Gemini AI Engine")
    key = config.get_gemini_api_key()
    c_s1, c_s2 = st.columns(2)
    c_s1.write(f"**Gemini API Key:** `{config.mask_secret(key)}`")
    c_s2.write(f"**Active Model:** `{config.get_gemini_model()}`")

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

    # 2. Supabase Cloud Sync
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

    # 3. Local SQLite Backup
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
        page_title="BPSC Question Lab v2.0",
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
            <div class="brand-sub">Government Examination Lab</div>
            <div class="brand-name">🏛️ BPSC QUESTION LAB</div>
            <div class="brand-ver">
                <span>v{APP_VERSION}</span> · 
                <span style="color: #10b981; font-weight: 700;">● Online</span> · 
                <span>BPSC & UPSC</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Handle programmatic redirects
    default_page = st.session_state.get("nav_page", "Dashboard")
    if default_page not in NAV_PAGES:
        default_page = "Dashboard"

    selected_page = st.sidebar.radio(
        "Navigate",
        NAV_PAGES,
        index=NAV_PAGES.index(default_page),
        key="_nav_radio_widget",
    )
    st.session_state["nav_page"] = selected_page

    st.sidebar.markdown(
        """
        <div class="sidebar-target-box">
            <div style="font-weight: 700; color: #60a5fa; margin-bottom: 5px; display: flex; align-items: center; justify-content: space-between;">
                <span>🎯 Target: 71st BPSC Prelims</span>
                <span style="font-size: 11px; background: rgba(59, 130, 246, 0.25); border: 1px solid rgba(59, 130, 246, 0.4); padding: 2px 7px; border-radius: 999px; font-weight: 600;">-0.33 Mark</span>
            </div>
            <div style="font-size: 12px; color: #cbd5e1; line-height: 1.5;">
                • 150 Questions · 120 Minutes<br>
                • Core: Bihar Special, History, Polity, Science, Current Affairs
            </div>
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
