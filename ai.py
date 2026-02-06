import os
import base64
import json
import time
import random

from openai import OpenAI
from openai import AuthenticationError, RateLimitError, APIError, APITimeoutError

def _get_openai_key() -> str | None:
    # 1) Streamlit secrets (Cloud)
    try:
        import streamlit as st
        key = st.secrets.get("OPENAI_API_KEY", None)
        if key:
            return str(key).strip()
    except Exception:
        pass

    # 2) Env var fallback (locale)
    key = os.getenv("OPENAI_API_KEY")
    return key.strip() if key else None

def _client() -> OpenAI:
    key = _get_openai_key()
    if not key:
        raise RuntimeError("OPENAI_API_KEY mancante. Mettila in Streamlit Secrets o come variabile d’ambiente.")
    return OpenAI(api_key=key)

def _b64(img: bytes) -> str:
    return base64.b64encode(img).decode("utf-8")

def _retry(fn, max_tries=4):
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
            time.sleep(1.2 * attempt)

def _parse_json(text: str) -> dict:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end+1])
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
    txt = resp.choices[0].message.content
    return _parse_json(txt)

def estimate_meal_from_text(text: str) -> dict:
    client = _client()
    prompt = f"""
Stima calorie realistiche per questo pasto: {text}
Rispondi SOLO JSON:
{{"total_calories": number, "description": string, "notes": string}}
"""
    def _call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

    resp = _retry(_call)
    txt = resp.choices[0].message.content
    return _parse_json(txt)

def estimate_workout_from_text(text: str, weight_kg: float | None, height_cm: float | None) -> dict:
    client = _client()
    prompt = f"""
Stima calorie bruciate per questo allenamento: {text}
Dati persona: peso={weight_kg}, altezza={height_cm}

Rispondi SOLO JSON:
{{"calories_burned": number, "description": string, "notes": string}}
"""
    def _call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
    resp = _retry(_call)
    txt = resp.choices[0].message.content
    return _parse_json(txt)

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
        return "AuthenticationError: API key OpenAI mancante/errata/revocata. Controlla Streamlit Secrets e rigenera la key se serve."
    if isinstance(e, RateLimitError):
        return "RateLimitError: troppe richieste o quota/crediti esauriti. Riprova tra 1–2 minuti o verifica billing."
    if isinstance(e, APITimeoutError):
        return "Timeout OpenAI: riprova."
    if isinstance(e, APIError):
        return "Errore temporaneo OpenAI: riprova tra poco."
    return f"Errore OpenAI: {type(e).__name__}"