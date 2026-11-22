"""Thin wrapper around the Google Gemini API (google-genai SDK).

The API key is read from (in order): Streamlit secrets, the GEMINI_API_KEY
environment variable. It is NEVER hard-coded or written to disk.
"""
from __future__ import annotations

import json
import os
import re
import time

DEFAULT_MODEL = "gemini-3.5-flash"

_client = None
_client_key = None


def get_api_key() -> str | None:
    try:  # Streamlit Cloud secrets (only when running inside streamlit)
        import streamlit as st

        if st.session_state.get("user_api_key"):  # key pasted in the sidebar (this session only)
            return st.session_state["user_api_key"]
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY")


def get_model() -> str:
    try:
        import streamlit as st

        if "GEMINI_MODEL" in st.secrets:
            return st.secrets["GEMINI_MODEL"]
    except Exception:
        pass
    return os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)


def _client_for(key: str):
    global _client, _client_key
    if _client is None or _client_key != key:
        from google import genai
        from google.genai import types

        # 60 s per request (milliseconds): a hung connection raises and the retry loop in call() takes over.
        _client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=60_000))
        _client_key = key
    return _client


class LLMError(RuntimeError):
    pass


# Minimum gap between calls (seconds) so the free tier RPM limit is respected.
MIN_GAP = float(os.environ.get("LLM_MIN_GAP", "0"))
_last_call = 0.0


def call(
    system: str | None,
    user: str,
    temperature: float | None = None,
    json_mode: bool = False,
    api_key: str | None = None,
    model: str | None = None,
    retries: int = 4,
) -> str:
    """Send one prompt, return the raw text. Retries on rate-limit / 5xx."""
    global _last_call
    from google.genai import types

    key = api_key or get_api_key()
    if not key:
        raise LLMError("No GEMINI_API_KEY configured.")
    client = _client_for(key)
    cfg = {}
    if system:
        cfg["system_instruction"] = system
    if temperature is not None:
        cfg["temperature"] = temperature
    if json_mode:
        cfg["response_mime_type"] = "application/json"
    config = types.GenerateContentConfig(**cfg)

    delay = 5.0
    for attempt in range(retries + 1):
        wait = MIN_GAP - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            _last_call = time.time()
            resp = client.models.generate_content(
                model=model or get_model(), contents=user, config=config
            )
            return resp.text or ""
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            transient = any(s in msg for s in ("429", "RESOURCE_EXHAUSTED", "503", "500", "UNAVAILABLE", "overloaded"))
            if not transient or attempt == retries:
                raise LLMError(msg) from e
            m = re.search(r"retry in ([\d.]+)s", msg) or re.search(r"retryDelay['\"]?: ?['\"]?(\d+)", msg)
            time.sleep(float(m.group(1)) + 1 if m else delay)
            delay *= 2
    raise LLMError("unreachable")


def parse_json(text: str):
    """Parse JSON from model text; tolerates ```json fences and leading prose.
    Returns (obj, ok)."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t), True
    except Exception:
        pass
    m = re.search(r"[\{\[].*[\}\]]", t, re.S)
    if m:
        try:
            return json.loads(m.group(0)), True
        except Exception:
            pass
    return None, False
