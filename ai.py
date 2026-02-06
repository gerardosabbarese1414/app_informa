import os
import base64
import json
import time
import random

from openai import OpenAI
from openai import AuthenticationError, RateLimitError, APIError, APITimeoutError


def _read_secret_key() -> tuple[str | None, str]:
    """
    Returns: (key, source) where source is 'secrets', 'env', or 'missing'
    """
    # 1) Streamlit secrets (Cloud)
    try:
        import streamlit as st
        k = st.secrets.get("OPENAI_API_KEY", None)
        if k is not None:
            k = str(k).strip()
            if k:
                return k, "secrets"
    except Exception:
        pass

    # 2) Environment (local fallback)
    k = os.getenv("OPENAI_API_KEY")
    if k:
        k = k.strip()
        if k:
            return k, "env"

    return None, "missing"


def openai_status() -> dict:
    """
    Safe status info for UI/debug (does not reveal key).
    """
    key, source = _read_secret_key()
    # Very basic sanity check: correct prefix and non-trivial length
    format_ok = bool(key) and key.startswith("sk-") and len(key) > 20
    return {"has_key": bool(key), "source": source, "format_ok": format_ok}


def _get_openai_key_or_raise() -> str:
    key, _ = _read_secret_key()
    if not key:
        raise RuntimeError("OPENAI_API_KEY mancante (Streamlit Secrets o env).")
    if not (key.startswith("sk-") and len(key) > 20):
        raise RuntimeError("OPENAI_API_KEY presente ma con formato non valido.")
    return key


def _client() -> OpenAI:
    return OpenAI(api_key=_get_openai_key_or_raise())


def _b64(img: bytes) -> str:
    return base64.b64encode(img).decode("utf-8")


def _retry(fn, max_tries: int = 4):
    for attempt in range(1, max_tries + 1):
        try:
            return fn()
        except RateLimitError:
            if attempt == max_tries:
                raise
            time.sleep((2 ** attempt) + random.random())
        except (APITimeoutError, APIError):
            if attempt == max_tries:
                raise
            time.sleep(1.5 * attempt)


def _parse_json(text: str) -> dict:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end + 1])
        return {"error": "json_parse_failed", "raw": text}


def analyze_food_photo(img_bytes: bytes, mime: str, note: str, meal_time: str) -> dict:
    client = _client()

    prompt = f"""
Analizza il pasto in foto e stima calorie realistiche.
Orario: {meal_time}
Nota utente: {note}

Rispondi SOLO JSON:
{{"total_calories": number, "description": string, "notes": string}}
"""

    data_url = f"data:{mime};base64,{_b64(img_bytes)}"

    def _call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ]
            }]
        )

    resp = _retry(_call)
    return _parse_json(resp.choices[0].message.content)


def estimate_meal_from_text(text: str) -> dict:
    client = _client()

    prompt = f"""
Stima calorie realistiche per questo pasto:
{text}

Rispondi SOLO JSON:
{{"total_calories": number, "description": string, "notes": string}}
"""

    def _call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

    resp = _retry(_call)
    return _parse_json(resp.choices[0].message.content)


# Alias per compatibilità col tuo pages.py
def estimate_from_text(text: str) -> dict:
    return estimate_meal_from_text(text)


def generate_weekly_plan(summary: str) -> str:
    client = _client()

    def _call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": summary}]
        )

    resp = _retry(_call)
    return (resp.choices[0].message.content or "").strip()


def explain_openai_error(e: Exception) -> str:
    if isinstance(e, AuthenticationError):
        return ("AuthenticationError: API key OpenAI errata/revocata o non abilitata. "
                "Rigenera la key e aggiorna i Secrets, poi Reboot app.")
    if isinstance(e, RateLimitError):
        return "RateLimitError: troppe richieste o quota/crediti esauriti."
    if isinstance(e, APITimeoutError):
        return "Timeout OpenAI: riprova."
    if isinstance(e, APIError):
        return "Errore temporaneo OpenAI: riprova tra poco."
    if isinstance(e, RuntimeError):
        return str(e)
    return f"Errore OpenAI: {type(e).__name__}"