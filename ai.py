import os, base64, json, time, random
from openai import OpenAI
from openai import AuthenticationError, RateLimitError, APIError, APITimeoutError


def _read_key() -> tuple[str | None, str]:
    try:
        import streamlit as st
        k = st.secrets.get("OPENAI_API_KEY", None)
        if k:
            return str(k).strip(), "secrets"
    except Exception:
        pass
    k = os.getenv("OPENAI_API_KEY")
    return (k.strip(), "env") if k else (None, "missing")


def openai_status() -> dict:
    k, src = _read_key()
    ok = bool(k) and k.startswith("sk-") and len(k) > 20
    return {"has_key": bool(k), "format_ok": ok, "source": src}


def _client() -> OpenAI:
    k, _ = _read_key()
    if not k:
        raise RuntimeError("OPENAI_API_KEY mancante.")
    if not (k.startswith("sk-") and len(k) > 20):
        raise RuntimeError("OPENAI_API_KEY presente ma formato non valido.")
    return OpenAI(api_key=k)


def explain_openai_error(e: Exception) -> str:
    if isinstance(e, AuthenticationError):
        return "AuthenticationError: key errata/revocata. Aggiorna Secrets e fai Reboot."
    if isinstance(e, RateLimitError):
        return "RateLimitError: troppe richieste o quota esaurita."
    if isinstance(e, APITimeoutError):
        return "Timeout OpenAI: riprova."
    if isinstance(e, APIError):
        return "Errore temporaneo OpenAI: riprova."
    if isinstance(e, RuntimeError):
        return str(e)
    return f"Errore OpenAI: {type(e).__name__}"


def _retry(fn, max_tries=4):
    for attempt in range(1, max_tries + 1):
        try:
            return fn()
        except RateLimitError:
            if attempt == max_tries:
                raise
            time.sleep((2**attempt) + random.random())
        except (APITimeoutError, APIError):
            if attempt == max_tries:
                raise
            time.sleep(1.3 * attempt)


def _b64(img: bytes) -> str:
    return base64.b64encode(img).decode("utf-8")


def _parse_json(txt: str) -> dict:
    txt = (txt or "").strip()
    try:
        return json.loads(txt)
    except Exception:
        s = txt.find("{"); e = txt.rfind("}")
        if s != -1 and e != -1 and e > s:
            return json.loads(txt[s:e+1])
        return {"error": "json_parse_failed", "raw": txt}


def analyze_food_photo(img_bytes: bytes, mime: str, meal_time: str, note: str) -> dict:
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


def estimate_workout_from_text(text: str, weight_kg: float | None, height_cm: float | None) -> dict:
    client = _client()
    prompt = f"""
Stima calorie bruciate per questo allenamento:
{text}

Dati persona:
- peso_kg: {weight_kg}
- altezza_cm: {height_cm}

Rispondi SOLO JSON:
{{"calories_burned": number, "description": string, "notes": string}}
"""
    def _call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
    resp = _retry(_call)
    return _parse_json(resp.choices[0].message.content)


def generate_weekly_plan(summary_text: str) -> str:
    """Versione testo (rimane)"""
    client = _client()
    def _call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": summary_text}]
        )
    resp = _retry(_call)
    return (resp.choices[0].message.content or "").strip()


def generate_weekly_plan_json(summary_text: str) -> dict:
    """
    Versione STRUTTURATA: restituisce un JSON con meals/workouts programmati.
    """
    client = _client()
    prompt = f"""
Sei un coach nutrizionale/fitness.
Genera un piano settimanale STRUTTURATO basandoti su questi dati:

{summary_text}

Devi restituire SOLO JSON con questo schema:
{{
  "week_start": "YYYY-MM-DD",
  "meals": [
    {{"date":"YYYY-MM-DD","time":"HH:MM","title":"Colazione|Pranzo|Cena|Spuntino","items":"testo breve","expected_calories": number, "notes":"string"}}
  ],
  "workouts": [
    {{"date":"YYYY-MM-DD","time":"HH:MM","title":"string","duration_min": number, "expected_calories_burned": number, "notes":"string"}}
  ]
}}

Regole:
- usa solo date della settimana che inizia in week_start
- inserisci orari realistici
- expected_calories ed expected_calories_burned devono essere numeri
"""

    def _call():
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

    resp = _retry(_call)
    return _parse_json(resp.choices[0].message.content)