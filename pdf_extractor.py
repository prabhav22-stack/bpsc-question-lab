"""PDF extraction and OCR processing engine for BPSC Question Lab v2.0.

Provides automated extraction of multiple-choice questions from both:
1. Digital / OCR Text PDFs (via pypdf text extraction + Gemini structured categorization)
2. Scanned Image PDFs (via pypdf slicing + Gemini multimodal Vision OCR)

Automatically classifies and sorts extracted questions into the 10 standard
BPSC / UPSC syllabus subjects.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import pypdf

import ai_service
import config
from schemas import ExtractedMockQuestion, ExtractedMockQuestionSet

try:
    from google import genai
    from google.genai import types

    _HAS_GENAI = True
except ImportError:
    _HAS_GENAI = False


SYSTEM_PDF_MOCK_EXTRACTOR = """You are an expert examination archivist and syllabus classifier for BPSC CCE & UPSC Prelims.
Your task is to analyze mock test exam paper pages (either formatted digital text or scanned PDF page images) and extract every multiple-choice question (MCQ).

For every question found:
1. Extract the full question stem.
2. Extract the text for all 4 options (A, B, C, D). If options in the source are labeled 1, 2, 3, 4 or (a), (b), (c), (d), map them cleanly to A, B, C, D.
3. Identify the correct answer option:
   - If an official answer key, solution table, or marked answer is present in the text, use it.
   - If no answer key is visible in this chunk, accurately determine the correct option using authoritative academic knowledge.
4. Provide a clear, factual explanation explaining why the correct option is right.
5. Crucially: Classify and sort the question into exactly ONE of the following standard syllabus subjects:
   - "Modern History" (Revolt of 1857, British rule, Freedom movement, INC, Governor Generals)
   - "Ancient & Medieval History" (Indus Valley, Vedic, Mauryan, Gupta, Delhi Sultanate, Mughals)
   - "Bihar Special" (History of Bihar, Champaran, Kunwar Singh, Rivers of Bihar, Bihar Geography, Census, State economy, Bihar culture)
   - "Geography" (Physical geography, Indian rivers, climate, soils, minerals, world geography)
   - "Indian Polity" (Constitution, Articles, Preamble, Fundamental Rights, Parliament, Supreme Court, Panchayati Raj)
   - "Economy" (Macroeconomics, RBI, Banking, Budget, Inflation, Schemes, Planning)
   - "General Science" (Physics, Chemistry, Biology, Diseases, Human anatomy, Scientific instruments)
   - "Environment" (Ecology, Biodiversity, Wildlife parks, Climate change, Environmental treaties)
   - "Current Affairs" (Recent summits, awards, sports, appointments, government initiatives, indices)
   - "Other" (Reasoning, Aptitude, or unclassified)
