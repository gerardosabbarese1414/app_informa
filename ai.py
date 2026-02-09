import os
import json
import base64
import time
from typing import Any

import streamlit as st
from openai import OpenAI

from utils import heuristic_meal_kcal, heuristic_workout_kcal


def _get_api_key() -> str | None:
    # Streamlit Cloud: st.secrets; locale: env var
    if "OPENAI_API_KEY" in st.secrets:
        return st.secrets["OPENAI_API_KEY"]
    return os.getenv("OPENAI_API_KEY")


def _client() -> OpenAI:
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY mancante. Impostala in Streamlit Secrets.")
    return OpenAI(api_key=api_key)


def explain_openai_error(e: Exception) -> str:
    msg = str(e)
    if "Authentication" in msg or "401" in msg:
        return "Errore OpenAI: API key non valida o mancante (AuthenticationError). Controlla OPENAI_API_KEY nei Secrets."
    if "RateLimit" in msg or "429" in msg:
        return "OpenAI in Rate Limit (429). Riprova tra poco oppure riduci chiamate."
    return f"Errore OpenAI: {msg}"


def _retry(fn, tries=3, base_sleep=1.0):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last = e
            time.sleep(base_sleep * (2 ** i))
    raise last


def _safe_json(text: str) -> dict[str, Any]:
    # prova a estrarre JSON anche se il modello aggiunge testo
    text = (text or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        # heuristica: cerca prima { ... }
        s = text.find("{")
        t = text.rfind("}")
        if s != -1 and t != -1 and t > s:
            try:
                return json.loads(text[s:t+1])
            except Exception:
                return {}
    return {}


# --------- MEAL TEXT ---------
def estimate_meal_from_text(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {"total_calories": 0, "description": "", "notes": "Nessun testo."}

    def _call():
        client = _client()
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "user",
                    "content": (
                        "Stima le calorie del pasto descritto. "
                        "Rispondi SOLO JSON con chiavi: total_calories (numero), description (stringa), notes (stringa breve). "
                        f"Pasto: {text}"
                    ),
                }
            ],
        )
        out_text = getattr(resp, "output_text", None) or ""
        data = _safe_json(out_text)
        if "total_calories" not in data:
            data = {"total_calories": heuristic_meal_kcal(text), "description": text, "notes": "Fallback euristico."}
        return data

    try:
        return _retry(_call)
    except Exception:
        # fallback hard
        return {"total_calories": heuristic_meal_kcal(text), "description": text, "notes": "Fallback: OpenAI non disponibile."}


# --------- WORKOUT TEXT ---------
def estimate_workout_from_text(text: str, weight_kg: float | None, height_cm: float | None) -> dict:
    text = (text or "").strip()
    if not text:
        return {"calories_burned": 0, "notes": "Nessun testo."}

    def _call():
        client = _client()
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "user",
                    "content": (
                        "Stima le calorie bruciate per l'allenamento. "
                        "Rispondi SOLO JSON con chiavi: calories_burned (numero), notes (stringa breve). "
                        f"Contesto: peso_kg={weight_kg}, altezza_cm={height_cm}. "
                        f"Allenamento: {text}"
                    ),
                }
            ],
        )
        out_text = getattr(resp, "output_text", None) or ""
        data = _safe_json(out_text)
        if "calories_burned" not in data:
            # fallback: prova a dedurre durata dal testo? (semplice)
            data = {"calories_burned": 0, "notes": "Fallback."}
        return data

    try:
        return _retry(_call)
    except Exception:
        # fallback euristico: prova a stimare da keyword + durata se presente
        dur = 45
        for token in text.split():
            if token.isdigit():
                dur = int(token)
                break
        return {"calories_burned": heuristic_workout_kcal(text, dur), "notes": "Fallback: OpenAI non disponibile."}


# --------- FOOD PHOTO (VISION) ---------
def analyze_food_photo(image_bytes: bytes, mime: str, time_str: str, note: str) -> dict:
    """
    Vision: analizza la foto + contesto (orario + nota).
    """
    if not image_bytes:
        return {"total_calories": 0, "description": "", "notes": "Nessuna immagine."}

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime};base64,{b64}"

    def _call():
        client = _client()
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Analizza la foto del pasto e stima le calorie. "
                                "Rispondi SOLO JSON con chiavi: total_calories (numero), description (stringa), notes (stringa breve). "
                                f"Orario: {time_str}. Nota: {note or ''}."
                            ),
                        },
                        {"type": "input_image", "image_url": data_url},
                    ],
                }
            ],
        )
        out_text = getattr(resp, "output_text", None) or ""
        data = _safe_json(out_text)
        if "total_calories" not in data:
            data = {"total_calories": 600, "description": "Pasto (foto)", "notes": "Fallback (parse)."}
        return data

    try:
        return _retry(_call)
    except Exception:
        return {"total_calories": 600, "description": "Pasto (foto)", "notes": "Fallback: OpenAI non disponibile."}


# --------- WEEKLY PLAN (TEXT) ---------
def generate_weekly_plan(prompt: str) -> str:
    prompt = (prompt or "").strip()
    if not prompt:
        return "Prompt vuoto."

    def _call():
        client = _client()
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=[{"role": "user", "content": prompt}],
        )
        return (getattr(resp, "output_text", None) or "").strip()

    try:
        return _retry(_call)
    except Exception as e:
        return f"Non riesco a generare il piano ora (OpenAI). Dettagli: {explain_openai_error(e)}"