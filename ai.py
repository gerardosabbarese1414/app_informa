import os
import json
import base64
import time
from typing import Any, Callable

import streamlit as st
from openai import OpenAI

from utils import heuristic_meal_kcal, heuristic_workout_kcal


# ----------------------------
# OpenAI client helpers
# ----------------------------
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


def _retry(fn: Callable[[], Any], tries: int = 3, base_sleep: float = 1.0):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last = e
            time.sleep(base_sleep * (2 ** i))
    raise last


def _json_schema_meal() -> dict:
    return {
        "type": "json_schema",
        "name": "meal_estimate",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "total_calories": {"type": "number"},
                "description": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["total_calories", "description", "notes"],
        },
    }


def _json_schema_workout() -> dict:
    return {
        "type": "json_schema",
        "name": "workout_estimate",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "calories_burned": {"type": "number"},
                "notes": {"type": "string"},
            },
            "required": ["calories_burned", "notes"],
        },
    }


# ----------------------------
# MEAL (free text)
# ----------------------------
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
                        "Stima le calorie del pasto descritto.\n"
                        "Se mancano quantità/dettagli, fai assunzioni ragionevoli (porzioni standard) e scrivile in notes.\n"
                        "Mantieni description breve e concreta.\n"
                        f"Pasto: {text}"
                    ),
                }
            ],
            # ✅ Structured Outputs: JSON sempre valido e conforme allo schema
            text={"format": _json_schema_meal()},
        )
        out_text = getattr(resp, "output_text", None) or ""
        data = json.loads(out_text)

        # normalizza
        tc = float(data.get("total_calories", 0) or 0)
        data["total_calories"] = max(0.0, tc)
        data["description"] = str(data.get("description", "") or "").strip()
        data["notes"] = str(data.get("notes", "") or "").strip()
        return data

    try:
        return _retry(_call)
    except Exception:
        return {
            "total_calories": heuristic_meal_kcal(text),
            "description": text,
            "notes": "Fallback: OpenAI non disponibile.",
        }


# ----------------------------
# WORKOUT (free text)
# ----------------------------
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
                        "Stima le calorie bruciate per l'allenamento descritto.\n"
                        "Se mancano durata/intensità, fai assunzioni ragionevoli e scrivile in notes.\n"
                        "Usa il contesto antropometrico come supporto, se utile.\n"
                        f"Contesto: peso_kg={weight_kg}, altezza_cm={height_cm}.\n"
                        f"Allenamento: {text}"
                    ),
                }
            ],
            # ✅ Structured Outputs
            text={"format": _json_schema_workout()},
        )
        out_text = getattr(resp, "output_text", None) or ""
        data = json.loads(out_text)

        cb = float(data.get("calories_burned", 0) or 0)
        data["calories_burned"] = max(0.0, cb)
        data["notes"] = str(data.get("notes", "") or "").strip()
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
        return {
            "calories_burned": heuristic_workout_kcal(text, dur),
            "notes": "Fallback: OpenAI non disponibile.",
        }


# ----------------------------
# FOOD PHOTO (vision)
# ----------------------------
def analyze_food_photo(image_bytes: bytes, mime: str, time_str: str, note: str) -> dict:
    """
    Vision: analizza la foto + contesto (orario + nota).
    Ritorna SEMPRE JSON conforme allo schema meal_estimate.
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
                                "Analizza la foto del pasto e stima le calorie.\n"
                                "Se non riconosci con certezza, fai una stima prudente e scrivi le assunzioni in notes.\n"
                                f"Orario: {time_str}. Nota: {note or ''}."
                            ),
                        },
                        {"type": "input_image", "image_url": data_url},
                    ],
                }
            ],
            # ✅ Structured Outputs
            text={"format": _json_schema_meal()},
        )
        out_text = getattr(resp, "output_text", None) or ""
        data = json.loads(out_text)

        tc = float(data.get("total_calories", 0) or 0)
        data["total_calories"] = max(0.0, tc)
        data["description"] = str(data.get("description", "") or "").strip()
        data["notes"] = str(data.get("notes", "") or "").strip()
        return data

    try:
        return _retry(_call)
    except Exception:
        return {"total_calories": 600, "description": "Pasto (foto)", "notes": "Fallback: OpenAI non disponibile."}