6. Extract a concise topic (e.g. "Fundamental Rights", "Drain of Wealth", "Rivers of Bihar").
7. Estimate difficulty ("Easy", "Medium", "Hard").
"""


def detect_pdf_type(reader: pypdf.PdfReader) -> Tuple[bool, str, int]:
    """Detect whether a PDF has digital text or is a scanned image document.

    Returns:
        (is_scanned: bool, mode_description: str, total_pages: int)
    """
    total_pages = len(reader.pages)
    if total_pages == 0:
        return False, "Empty PDF Document", 0

    # Sample up to first 8 pages
    sample_count = min(8, total_pages)
    total_chars = 0
    for i in range(sample_count):
        try:
            txt = reader.pages[i].extract_text() or ""
            total_chars += len(txt.strip())
        except Exception:
            pass

    avg_chars = total_chars / sample_count
    if avg_chars < 50:
        return True, "Scanned Image PDF (Multimodal Vision OCR)", total_pages
    return False, "Digital / OCR Text PDF (Direct Text Extraction)", total_pages


def slice_pdf_chunk(reader: pypdf.PdfReader, start_page: int, end_page: int) -> bytes:
    """Slice a range of pages from reader into standalone PDF bytes."""
    writer = pypdf.PdfWriter()
    for page_idx in range(start_page, min(end_page, len(reader.pages))):
        writer.add_page(reader.pages[page_idx])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def extract_mock_questions_from_pdf(
    pdf_bytes: bytes,
    mock_title: str = "Uploaded Mock Test",
    target_exam: str = "BPSC",
    page_start: Optional[int] = None,
    page_end: Optional[int] = None,
    chunk_size: int = 4,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Extract and categorize all MCQs from an uploaded mock test PDF.

    Supports both digital OCR text and scanned PDF images with automatic
    subject classification into standard BPSC/UPSC subjects.

    Returns:
        (questions_list, extraction_stats)
    """
    if not config.is_gemini_configured():
        raise ai_service.AIServiceError(
            "Gemini AI is not configured. Please add your GEMINI_API_KEY to extract and classify questions."
        )

    client = ai_service._get_client()
    model = config.get_gemini_model()

    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    except Exception as exc:
        raise ValueError(f"Failed to read PDF document: {exc}") from exc

    total_doc_pages = len(reader.pages)
    if total_doc_pages == 0:
        raise ValueError("The uploaded PDF has no pages.")

    is_scanned, mode_desc, _ = detect_pdf_type(reader)

    # Determine page bounds (1-indexed for user, 0-indexed for reader)
    s_idx = max(0, (page_start - 1) if page_start else 0)
    e_idx = min(total_doc_pages, page_end if page_end else total_doc_pages)
    if s_idx >= e_idx:
        s_idx = 0
        e_idx = total_doc_pages

    pages_to_process = list(range(s_idx, e_idx))
    total_to_process = len(pages_to_process)
    file_hash = hashlib.sha256(pdf_bytes).hexdigest()

    # Divide into chunks
    chunks: List[Tuple[int, int]] = []
    for i in range(0, total_to_process, chunk_size):
        c_start = pages_to_process[i]
        c_end = pages_to_process[min(i + chunk_size - 1, total_to_process - 1)] + 1
        chunks.append((c_start, c_end))

    all_extracted: List[Dict[str, Any]] = []
    subject_counts: Dict[str, int] = {}
    seen_stems: set = set()
    internal_duplicates = 0

    if progress_callback:
        progress_callback(
            0.05,
            f"Detected: {mode_desc} · Processing {total_to_process} page(s) in {len(chunks)} batch(es)...",
        )

    for chunk_idx, (c_start, c_end) in enumerate(chunks):
        p_pct = 0.05 + 0.90 * (chunk_idx / max(1, len(chunks)))
        chunk_label = f"Pages {c_start + 1} to {c_end}"
        if progress_callback:
            progress_callback(
                p_pct,
                f"Extracting & categorizing {chunk_label} ({chunk_idx + 1}/{len(chunks)})...",
            )

        try:
            prompt_instruction = (
                f"Analyze these mock examination paper pages ({chunk_label}) for '{mock_title}'.\n"
                f"Target exam: {target_exam}.\n"
                "Extract all multiple-choice questions found on these pages.\n"
                "For each question, accurately categorize its 'subject' into one of the 10 standard syllabus subjects:\n"
                "Modern History, Ancient & Medieval History, Bihar Special, Geography, Indian Polity, "
                "Economy, General Science, Environment, Current Affairs, Other.\n"
                "If no questions are on these pages (e.g. cover page, blank page, instructions), return an empty list."
            )

            req_config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PDF_MOCK_EXTRACTOR,
                response_mime_type="application/json",
                response_schema=ExtractedMockQuestionSet,
                temperature=0.2,
            )

            if is_scanned:
                # Sliced scanned sub-PDF as multimodal byte Part
                sub_bytes = slice_pdf_chunk(reader, c_start, c_end)
                pdf_part = types.Part.from_bytes(data=sub_bytes, mime_type="application/pdf")
                response = client.models.generate_content(
                    model=model,
                    contents=[pdf_part, prompt_instruction],
                    config=req_config,
                )
            else:
                # Digital text chunk
                chunk_texts: List[str] = []
                for p_num in range(c_start, c_end):
                    t = reader.pages[p_num].extract_text() or ""
                    if t.strip():
                        chunk_texts.append(f"--- Page {p_num + 1} ---\n{t}")
                combined_text = "\n\n".join(chunk_texts)

                if len(combined_text.strip()) < 50:
                    # Fallback to vision if page text extraction returned almost nothing
                    sub_bytes = slice_pdf_chunk(reader, c_start, c_end)
                    pdf_part = types.Part.from_bytes(data=sub_bytes, mime_type="application/pdf")
                    contents_payload = [pdf_part, prompt_instruction]
                else:
                    contents_payload = [f"{prompt_instruction}\n\nPAGE CONTENT:\n{combined_text}"]

                response = client.models.generate_content(
                    model=model,
                    contents=contents_payload,
                    config=req_config,
                )

            if response.text:
                parsed_json = json.loads(response.text)
                q_set = ExtractedMockQuestionSet.model_validate(parsed_json)
                for q in q_set.questions:
                    # Deduplicate questions within the document
                    raw_stem = q.question.strip()
                    s_clean = re.sub(
                        r"^(?:\(?\d{1,4}\)?[\.\:\-\s]+|q(?:uestion)?\s*[\.\:\-]?\s*\d{1,4}[\.\)\:\-\s]+)",
                        "",
                        raw_stem,
                        flags=re.IGNORECASE,
                    )
                    norm_stem = re.sub(r"\s+", " ", s_clean.lower()).rstrip("?.:;! \t\n\r")
                    if norm_stem in seen_stems:
                        internal_duplicates += 1
                        continue
                    seen_stems.add(norm_stem)

                    # Prepare database-ready dictionary
                    q_dict = {
                        "exam": target_exam,
                        "subject": q.subject,
                        "topic": q.topic.strip() or "General",
                        "question": raw_stem,
                        "option_a": q.option_a.strip(),
                        "option_b": q.option_b.strip(),
                        "option_c": q.option_c.strip(),
                        "option_d": q.option_d.strip(),
                        "correct_option": q.correct_option,
                        "explanation": q.explanation.strip(),
                        "distractor_notes": q.distractor_notes.strip(),
                        "concept_tested": q.concept_tested.strip(),
                        "difficulty": q.difficulty,
                        "question_type": q.question_type,
                        "source_type": "Mock question",
                        "source_name": mock_title.strip() or "Uploaded Mock Test",
                        "exam_edition": f"{mock_title.strip()} (Mock PDF)",
                        "is_ai_generated": 0,
                        "answer_key_status": "Extracted & Verified",
                    }
                    all_extracted.append(q_dict)
                    subj = q.subject
                    subject_counts[subj] = subject_counts.get(subj, 0) + 1

        except Exception as exc:
            # Continue processing remaining chunks rather than aborting entirely
            pass

    if progress_callback:
        progress_callback(
            1.0,
            f"Extraction complete: {len(all_extracted)} question(s) parsed and categorized."
            + (f" ({internal_duplicates} repeated question(s) skipped in document)" if internal_duplicates > 0 else ""),
        )

    stats = {
        "mode": mode_desc,
        "is_scanned": is_scanned,
        "total_doc_pages": total_doc_pages,
        "pages_processed": total_to_process,
        "total_extracted": len(all_extracted),
        "internal_duplicates_skipped": internal_duplicates,
        "file_hash": file_hash,
        "subject_counts": subject_counts,
        "mock_title": mock_title,
    }

    return all_extracted, stats
