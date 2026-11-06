"""OMR Sheet Generator, Question Paper Compiler, and Offline Exam Evaluation Engine.

Provides high-resolution, print-ready PDF generation for:
1. Authentic BPSC Prelims OMR Answer Sheets (with barcode/alignment markers, candidate roll grid, and bubble matrix).
2. Official BPSC-style Question Papers with standard formatting and examination instructions.
3. Computer Vision / Gemini Vision analysis to grade uploaded OMR sheets and checked papers.
"""

from __future__ import annotations

import io
import json
import math
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
from PIL import Image

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.pdfgen import canvas
    from reportlab.platypus import (
        HRFlowable,
        KeepTogether,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    _HAS_REPORTLAB = True
except ImportError:
    _HAS_REPORTLAB = False


# -----------------------------------------------------------------------------
# 1. BPSC OMR Sheet PDF Generator
# -----------------------------------------------------------------------------

def generate_bpsc_omr_pdf(
    question_count: int = 150,
    exam_title: str = "BPSC Combined Competitive Examination (Prelims)",
    series: str = "A",
    candidate_roll: str = "1049281",
) -> bytes:
    """Generate a high-precision, authentic A4 BPSC OMR Answer Sheet PDF."""
    if not _HAS_REPORTLAB:
        raise ImportError("reportlab is required for PDF generation. Install with 'pip install reportlab'.")

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4  # 595.27 x 841.89 points

    # Registration corner markers for OMR optical scanners / CV alignment
    marker_size = 12
    margin = 18
    c.setFillColor(colors.black)
    c.rect(margin, page_h - margin - marker_size, marker_size, marker_size, fill=1)
    c.rect(page_w - margin - marker_size, page_h - margin - marker_size, marker_size, marker_size, fill=1)
    c.rect(margin, margin, marker_size, marker_size, fill=1)
    c.rect(page_w - margin - marker_size, margin, marker_size, marker_size, fill=1)

    # Header Box
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(page_w / 2, page_h - 36, "BIHAR PUBLIC SERVICE COMMISSION, PATNA")
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(page_w / 2, page_h - 50, "OMR ANSWER SHEET / ओ.एम.आर. उत्तर पत्रक")
    c.setFont("Helvetica", 8.5)
    c.drawCentredString(page_w / 2, page_h - 63, f"{exam_title} · SERIES: {series.upper()}")

    # Divider bar
    c.setLineWidth(1)
    c.line(margin + 5, page_h - 70, page_w - margin - 5, page_h - 70)

    # Candidate Meta Block (Roll No & Series Bubbles)
    top_y = page_h - 78
    box_h = 74
    c.setStrokeColor(colors.HexColor("#334155"))
    c.setFillColor(colors.HexColor("#f8fafc"))
    c.roundRect(margin + 5, top_y - box_h, page_w - (2 * margin) - 10, box_h, 4, stroke=1, fill=1)

    # Roll Number Grid
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(margin + 15, top_y - 12, "CANDIDATE ROLL NUMBER / अनुक्रमांक:")
    roll_str = str(candidate_roll).zfill(7)[:7]
    cell_w = 14
    cell_h = 14
    start_x = margin + 175
    for i, ch in enumerate(roll_str):
        c.setStrokeColor(colors.black)
        c.rect(start_x + (i * cell_w), top_y - 18, cell_w, cell_h, stroke=1, fill=0)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(start_x + (i * cell_w) + (cell_w / 2), top_y - 15, ch)

    # Booklet Series Selection
    c.setFont("Helvetica-Bold", 8)
    c.drawString(margin + 300, top_y - 12, "BOOKLET SERIES / प्रश्न पुस्तिका श्रृंखला:")
    s_x = margin + 465
    for s_opt in ["A", "B", "C", "D"]:
        is_sel = (s_opt == series.upper())
        c.setStrokeColor(colors.black)
        c.setFillColor(colors.black if is_sel else colors.white)
        c.circle(s_x, top_y - 10, 5, stroke=1, fill=1 if is_sel else 0)
        c.setFillColor(colors.white if is_sel else colors.black)
        c.setFont("Helvetica-Bold", 6.5)
        c.drawCentredString(s_x, top_y - 12.5, s_opt)
        s_x += 18

    # Instructions line
    c.setFillColor(colors.HexColor("#b91c1c"))
    c.setFont("Helvetica-Bold", 7)
    c.drawString(
        margin + 15,
        top_y - 32,
        "IMPORTANT: Use Black / Blue Ball Point Pen only. Darken only ONE bubble completely for each question. Negative marking (-0.33) applies."
    )

    # Signature Boxes
    c.setStrokeColor(colors.HexColor("#94a3b8"))
    c.setFillColor(colors.white)
    sig_w = 180
    sig_h = 24
    c.rect(margin + 15, top_y - 68, sig_w, sig_h, stroke=1, fill=1)
    c.rect(page_w - margin - 15 - sig_w, top_y - 68, sig_w, sig_h, stroke=1, fill=1)
    c.setFillColor(colors.HexColor("#475569"))
    c.setFont("Helvetica", 6.5)
    c.drawString(margin + 20, top_y - 63, "Candidate's Full Signature in Running Hand")
    c.drawString(page_w - margin - 10 - sig_w, top_y - 63, "Invigilator's Signature & Stamp")

    # -------------------------------------------------------------------------
    # Answer Bubble Grid
    # -------------------------------------------------------------------------
    grid_top_y = top_y - box_h - 12
    grid_bottom_y = margin + 25
    avail_h = grid_top_y - grid_bottom_y

    total_q = max(1, min(150, int(question_count)))
    if total_q <= 25:
        num_cols = 1
    elif total_q <= 50:
        num_cols = 2
    elif total_q <= 100:
        num_cols = 4
    else:
        num_cols = 5

    qs_per_col = math.ceil(total_q / num_cols)
    row_h = min(17.0, avail_h / (qs_per_col + 1.5))
    col_w = (page_w - (2 * margin) - 10) / num_cols

    for c_idx in range(num_cols):
        c_start_x = margin + 5 + (c_idx * col_w)
        # Column Header Box
        c.setStrokeColor(colors.HexColor("#cbd5e1"))
        c.setFillColor(colors.HexColor("#e2e8f0"))
        c.rect(c_start_x + 2, grid_top_y - row_h, col_w - 4, row_h, stroke=1, fill=1)
        c.setFillColor(colors.HexColor("#1e293b"))
        c.setFont("Helvetica-Bold", 7)
        c.drawString(c_start_x + 6, grid_top_y - row_h + 4.5, "Q#")
        # Header A B C D letters
        b_spacing = (col_w - 38) / 3.0
        for opt_idx, opt_letter in enumerate(["A", "B", "C", "D"]):
            bx = c_start_x + 26 + (opt_idx * b_spacing)
            c.drawCentredString(bx, grid_top_y - row_h + 4.5, opt_letter)

        # Draw Question Rows for this column
        for r_idx in range(qs_per_col):
            q_num = (c_idx * qs_per_col) + r_idx + 1
            if q_num > total_q:
                break
            curr_y = grid_top_y - ((r_idx + 2) * row_h)
            # Alternate light zebra striping
            if r_idx % 2 == 1:
                c.setFillColor(colors.HexColor("#f8fafc"))
                c.rect(c_start_x + 2, curr_y - 2, col_w - 4, row_h, stroke=0, fill=1)

            c.setFillColor(colors.HexColor("#0f172a"))
            c.setFont("Helvetica-Bold", 7)
            c.drawString(c_start_x + 6, curr_y + 1.5, f"{q_num:2d}")

            # Draw Bubbles A, B, C, D
            for opt_idx, opt_letter in enumerate(["A", "B", "C", "D"]):
                bx = c_start_x + 26 + (opt_idx * b_spacing)
                by = curr_y + 3.5
                c.setStrokeColor(colors.HexColor("#475569"))
                c.setLineWidth(0.65)
                c.circle(bx, by, 4.2, stroke=1, fill=0)
                c.setFillColor(colors.HexColor("#475569"))
                c.setFont("Helvetica", 5.5)
                c.drawCentredString(bx, by - 1.8, opt_letter)

    # Footer instructions
    c.setFillColor(colors.HexColor("#64748b"))
    c.setFont("Helvetica", 7)
    c.drawCentredString(
        page_w / 2,
        margin + 8,
        "Question Lab · Computer Vision & OMR Evaluation System · Do Not Fold or Mutilate This Sheet"
    )

    c.showPage()
    c.save()
    return buf.getvalue()


# -----------------------------------------------------------------------------
# 2. BPSC Question Paper PDF Generator
# -----------------------------------------------------------------------------

def generate_bpsc_question_paper_pdf(
    questions: Union[List[Dict[str, Any]], pd.DataFrame],
    exam_title: str = "BPSC Combined Competitive Examination (Prelims)",
    series: str = "A",
    duration_minutes: int = 120,
    max_marks: int = 150,
) -> bytes:
    """Generate an official BPSC-formatted Question Booklet PDF."""
    if not _HAS_REPORTLAB:
        raise ImportError("reportlab is required for PDF generation. Install with 'pip install reportlab'.")

    if isinstance(questions, pd.DataFrame):
        q_list = questions.to_dict("records")
    else:
        q_list = list(questions)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "BPSC_Title",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=14,
        alignment=1,
        spaceAfter=4,
        textColor=colors.HexColor("#0f172a"),
    )
    subtitle_style = ParagraphStyle(
        "BPSC_SubTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        alignment=1,
        spaceAfter=2,
        textColor=colors.HexColor("#334155"),
    )
    meta_style = ParagraphStyle(
        "BPSC_Meta",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        alignment=1,
        spaceAfter=8,
        textColor=colors.HexColor("#475569"),
    )
    instr_style = ParagraphStyle(
        "BPSC_Instr",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#334155"),
    )
    q_stem_style = ParagraphStyle(
        "BPSC_QStem",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13.5,
        spaceAfter=4,
        textColor=colors.HexColor("#0f172a"),
    )
    option_style = ParagraphStyle(
        "BPSC_Opt",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        leftIndent=14,
        spaceAfter=2,
        textColor=colors.HexColor("#1e293b"),
    )

    story: List[Any] = []

    # Booklet Header Block
    story.append(Paragraph("BIHAR PUBLIC SERVICE COMMISSION, PATNA", title_style))
    story.append(Paragraph(exam_title.upper(), subtitle_style))
    story.append(
        Paragraph(
            f"<strong>BOOKLET SERIES: {series.upper()}</strong> &nbsp;|&nbsp; "
            f"Time Allowed: <strong>{duration_minutes} Minutes</strong> &nbsp;|&nbsp; "
            f"Maximum Marks: <strong>{max_marks}</strong>",
            meta_style,
        )
    )
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#334155"), spaceAfter=6))

    # Instructions to Candidate
    instr_text = (
        "<strong>INSTRUCTIONS TO CANDIDATES:</strong><br/>"
        "1. This question paper booklet contains multiple-choice questions. Each question has four choices (A, B, C, D).<br/>"
        "2. Candidates must mark their answers only on the separate OMR Answer Sheet provided using a Black or Blue ballpoint pen.<br/>"
        "3. Each correct answer carries 1 mark. There is negative marking of <strong>-0.33 (1/3rd penalty)</strong> for every wrong answer.<br/>"
        "4. No marks will be deducted for unattempted questions. Do not write anything on the OMR sheet except required details."
    )
    story.append(Paragraph(instr_text, instr_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceBefore=6, spaceAfter=10))

    # Questions Enumeration
    for idx, q in enumerate(q_list, start=1):
        q_elements = []
        stem_raw = str(q.get("question", "")).strip()
        stem_html = f"<strong>Q.{idx}</strong> &nbsp; {stem_raw}"
        q_elements.append(Paragraph(stem_html, q_stem_style))

        opt_a = str(q.get("option_a", "")).strip()
        opt_b = str(q.get("option_b", "")).strip()
        opt_c = str(q.get("option_c", "")).strip()
        opt_d = str(q.get("option_d", "")).strip()

        q_elements.append(Paragraph(f"<strong>(A)</strong> &nbsp;{opt_a}", option_style))
        q_elements.append(Paragraph(f"<strong>(B)</strong> &nbsp;{opt_b}", option_style))
        q_elements.append(Paragraph(f"<strong>(C)</strong> &nbsp;{opt_c}", option_style))
        q_elements.append(Paragraph(f"<strong>(D)</strong> &nbsp;{opt_d}", option_style))
        q_elements.append(Spacer(1, 8))

        story.append(KeepTogether(q_elements))

    doc.build(story)
    return buf.getvalue()


