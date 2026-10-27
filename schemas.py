"""Pydantic schemas and data validation models for BPSC Question Lab v1.0.

Provides strict validation for AI generated questions, mistake diagnoses,
performance reports, and research summaries.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, PrivateAttr, field_validator


class GeneratedQuestion(BaseModel):
    """Schema for an individual AI-generated practice question."""

    question: str = Field(..., description="The complete question stem.")
    option_a: str = Field(..., description="Text for Option A.")
    option_b: str = Field(..., description="Text for Option B.")
    option_c: str = Field(..., description="Text for Option C.")
    option_d: str = Field(..., description="Text for Option D.")
    correct_option: Literal["A", "B", "C", "D"] = Field(..., description="The single correct answer option.")
    explanation: str = Field(..., description="Clear explanation of the correct answer.")
    distractor_notes: str = Field(
        default="",
        description="Explanation of why distractors (incorrect options) are wrong.",
    )
    concept_tested: str = Field(..., description="Key concept or syllabus fact tested.")
    subject: str = Field(default="Other", description="Main syllabus subject.")
    topic: str = Field(default="General", description="Topic within the subject.")
    subtopic: str = Field(default="", description="Specific subtopic or theme.")
    difficulty: Literal["Easy", "Medium", "Hard"] = Field(default="Medium", description="Question difficulty.")
    question_type: str = Field(
        default="Standard MCQ",
        description="Question style (e.g., Standard MCQ, Statement-based, Assertion-Reason, Chronology, Matching, Bihar Special).",
    )
    source_reference: str = Field(
        default="",
        description="Contextual source reference or syllabus topic. Must not claim to be an official PYQ unless verified.",
    )
    is_ai_generated: bool = Field(default=True, description="Flag indicating AI generation.")

    @field_validator("question", "option_a", "option_b", "option_c", "option_d", "explanation")
    @classmethod
    def check_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or whitespace.")
        return s

    @field_validator("option_d")
    @classmethod
    def check_distinct_options(cls, v: str, info) -> str:
        data = info.data
        opts = [data.get("option_a", "").strip().lower(),
                data.get("option_b", "").strip().lower(),
                data.get("option_c", "").strip().lower(),
                v.strip().lower()]
        unique_opts = {o for o in opts if o}
        if len(unique_opts) < 4:
            raise ValueError("All 4 question options must be distinct.")
        return v


class GeneratedQuestionSet(BaseModel):
    """Schema for a collection of generated questions."""

    exam: str = Field(default="BPSC", description="Target exam (BPSC, UPSC, or Both).")
    subject: str = Field(..., description="Subject name.")
    topic: str = Field(..., description="Topic name.")
    questions: List[GeneratedQuestion] = Field(default_factory=list, description="List of validated questions.")
    _retrieved_exemplars: List[Dict[str, Any]] = PrivateAttr(default_factory=list)

    @property
    def retrieved_exemplars(self) -> List[Dict[str, Any]]:
        return self._retrieved_exemplars

    @retrieved_exemplars.setter
    def retrieved_exemplars(self, value: List[Dict[str, Any]]) -> None:
        self._retrieved_exemplars = value


class MistakeDiagnosis(BaseModel):
    """Schema for AI mistake analysis."""

    suggested_error_type: Literal[
        "Knowledge gap",
        "Conceptual confusion",
        "Misread question",
        "Incorrect elimination / guess",
        "Careless error",
        "Calculation or reasoning error",
        "Confusion between similar facts",
        "Other",
    ] = Field(..., description="Primary categorized root cause.")
    diagnosis: str = Field(..., description="Why the student likely chose the incorrect option.")
    concept_recap: str = Field(..., description="Concise statement of the correct principle or fact.")
    distinction: str = Field(default="", description="Crucial distinction to remember for exam day.")
    next_step_action: str = Field(..., description="Specific, actionable revision recommendation.")


class ActionItem(BaseModel):
    """Individual actionable recommendation for performance improvement."""

    topic: str = Field(..., description="Topic or subject needing attention.")
    action: str = Field(..., description="Specific recommended study activity.")
    rationale: str = Field(..., description="Evidence-backed reason from test performance.")
    priority: Literal["High", "Medium", "Low"] = Field(default="Medium")


class DiagnosticReport(BaseModel):
    """Schema for the AI Performance Coach post-test report."""

    test_summary: str = Field(..., description="Objective overview of measured performance.")
    strong_areas: List[str] = Field(default_factory=list, description="Topics with demonstrated mastery.")
    weak_areas: List[str] = Field(default_factory=list, description="Topics with recurring errors or low accuracy.")
    identified_knowledge_gaps: List[str] = Field(default_factory=list, description="Factual gaps observed.")
    conceptual_misunderstandings: List[str] = Field(default_factory=list, description="Conceptual confusions observed.")
    reading_or_guessing_patterns: List[str] = Field(
        default_factory=list, description="Patterns in careless reading or elimination."
    )
    recommended_action_items: List[ActionItem] = Field(
        default_factory=list, description="Ordered revision actions."
    )


class ResearchSummary(BaseModel):
    """Schema for source research and current affairs synthesis."""

    title: str = Field(..., description="Title of the topic or document.")
    source_url: str = Field(default="", description="Origin URL if available.")
    publisher: str = Field(default="", description="Source entity or publication.")
    publication_date: str = Field(default="", description="Date of release or retrieval.")
    summary: str = Field(..., description="Core summary for exam preparation.")
    key_exam_facts: List[str] = Field(default_factory=list, description="High-yield facts for prelims/mains.")
    syllabus_links: List[str] = Field(default_factory=list, description="Matching BPSC/UPSC syllabus topics.")
    bihar_specific_angle: str = Field(default="", description="Bihar-specific relevance, if applicable.")


class ExtractedMockQuestion(BaseModel):
    """Schema for an individual MCQ extracted from an uploaded mock test PDF."""

    question: str = Field(..., description="The complete question stem.")
    option_a: str = Field(..., description="Text for Option A.")
    option_b: str = Field(..., description="Text for Option B.")
    option_c: str = Field(..., description="Text for Option C.")
    option_d: str = Field(..., description="Text for Option D.")
    correct_option: Literal["A", "B", "C", "D"] = Field(
        default="A",
        description="The correct answer option (A, B, C, or D).",
    )
    explanation: str = Field(
        default="",
        description="Detailed explanation of the correct answer, or context from the paper.",
    )
    distractor_notes: str = Field(
        default="",
        description="Analysis of why incorrect options are wrong.",
    )
    concept_tested: str = Field(
        default="",
        description="Core syllabus concept or factual point tested.",
    )
    subject: Literal[
        "Modern History",
        "Ancient & Medieval History",
        "Bihar Special",
        "Geography",
        "Indian Polity",
        "Economy",
        "General Science",
        "Environment",
        "Current Affairs",
        "Other",
    ] = Field(
        default="Other",
        description="Categorized subject according to BPSC/UPSC syllabus.",
    )
    topic: str = Field(default="General", description="Topic within the subject.")
    difficulty: Literal["Easy", "Medium", "Hard"] = Field(
        default="Medium", description="Estimated difficulty level."
    )
    question_type: str = Field(
        default="Standard MCQ",
        description="Question format (Standard MCQ, Statement-based, Assertion-Reason, Matching, etc.).",
    )
    original_language: str = Field(
        default="English",
        description="Original language of the question in the document ('English', 'Hindi', 'Bilingual').",
    )
    original_question_hindi: str = Field(
        default="",
        description="The original Hindi question text if translated, preserving source wording.",
    )

    @field_validator("subject", mode="before")
    @classmethod
    def normalize_subject(cls, v: Any) -> str:
        if not isinstance(v, str):
            return "Other"
        v_clean = v.strip()
        mapping = {
            "modern history": "Modern History",
            "history": "Modern History",
            "ancient history": "Ancient & Medieval History",
            "medieval history": "Ancient & Medieval History",
            "ancient & medieval history": "Ancient & Medieval History",
            "bihar": "Bihar Special",
            "bihar special": "Bihar Special",
            "bihar gk": "Bihar Special",
            "geography": "Geography",
            "polity": "Indian Polity",
            "indian polity": "Indian Polity",
            "constitution": "Indian Polity",
            "economy": "Economy",
            "economics": "Economy",
            "indian economy": "Economy",
            "science": "General Science",
            "general science": "General Science",
            "environment": "Environment",
            "ecology": "Environment",
            "current affairs": "Current Affairs",
            "ca": "Current Affairs",
        }
        return mapping.get(
            v_clean.lower(),
            v_clean
            if v_clean
            in [
                "Modern History",
                "Ancient & Medieval History",
                "Bihar Special",
                "Geography",
                "Indian Polity",
                "Economy",
                "General Science",
                "Environment",
                "Current Affairs",
                "Other",
            ]
            else "Other",
        )

    @field_validator("correct_option", mode="before")
    @classmethod
    def normalize_correct_option(cls, v: Any) -> str:
        if isinstance(v, str):
            s = v.strip().upper()
            if s in ("A", "B", "C", "D"):
                return s
            if s.startswith("A"):
                return "A"
            if s.startswith("B"):
                return "B"
            if s.startswith("C"):
                return "C"
            if s.startswith("D"):
                return "D"
        return "A"

    @field_validator("question", "option_a", "option_b", "option_c", "option_d", mode="before")
    @classmethod
    def clean_text_fields(cls, v: Any) -> str:
        if v is None:
            return "(Not available)"
        s = str(v).strip()
        return s if s else "(Not available)"


class ExtractedMockQuestionSet(BaseModel):
    """Schema for a collection of questions extracted from a PDF chunk."""

    questions: List[ExtractedMockQuestion] = Field(
        default_factory=list,
        description="List of all multiple-choice questions parsed from the PDF pages.",
    )


class WeeklyStrategyBriefing(BaseModel):
    """Schema for AI synthesized weekly study strategy."""

    executive_summary: str = Field(..., description="High-level evaluation of current readiness and priority.")
    daily_focus_tips: List[str] = Field(default_factory=list, description="Actionable recommendations for study days.")
    neglected_subject_alert: str = Field(default="", description="Subject needing urgent coverage.")
    exam_mindset_tip: str = Field(..., description="Motivational or psychological test-taking advice.")


class MnemonicAnchor(BaseModel):
    """Schema for AI-generated memory anchors and mnemonics."""

    mnemonic: str = Field(..., description="Catchy acronym, sentence mnemonic, or memory rhyme.")
    core_fact: str = Field(..., description="The fundamental fact or principle to remember.")
    trap_to_avoid: str = Field(..., description="The distractor trap BPSC commonly sets.")
    bihar_angle: str = Field(default="", description="Specific Bihar state relevance if any.")


class QuestionDeepDive(BaseModel):
    """Schema for high-yield exam intelligence on a question."""

    high_yield_facts: List[str] = Field(default_factory=list, description="3-5 critical related syllabus facts.")
    bpsc_trend_note: str = Field(..., description="Why BPSC tests this topic and recent trends.")
    likely_exam_variations: List[str] = Field(default_factory=list, description="Ways this topic could appear in future exams.")
    related_articles_or_dates: str = Field(default="", description="Key constitutional articles, sections, or dates.")


