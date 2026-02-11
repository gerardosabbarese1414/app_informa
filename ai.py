# ai.py
import os
import json
import time
import base64
from typing import Any, Callable, Optional

import streamlit as st
from openai import OpenAI

from utils import heuristic_meal_kcal, heuristic_workout_kcal


def _get_api_key() -> Optional[str]:
    try:
        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass
    return os.getenv("OPENAI_API_KEY")


def _client() -> OpenAI:
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY mancante (st.secrets o env var).")
    return OpenAI(api_key=api_key)


def explain_openai_error(e: Exception) -> str:
    msg = str(e)
    if "401" in msg or "Authentication" in msg:
        return "API key non valida/mancante (401)."
    if "429" in msg or "RateLimit" in msg or "rate limit" in msg.lower():
        return "Rate limit/quota (429)."
    if "403" in msg:
        return "Accesso negato (403)."
    return msg


def _retry(fn: Callable[[], Any], tries: int = 3, base_sleep: float = 0.8):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last = e
            time.sleep(base_sleep * (2 ** i))
    raise last


def _err_to_notes(e: Exception) -> str:
    return f"Fallback: OpenAI non disponibile. Dettagli: {explain_openai_error(e)}"


def _meal_schema() -> dict:
    return {
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


def _workout_schema() -> dict:
    return {
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


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        if v != v:
            return default
        return v
    except Exception:
        return default


def estimate_meal_from_text(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {"total_calories": 0.0, "description": "", "notes": "Nessun testo."}

    def _call():
        client = _client()

        # Chat Completions + Structured Outputs (json_schema)
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Stima le calorie del cibo/bevanda descritti.\n"
                        "Se mancano quantità/dettagli, fai assunzioni ragionevoli (porzioni standard) "
                        "e scrivile in notes.\n"
                        "Se è una bevanda (es. caffè/cappuccino), considera latte/zucchero se citati; "
                        "se non citati, assumi non zuccherato e porzioni standard.\n"
                        "Restituisci description breve.\n\n"
                        f"Descrizione: {text}"
                    ),
                }
            ],
            response_format={"type": "json_schema", "json_schema": _meal_schema()},
        )

        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)

        tc = max(0.0, _safe_float(data.get("total_calories", 0), 0.0))
        desc = str(data.get("description", "") or "").strip() or text
        notes = str(data.get("notes", "") or "").strip()
        return {"total_calories": tc, "description": desc, "notes": notes}

    try:
        return _retry(_call)
    except Exception as e:
        return {
            "total_calories": float(heuristic_meal_kcal(text)),
            "description": text,
            "notes": _err_to_notes(e),
        }


def estimate_workout_from_text(text: str, weight_kg: Optional[float], height_cm: Optional[float]) -> dict:
    text = (text or "").strip()
    if not text:
        return {"calories_burned": 0.0, "notes": "Nessun testo."}

    def _call():
        client = _client()
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Stima le calorie bruciate dall'allenamento descritto.\n"
                        "Se mancano durata/intensità, fai assunzioni ragionevoli e scrivile in notes.\n"
                        f"Contesto: peso_kg={weight_kg}, altezza_cm={height_cm}\n"
                        f"Allenamento: {text}"
                    ),
                }
            ],
            response_format={"type": "json_schema", "json_schema": _workout_schema()},
        )

        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)

        cb = max(0.0, _safe_float(data.get("calories_burned", 0), 0.0))
        notes = str(data.get("notes", "") or "").strip()
        return {"calories_burned": cb, "notes": notes}

    try:
        return _retry(_call)
    except Exception as e:
        dur = 45
        for tok in text.replace(",", " ").split():
            if tok.isdigit():
                dur = int(tok)
                break
        return {
            "calories_burned": float(heuristic_workout_kcal(text, dur)),
            "notes": _err_to_notes(e),
        }


def analyze_food_photo(image_bytes: bytes, mime: str, time_str: str, note: str) -> dict:
    if not image_bytes:
        return {"total_calories": 0.0, "description": "", "notes": "Nessuna immagine."}

    mime = (mime or "image/jpeg").strip()
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime};base64,{b64}"

    def _call():
        client = _client()
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Analizza la foto del cibo/bevanda e stima le calorie.\n"
                                "Se non sei sicuro, fai una stima prudente e scrivi le assunzioni in notes.\n"
                                f"Orario: {time_str}\n"
                                f"Nota: {note or ''}"
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            response_format={"type": "json_schema", "json_schema": _meal_schema()},
        )

        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)

        tc = max(0.0, _safe_float(data.get("total_calories", 0), 0.0))
        desc = str(data.get("description", "") or "").strip() or "Pasto (foto)"
        notes = str(data.get("notes", "") or "").strip()
        return {"total_calories": tc, "description": desc, "notes": notes}

    try:
        return _retry(_call)
    except Exception as e:
        return {"total_calories": 0.0, "description": "Pasto (foto)", "notes": _err_to_notes(e)}


def generate_weekly_plan(prompt: str) -> str:
    prompt = (prompt or "").strip()
    if not prompt:
        return "Prompt vuoto."

    def _call():
        client = _client()
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return (resp.choices[0].message.content or "").strip()

    try:
        return _retry(_call)
    except Exception as e:
        return f"Non riesco a generare il piano ora. Dettagli: {explain_openai_error(e)}"