# -----------------------------------------------------------------------------
# 3. OMR Evaluation & Deterministic Scoring
# -----------------------------------------------------------------------------

def evaluate_omr_response_data(
    detected_answers: Dict[int, str],
    official_key: Dict[int, str],
    questions_map: Optional[Dict[int, Dict[str, Any]]] = None,
    negative_rate: float = 0.33,
) -> Dict[str, Any]:
    """Grade detected OMR bubble selections against the official answer key."""
    total_q = len(official_key)
    correct_count = 0
    incorrect_count = 0
    unattempted_count = 0
    breakdown: List[Dict[str, Any]] = []

    for qno, cor_opt in sorted(official_key.items()):
        sel_opt = detected_answers.get(qno, "-").strip().upper()
        if sel_opt not in ("A", "B", "C", "D"):
            sel_opt = "-"

        q_info = (questions_map or {}).get(qno, {})
        is_cor = (sel_opt == cor_opt)

        if sel_opt == "-":
            unattempted_count += 1
            status = "Unattempted"
        elif is_cor:
            correct_count += 1
            status = "Correct"
        else:
            incorrect_count += 1
            status = "Incorrect"

        breakdown.append({
            "qno": qno,
            "selected_option": sel_opt,
            "correct_option": cor_opt,
            "is_correct": is_cor,
            "status": status,
            "question": q_info.get("question", f"Question {qno}"),
            "subject": q_info.get("subject", "General"),
            "topic": q_info.get("topic", "General"),
            "explanation": q_info.get("explanation", ""),
            "distractor_notes": q_info.get("distractor_notes", ""),
        })

    attempted = correct_count + incorrect_count
    accuracy = round((correct_count / attempted * 100), 1) if attempted > 0 else 0.0
    penalty_lost = round(incorrect_count * negative_rate, 2)
    net_score = round(correct_count - penalty_lost, 2)

    return {
        "total_questions": total_q,
        "attempted": attempted,
        "unattempted": unattempted_count,
        "correct": correct_count,
        "incorrect": incorrect_count,
        "accuracy": accuracy,
        "penalty_lost": penalty_lost,
        "net_score": net_score,
        "negative_rate": negative_rate,
        "breakdown": breakdown,
    }


