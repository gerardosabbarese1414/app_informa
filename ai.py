import os
import base64
import json
import time
import random

from openai import OpenAI
from openai import AuthenticationError, RateLimitError, APIError, APITimeoutError


# ========= API KEY =========
def _get_openai_key() -> str | None:
    try:
        import streamlit as st
        key = st.secrets.get("OPENAI_API_KEY", None)
        if key:
            return str(key).strip()
    except Exception:
        pass

    key = os.getenv("OPENAI_API_KEY")
    return key.strip() if key else None


def _client() -> OpenAI:
    key = _get_openai_key()
    if not key:
        raise RuntimeError("OPENAI_API_KEY mancante. Inseriscila in Streamlit Secrets.")
    return OpenAI(api_key=key)


# ========= UTILS =========
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


# ========= FOTO PASTO =========
def analyze_food_photo(
    img_bytes: bytes,
    mime: str,
    note: str,
    meal_time: str
) -> dict:
    client = _client()

    prompt = f"""
Analizza il pasto in foto e stima calorie realistiche.
Orario: {meal_time}
Nota utente: {note}

Rispondi SOLO in JSON:
{{
  "total_calories": number,
  "description": string,
  "notes": string
}}
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


# ========= PASTO DA TESTO =========
def estimate_meal_from_text(text: str) -> dict:
    client = _client()

    prompt = f"""
Stima calorie realistiche per questo pasto:
{text}

Rispondi SOLO in JSON:
{{
  "total_calories": number,
  "description": string,
  "notes": string
}}
"""

    def _call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

    resp = _retry(_call)
    return _parse_json(resp.choices[0].message.content)


# ========= ALIAS COMPATIBILITÀ =========
def estimate_from_text(text: str) -> dict:
    return estimate_meal_from_text(text)


# ========= ALLENAMENTO =========
def estimate_workout_from_text(
    text: str,
    weight_kg: float | None,
    height_cm: float | None
) -> dict:
    client = _client()

    prompt = f"""
Stima calorie bruciate per questo allenamento:
{text}

Dati persona:
- peso: {weight_kg}
- altezza: {height_cm}

Rispondi SOLO in JSON:
{{
  "calories_burned": number,
  "description": string,
  "notes": string
}}
"""

    def _call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

    resp = _retry(_call)
    return _parse_json(resp.choices[0].message.content)


# ========= PIANO SETTIMANALE =========
def generate_weekly_plan(summary: str) -> str:
    client = _client()

    def _call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": summary}]
        )

    resp = _retry(_call)
    return (resp.choices[0].message.content or "").strip()


# ========= ERRORI LEGGIBILI =========
def explain_openai_error(e: Exception) -> str:
    if isinstance(e, AuthenticationError):
        return "Errore OpenAI: API key mancante/errata. Controlla Streamlit Secrets."
    if isinstance(e, RateLimitError):
        return "Rate limit OpenAI: troppe richieste o quota esaurita."
    if isinstance(e, APITimeoutError):
        return "Timeout OpenAI. Riprova."
    if isinstance(e, APIError):
        return "Errore temporaneo OpenAI. Riprova."
    return f"Errore OpenAI: {type(e).__name__}"