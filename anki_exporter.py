"""Anki flashcard package (.apkg) generator for Question Lab.

Leverages the open-source genanki library to produce styled, interactive
spaced-repetition flashcards directly importable into Anki desktop and mobile.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List, Union
import pandas as pd

try:
    import genanki
    _HAS_GENANKI = True
except ImportError:
    _HAS_GENANKI = False

# Stable unique Model ID and CSS for Question Lab Flashcards
BPSC_ANKI_MODEL_ID = 1607392325

BPSC_CARD_CSS = """
.card {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 16px;
    text-align: left;
    color: #1e293b;
    background-color: #f8fafc;
    padding: 16px;
    line-height: 1.5;
}
.header-badge {
    display: inline-block;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-radius: 9999px;
    background: #e2e8f0;
    color: #475569;
    margin-bottom: 12px;
}
.badge-subject {
    background: #dbeafe;
    color: #1e40af;
    border: 1px solid #bfdbfe;
}
.badge-pyq {
    background: #fef3c7;
    color: #92400e;
    border: 1px solid #fde68a;
}
.question-stem {
    font-size: 17px;
    font-weight: 600;
    color: #0f172a;
    margin-bottom: 14px;
}
.options-grid {
    margin-top: 10px;
    margin-bottom: 14px;
}
.option-row {
    padding: 8px 12px;
    margin-bottom: 6px;
    border-radius: 8px;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    font-size: 14.5px;
}
.option-letter {
    font-weight: 700;
    color: #64748b;
    margin-right: 6px;
}
.correct-banner {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    color: #166534;
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 16px;
    font-weight: 700;
    margin-top: 12px;
    margin-bottom: 12px;
}
.explanation-box {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    padding: 12px 14px;
    border-radius: 8px;
    margin-top: 10px;
    font-size: 14px;
}
.distractor-box {
    background: #fffbeb;
    border: 1px solid #fef3c7;
    color: #92400e;
    padding: 10px 12px;
    border-radius: 8px;
    margin-top: 8px;
    font-size: 13.5px;
}
.concept-tag {
    font-size: 12px;
    color: #3b82f6;
    font-weight: 600;
    margin-top: 8px;
}
"""

BPSC_FRONT_TEMPLATE = """
<div class="card">
    <div>
        <span class="header-badge badge-subject">{{Subject}}</span>
        {{#Topic}}<span class="header-badge">{{Topic}}</span>{{/Topic}}
        {{#Source}}<span class="header-badge badge-pyq">{{Source}}</span>{{/Source}}
    </div>
    <div class="question-stem">{{Question}}</div>
    <div class="options-grid">
        <div class="option-row"><span class="option-letter">(A)</span> {{Option_A}}</div>
        <div class="option-row"><span class="option-letter">(B)</span> {{Option_B}}</div>
        <div class="option-row"><span class="option-letter">(C)</span> {{Option_C}}</div>
        <div class="option-row"><span class="option-letter">(D)</span> {{Option_D}}</div>
    </div>
</div>
"""

BPSC_BACK_TEMPLATE = """
{{FrontSide}}
<hr id="answer">
<div class="card">
    <div class="correct-banner">
        ✅ Correct Answer: Option {{Correct_Option}} — {{Correct_Text}}
    </div>
    {{#Explanation}}
    <div class="explanation-box">
        <strong>💡 Explanation:</strong><br/>
        {{Explanation}}
    </div>
    {{/Explanation}}
    {{#Distractor_Notes}}
    <div class="distractor-box">
        <strong>⚠️ Distractor Trap Analysis:</strong><br/>
        {{Distractor_Notes}}
    </div>
    {{/Distractor_Notes}}
    {{#Concept_Tested}}
    <div class="concept-tag">📌 Concept Tested: {{Concept_Tested}}</div>
    {{/Concept_Tested}}
</div>
"""


def _get_bpsc_model() -> Any:
    """Create or return the genanki Model instance."""
    if not _HAS_GENANKI:
        raise ImportError("genanki is not installed. Run 'pip install genanki'.")
    return genanki.Model(
        BPSC_ANKI_MODEL_ID,
        "Question Lab Card",
        fields=[
            {"name": "Question"},
            {"name": "Option_A"},
            {"name": "Option_B"},
            {"name": "Option_C"},
            {"name": "Option_D"},
            {"name": "Correct_Option"},
            {"name": "Correct_Text"},
            {"name": "Explanation"},
            {"name": "Distractor_Notes"},
            {"name": "Concept_Tested"},
            {"name": "Subject"},
            {"name": "Topic"},
            {"name": "Source"},
        ],
        templates=[
            {
                "name": "BPSC Multiple Choice",
                "qfmt": BPSC_FRONT_TEMPLATE,
                "afmt": BPSC_BACK_TEMPLATE,
            }
        ],
        css=BPSC_CARD_CSS,
    )


def generate_anki_apkg_bytes(
    questions: Union[List[Dict[str, Any]], pd.DataFrame],
    deck_name: str = "Question Lab Flashcards",
    deck_id: int = 2059481923,
) -> bytes:
    """Generate an Anki .apkg package as in-memory bytes.

    Args:
        questions: List of question dicts or pandas DataFrame.
        deck_name: Name of the Anki deck shown inside Anki app.
        deck_id: Unique integer identifier for the deck.

    Returns:
        Raw bytes of the .apkg zip archive.
    """
    if not _HAS_GENANKI:
        raise ImportError("genanki is not installed. Please install it to export .apkg packages.")

    if isinstance(questions, pd.DataFrame):
        rows = questions.to_dict("records")
    elif isinstance(questions, list):
        rows = questions
    else:
        rows = []

    if not rows:
        raise ValueError("Cannot generate Anki package: questions list or DataFrame is empty.")

    model = _get_bpsc_model()
    deck = genanki.Deck(deck_id, deck_name)

    for r in rows:
        stem = str(r.get("question", "")).strip()
        if not stem:
            continue
        opt_a = str(r.get("option_a", "")).strip()
        opt_b = str(r.get("option_b", "")).strip()
        opt_c = str(r.get("option_c", "")).strip()
        opt_d = str(r.get("option_d", "")).strip()
        cor = str(r.get("correct_option", "")).strip().upper()
        if cor not in ("A", "B", "C", "D"):
            cor = "A"

        opts_map = {"A": opt_a, "B": opt_b, "C": opt_c, "D": opt_d}
        cor_text = opts_map.get(cor, "")

        exp = str(r.get("explanation", "")).strip()
        dist = str(r.get("distractor_notes", "")).strip()
        concept = str(r.get("concept_tested", "")).strip()
        subj = str(r.get("subject", "General")).strip()
        topic = str(r.get("topic", "General")).strip()
        source = str(r.get("source_name", r.get("source_type", ""))).strip()

        # Build clean tags for Anki tag browser
        subj_tag = subj.replace(" ", "_").replace("&", "and")
        top_tag = topic.replace(" ", "_")
        tags = ["BPSC", f"BPSC::{subj_tag}"]
        if top_tag and top_tag != "General":
            tags.append(f"BPSC::{subj_tag}::{top_tag}")

        note = genanki.Note(
            model=model,
            fields=[
                stem,
                opt_a,
                opt_b,
                opt_c,
                opt_d,
                cor,
                cor_text,
                exp,
                dist,
                concept,
                subj,
                topic,
                source,
            ],
            tags=tags,
        )
        deck.add_note(note)

    # Package deck into temporary file and read back as bytes
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".apkg")
    try:
        os.close(tmp_fd)
        genanki.Package(deck).write_to_file(tmp_path)
        with open(tmp_path, "rb") as f:
            pkg_bytes = f.read()
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    return pkg_bytes