# -----------------------------------------------------------------------------
# 4. Computer Vision & Gemini Vision OMR Reader
# -----------------------------------------------------------------------------

def extract_answers_from_omr_document(
    file_bytes: bytes,
    file_name: str,
    total_questions: int,
    client: Any = None,
) -> Dict[int, str]:
    """Extract darkened bubbles from a scanned/photographed OMR sheet or checked answer key.

    Uses official Google Gemini Vision multimodal analysis to identify marked bubbles.
    Returns a dict mapping question number (1..N) to choice ('A', 'B', 'C', 'D', or '-').
    """
    from config import get_gemini_analysis_model, is_gemini_configured
    import ai_service
    from google.genai import types

    if not is_gemini_configured() and client is None:
        raise ai_service.AIServiceError("Gemini API key is not configured for OMR Vision Grading.")

    ai_client = client or ai_service._get_client()
    model = get_gemini_analysis_model()

    # Determine MIME type
    f_lower = file_name.lower()
    if f_lower.endswith(".pdf"):
        mime = "application/pdf"
    elif f_lower.endswith(".png"):
        mime = "image/png"
    elif f_lower.endswith(".webp"):
        mime = "image/webp"
    else:
        mime = "image/jpeg"

    doc_part = types.Part.from_bytes(data=file_bytes, mime_type=mime)

    prompt = f"""You are a high-precision Optical Mark Recognition (OMR) grading system for the Bihar Public Service Commission (BPSC).
Analyze this uploaded OMR sheet or marked question paper.
Total expected questions: {total_questions}.

INSTRUCTIONS:
1. Identify the marked/darkened bubble or chosen answer for every question from 1 to {total_questions}.
2. If bubble A is darkened, record 'A'.
3. If bubble B is darkened, record 'B'.
4. If bubble C is darkened, record 'C'.
5. If bubble D is darkened, record 'D'.
6. If no circle is darkened, or if a question is blank/skipped, record '-'.
7. If multiple circles are darkened or crossed out causing an invalid mark, record '-'.

Return a JSON object in this exact schema:
{{
  "detected_answers": {{
    "1": "A",
    "2": "B",
    "3": "-",
    ...
    "{total_questions}": "C"
  }}
}}
Ensure every question number from 1 to {total_questions} is included as a string key in 'detected_answers'.
"""

    try:
        response = ai_client.models.generate_content(
            model=model,
            contents=[doc_part, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
        data = json.loads(response.text)
        detected_raw = data.get("detected_answers", {})
        result: Dict[int, str] = {}
        for k, v in detected_raw.items():
            try:
                q_int = int(k)
                val = str(v).strip().upper()
                result[q_int] = val if val in ("A", "B", "C", "D") else "-"
            except ValueError:
                continue

        # Ensure all questions up to total_questions have an entry
        for i in range(1, total_questions + 1):
            if i not in result:
                result[i] = "-"
        return result
    except Exception as exc:
        raise ai_service.AIServiceError(f"OMR sheet analysis failed: {exc}") from exc


# -----------------------------------------------------------------------------
# 5. Gemini AI Performance Diagnostic Analysis for OMR Papers
# -----------------------------------------------------------------------------

def generate_omr_ai_analysis(
    eval_result: Dict[str, Any],
    exam_title: str = "BPSC Offline Simulation",
    client: Any = None,
) -> str:
    """Generate an in-depth AI coaching and improvement diagnosis from evaluated OMR test data.

    Uses Gemini Flash medium model to evaluate negative marking risk, knowledge gaps,
    subject breakdown, and actionable revision steps.
    """
    from config import get_gemini_analysis_model, is_gemini_configured
    import ai_service
    from google.genai import types

    if not is_gemini_configured() and client is None:
        return "⚠️ Gemini API is not configured. Please add your GEMINI_API_KEY in Settings or .env to receive AI diagnostic coaching."

    ai_client = client or ai_service._get_client()
    model = get_gemini_analysis_model()

    # Aggregate subject stats
    breakdown = eval_result.get("breakdown", [])
    subject_map: Dict[str, Dict[str, int]] = {}
    mistakes_sample = []
    for item in breakdown:
        subj = item.get("subject", "General")
        status = item.get("status", "Unattempted")
        if subj not in subject_map:
            subject_map[subj] = {"total": 0, "correct": 0, "incorrect": 0, "unattempted": 0}
        subject_map[subj]["total"] += 1
        if status == "Correct":
            subject_map[subj]["correct"] += 1
        elif status == "Incorrect":
            subject_map[subj]["incorrect"] += 1
            if len(mistakes_sample) < 6:
                mistakes_sample.append({
                    "q_num": item.get("q_num"),
                    "question": str(item.get("question", ""))[:120],
                    "marked": item.get("detected_option"),
                    "correct": item.get("correct_option"),
                    "subject": subj,
                })
        else:
            subject_map[subj]["unattempted"] += 1

    prompt = f"""You are the Lead Exam Strategist and AI Performance Coach for Bihar Public Service Commission (BPSC) Civil Services.
Analyze this candidate's completed offline OMR practice examination.

Exam: {exam_title}
Performance Data:
- Total Questions: {eval_result.get('total_questions', 0)}
- Questions Attempted: {eval_result.get('attempted', 0)} ({eval_result.get('unattempted', 0)} unattempted/skipped)
- Correct Answers: {eval_result.get('correct', 0)} (+1.00 marks each)
- Incorrect Answers: {eval_result.get('incorrect', 0)} (-0.33 negative marking penalty each)
- Penalty Bleed: -{eval_result.get('penalty_lost', 0):.2f} marks lost to wrong guesses
- Net Score: {eval_result.get('net_score', 0):.2f} / {eval_result.get('total_questions', 0)} ({eval_result.get('accuracy', 0):.1f}% accuracy)

Subject-Wise Breakdown:
{json.dumps(subject_map, indent=2)}

Sample Questions Marked Incorrect:
{json.dumps(mistakes_sample, indent=2)}

Provide an authoritative, candid, encouraging diagnostic report formatted in Markdown with the following clear sections:
### 1. 📊 Executive Scorecard & Cutoff Prognosis
- Evaluate if this net score meets expected BPSC Prelims cutoff thresholds (~60-65% net).
- Comment on attempt aggressiveness (did they attempt too many uncertain questions or play it too safe?).

### 2. 🩸 Negative Marking Bleed Analysis
- Specifically analyze the {eval_result.get('incorrect', 0)} incorrect responses and {eval_result.get('penalty_lost', 0):.2f} penalty points lost.
- Did the negative penalty drag down their percentile? Explain how strategic skips would have protected marks.

### 3. 🎯 Subject Strengths vs Vulnerabilities
- Highlight top performing subjects vs vulnerable domains requiring immediate attention (Bihar Special, History, Science, Mental Ability, etc.).

### 4. 🚀 3 High-Yield Action Steps for Revision
- Provide 3 concrete, targeted study and practice directives for the coming week to eliminate these exact errors.
"""
    try:
        response = ai_client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
            ),
        )
        return response.text or "No diagnostic feedback generated."
    except Exception as exc:
        return f"⚠️ Diagnostic analysis generation failed: {exc}"
