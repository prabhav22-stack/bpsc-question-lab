"""Audio Speech Synthesis & Exam Podcasting Engine for Question Lab.

Leverages Microsoft Edge's free Neural TTS (edge-tts) to provide natural,
bilingual Indian voices for question listening, distractor breakdowns,
and daily current affairs revision podcasts without paid API keys.
"""

from __future__ import annotations

import asyncio
import io
import re
from typing import Any, Dict, List, Optional

try:
    import edge_tts
    _HAS_EDGE_TTS = True
except ImportError:
    _HAS_EDGE_TTS = False

INDIAN_VOICES = [
    {"id": "en-IN-PrabhatNeural", "name": "Prabhat (Indian English - Academic Male)", "lang": "en-IN", "gender": "Male"},
    {"id": "en-IN-NeerjaNeural", "name": "Neerja (Indian English - Clear Female)", "lang": "en-IN", "gender": "Female"},
    {"id": "hi-IN-MadhurNeural", "name": "Madhur (Hindi - Formal Male)", "lang": "hi-IN", "gender": "Male"},
    {"id": "hi-IN-SwaraNeural", "name": "Swara (Hindi - Expressive Female)", "lang": "hi-IN", "gender": "Female"},
]

DEFAULT_VOICE = "en-IN-PrabhatNeural"


def is_audio_supported() -> bool:
    """Return True if edge-tts is available."""
    return _HAS_EDGE_TTS


def get_available_voices() -> List[Dict[str, str]]:
    """Return available high-quality neural voices."""
    return list(INDIAN_VOICES)


async def _synthesize_async(text: str, voice: str) -> bytes:
    communicate = edge_tts.Communicate(text=text, voice=voice)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio":
            buf.write(chunk.get("data", b""))
    return buf.getvalue()


def synthesize_text_to_audio(text: str, voice: str = DEFAULT_VOICE) -> bytes:
    """Synchronous wrapper to synthesize text to MP3 audio bytes using edge-tts.

    Handles running inside Streamlit's tornado event loop smoothly.
    """
    if not _HAS_EDGE_TTS:
        raise ImportError("edge-tts is not installed. Run 'pip install edge-tts'.")
    if not text or not text.strip():
        return b""

    # Strip markdown symbols for clean, natural speech pronunciation
    clean_text = re.sub(r'[\*_`#\[\]]', '', text)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()

    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(_synthesize_async(clean_text, voice))).result(timeout=30)
    except Exception:
        return asyncio.run(_synthesize_async(clean_text, voice))


def generate_question_narration(
    q_data: Dict[str, Any],
    include_options: bool = True,
    voice: str = DEFAULT_VOICE,
) -> bytes:
    """Format a question and its options into speech."""
    stem = str(q_data.get("question", "")).strip()
    subj = str(q_data.get("subject", "")).strip()
    script = f"Question from {subj}. {stem}."
    if include_options:
        opt_a = str(q_data.get("option_a", "")).strip()
        opt_b = str(q_data.get("option_b", "")).strip()
        opt_c = str(q_data.get("option_c", "")).strip()
        opt_d = str(q_data.get("option_d", "")).strip()
        script += f" Option A: {opt_a}. Option B: {opt_b}. Option C: {opt_c}. Option D: {opt_d}."
    return synthesize_text_to_audio(script, voice=voice)


def generate_explanation_narration(
    q_data: Dict[str, Any],
    voice: str = DEFAULT_VOICE,
) -> bytes:
    """Synthesize explanation, distractor warnings, and concept tested."""
    corr = str(q_data.get("correct_option", "A")).upper()
    corr_txt = str(q_data.get(f"option_{corr.lower()}", ""))
    exp = str(q_data.get("explanation", "")).strip()
    dist = str(q_data.get("distractor_notes", "")).strip()
    concept = str(q_data.get("concept_tested", "")).strip()

    script = f"The correct answer is Option {corr}: {corr_txt}. "
    if exp:
        script += f"Explanation: {exp}. "
    if dist:
        script += f"Distractor trap analysis: {dist}. "
    if concept:
        script += f"Core concept tested: {concept}."

    return synthesize_text_to_audio(script, voice=voice)


def generate_dossier_podcast(
    title: str,
    content: str,
    voice: str = DEFAULT_VOICE,
) -> bytes:
    """Synthesize a complete daily current affairs brief into an audio podcast episode."""
    intro = f"Welcome to Question Lab Daily Briefing. Today's feature: {title}."
    body = f"{intro} {content}. End of briefing."
    return synthesize_text_to_audio(body, voice=voice)
