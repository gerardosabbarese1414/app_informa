# ai.py
import os
import json
import time
import base64
from typing import Any, Callable, Optional

import streamlit as st
from openai import OpenAI

from utils import heuristic_meal_kcal, heuristic_workout_kcal


# ----------------------------
# Client + retry
# ----------------------------
def _get_api_key() -> Optional[str]:
    # Streamlit Cloud: st.secrets; locale: env var
    try:
        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass
    return os.getenv("OPENAI_API_KEY")


def _client() -> OpenAI:
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY mancante. Impostala in Streamlit Secrets o env var.")
    return OpenAI(api_key=api_key)


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
    msg = str(e)
    if "401" in msg or "Authentication" in msg:
        return "Fallback: OpenAI key non valida/mancante (401)."
    if "429" in msg or "Rate limit" in msg or "RateLimit" in msg:
        return "Fallback: OpenAI rate limit/quota (429)."
    return f"Fallback: Errore OpenAI: {msg}"


# ----------------------------
# JSON Schemas (Structured Outputs)
# ----------------------------
def _meal_schema() -> dict:
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


def _workout_schema() -> dict:
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


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        if v != v:  # NaN
            return default
        return v
    except Exception:
        return default


# ----------------------------
# MEAL from free text
# ----------------------------
def estimate_meal_from_text(text: str) -> dict:
    """
    Stima kcal da descrizione libera (testo).
    Ritorna SEMPRE dict: {total_calories, description, notes}
    """
    text = (text or "").strip()
    if not text:
        return {"total_calories": 0.0, "description": "", "notes": "Nessun testo."}

    def _call():
        client = _client()
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "user",
                    "content": (
                        "Stima le calorie del cibo/bevanda descritti.\n"
                        "Se mancano quantità o dettagli, fai assunzioni ragionevoli (porzioni standard) "
                        "e scrivile in notes.\n"
                        "Se è una bevanda (es. caffè/cappuccino), stima in base a latte/zucchero se citati; "
                        "se non citati, assumi non zuccherato e porzioni standard.\n"
                        "Restituisci description breve e concreta.\n\n"
                        f"Descrizione: {text}"
                    ),
                }
            ],
            text={"format": _meal_schema()},
        )

        out = getattr(resp, "output_text", None) or ""
        data = json.loads(out)

        tc = max(0.0, _safe_float(data.get("total_calories", 0), 0.0))
        desc = str(data.get("description", "") or "").strip()
        notes = str(data.get("notes", "") or "").strip()

        # normalizzazione minima
        if not desc:
            desc = text

        return {"total_calories": tc, "description": desc, "notes": notes}

    try:
        return _retry(_call)
    except Exception as e:
        # se qui ti torna 500 per "caffè", NON è più colpa del parsing:
        # è perché OpenAI non ha risposto e stai andando in euristica.
        return {
            "total_calories": float(heuristic_meal_kcal(text)),
            "description": text,
            "notes": _err_to_notes(e),
        }


# ----------------------------
# WORKOUT from free text
# ----------------------------
def estimate_workout_from_text(text: str, weight_kg: Optional[float], height_cm: Optional[float]) -> dict:
    """
    Stima kcal bruciate da descrizione libera.
    Ritorna SEMPRE dict: {calories_burned, notes}
    """
    text = (text or "").strip()
    if not text:
        return {"calories_burned": 0.0, "notes": "Nessun testo."}

    def _call():
        client = _client()
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "user",
                    "content": (
                        "Stima le calorie bruciate dall'allenamento descritto.\n"
                        "Se mancano durata/intensità, fai assunzioni ragionevoli e scrivile in notes.\n"
                        "Usa peso/altezza solo come supporto, se utile.\n\n"
                        f"Contesto: peso_kg={weight_kg}, altezza_cm={height_cm}\n"
                        f"Allenamento: {text}"
                    ),
                }
            ],
            text={"format": _workout_schema()},
        )

        out = getattr(resp, "output_text", None) or ""
        data = json.loads(out)

        cb = max(0.0, _safe_float(data.get("calories_burned", 0), 0.0))
        notes = str(data.get("notes", "") or "").strip()
        return {"calories_burned": cb, "notes": notes}

    try:
        return _retry(_call)
    except Exception as e:
        # fallback euristico
        # prova a recuperare una durata in minuti se presente, altrimenti default 45
        dur = 45
        for tok in text.replace("'", " ").replace(",", " ").split():
            if tok.isdigit():
                dur = int(tok)
                break
        return {
            "calories_burned": float(heuristic_workout_kcal(text, dur)),
            "notes": _err_to_notes(e),
        }


# ----------------------------
# FOOD PHOTO (vision)
# ----------------------------
def analyze_food_photo(image_bytes: bytes, mime: str, time_str: str, note: str) -> dict:
    """
    Analizza foto pasto con vision e stima kcal.
    Ritorna SEMPRE dict: {total_calories, description, notes}
    """
    if not image_bytes:
        return {"total_calories": 0.0, "description": "", "notes": "Nessuna immagine."}

    mime = (mime or "image/jpeg").strip()
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
                                "Analizza la foto del cibo/bevanda e stima le calorie.\n"
                                "Se non sei sicuro, fai una stima prudente e scrivi le assunzioni in notes.\n"
                                "Restituisci description breve.\n\n"
                                f"Orario: {time_str}\n"
                                f"Nota: {note or ''}"
                            ),
                        },
                        {"type": "input_image", "image_url": data_url},
                    ],
                }
            ],
            text={"format": _meal_schema()},
        )

        out = getattr(resp, "output_text", None) or ""
        data = json.loads(out)

        tc = max(0.0, _safe_float(data.get("total_calories", 0), 0.0))
        desc = str(data.get("description", "") or "").strip()
        notes = str(data.get("notes", "") or "").strip()

        if not desc:
            desc = "Pasto (foto)"

        return {"total_calories": tc, "description": desc, "notes": notes}

    try:
        return _retry(_call)
    except Exception as e:
        return {
            "total_calories": 0.0,
            "description": "Pasto (foto)",
            "notes": _err_to_notes(e),
        }