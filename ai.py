import os
import time
import json
import base64
from openai import OpenAI


def _api_key() -> str | None:
    return os.getenv("OPENAI_API_KEY")


def openai_ready() -> bool:
    k = _api_key()
    return bool(k and k.startswith("sk-"))


def _client() -> OpenAI:
    key = _api_key()
    if not key:
        raise RuntimeError("OPENAI_API_KEY mancante (Secrets/env).")
    return OpenAI(api_key=key)


def explain_openai_error(e: Exception) -> str:
    s = str(e)
    if "AuthenticationError" in s or "401" in s:
        return "Errore autenticazione OpenAI: controlla OPENAI_API_KEY nei Secrets."
    if "RateLimitError" in s or "429" in s:
        return "Rate limit OpenAI: troppe richieste. Riprova tra poco."
    return f"Errore OpenAI: {s}"


def _retry(fn, tries=4, sleep=1.5):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last = e
            time.sleep(sleep * (i + 1))
    raise last


def _json_only(prompt: str) -> dict:
    client = _client()

    def _call():
        resp = client.responses.create(model="gpt-4o-mini", input=prompt)
        out = (getattr(resp, "output_text", "") or "").strip()
        return json.loads(out)

    return _retry(_call)


def estimate_meal_from_text(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {"total_calories": 0, "notes": "Vuoto"}

    prompt = f"""
Stima le calorie per questo pasto:
"{text}"

Rispondi SOLO JSON:
{{"total_calories": <numero>, "notes": "<breve>"}} 
"""
    return _json_only(prompt)


def estimate_workout_from_text(text: str, weight_kg: float | None = None, height_cm: float | None = None) -> dict:
    text = (text or "").strip()
    if not text:
        return {"calories_burned": 0, "notes": "Vuoto"}

    prompt = f"""
Stima le calorie bruciate per questo allenamento:
"{text}"

Dati (se presenti):
- weight_kg: {weight_kg}
- height_cm: {height_cm}

Rispondi SOLO JSON:
{{"calories_burned": <numero>, "notes": "<breve>"}}
"""
    return _json_only(prompt)


def analyze_food_photo(image_bytes: bytes, mime_type: str, time_str: str, note: str) -> dict:
    client = _client()
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"

    prompt = f"""
Analizza la foto di un pasto.
Orario: {time_str}
Nota: {note}

Rispondi SOLO JSON:
{{"description":"...", "total_calories": <numero>, "confidence": <0..1>}}
"""

    def _call():
        resp = client.responses.create(
            model="gpt-4o-mini",
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url},
                ]
            }]
        )
        out = (getattr(resp, "output_text", "") or "").strip()
        return json.loads(out)

    return _retry(_call)


def generate_weekly_plan(prompt: str) -> str:
    client = _client()

    def _call():
        resp = client.responses.create(model="gpt-4o-mini", input=prompt)
        return getattr(resp, "output_text", None) or str(resp)

    return _retry(_call)