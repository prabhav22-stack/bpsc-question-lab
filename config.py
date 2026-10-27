"""Configuration and secret management for BPSC Question Lab.

Loads settings from Streamlit secrets (for cloud deployment or local .streamlit/secrets.toml)
or environment variables (.env file for local development).
Never logs, prints, or exposes raw API keys.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
except ImportError:
    pass

try:
    import streamlit as st

    _HAS_STREAMLIT = True
except ImportError:
    _HAS_STREAMLIT = False


def _get_setting(key: str, default: str = "") -> str:
    """Retrieve setting from Streamlit secrets or OS environment."""
    val = ""
    if _HAS_STREAMLIT:
        try:
            if key in st.secrets:
                val = str(st.secrets[key]).strip()
        except Exception:
            pass
    if not val:
        val = os.getenv(key, default).strip()
    return val


def get_gemini_api_key() -> str:
    """Return the configured Gemini API key, or empty string."""
    return _get_setting("GEMINI_API_KEY", "")


def get_gemini_model() -> str:
    """Return configured Gemini model name."""
    return _get_setting("GEMINI_MODEL", "gemini-3.5-flash-lite")


def get_gemini_analysis_model() -> str:
    """Return configured Gemini model name for in-depth exam analysis and diagnostics.

    Defaults to standard Flash medium ('gemini-3.5-flash') for deeper pedagogical reasoning.
    """
    return _get_setting("GEMINI_ANALYSIS_MODEL", "gemini-3.5-flash")


def get_supabase_url() -> str:
    """Return configured Supabase project URL."""
    return _get_setting("SUPABASE_URL", "")


def get_supabase_anon_key() -> str:
    """Return configured Supabase anon key."""
    return _get_setting("SUPABASE_ANON_KEY", "")


def is_gemini_configured() -> bool:
    """Check if a Gemini API key is configured."""
    key = get_gemini_api_key()
    return bool(key and key != "YOUR_GEMINI_API_KEY")


def is_supabase_configured() -> bool:
    """Check if Supabase cloud credentials are configured."""
    url = get_supabase_url()
    key = get_supabase_anon_key()
    return bool(url and key and url != "https://your-project-id.supabase.co" and key != "your-supabase-anon-public-key")


def mask_secret(secret: str) -> str:
    """Return a masked representation of a secret for safe display."""
    if not secret:
        return "Not configured"
    if len(secret) <= 8:
        return "••••••••"
    return f"{secret[:4]}••••••••{secret[-4:]}"
