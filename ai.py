import os, base64, json, time, random
from openai import OpenAI
from openai import RateLimitError, APIError, APITimeoutError

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def _b64_data_url(file_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def _retry_openai(fn, max_tries=4):
    # backoff progressivo con jitter
    for attempt in range(1, max_tries + 1):
        try:
            return fn()
        except RateLimitError:
            if attempt == max_tries:
                raise
            sleep_s = (2 ** attempt) + random.random()
            time.sleep(sleep_s)
        except (APITimeoutError, APIError):
            if attempt == max_tries:
                raise
            time.sleep(1.5 * attempt)

def analyze_food_photo(file_bytes: bytes, mime: str = "image/jpeg") -> dict:
    data_url = _b64_data_url(file_bytes, mime)

    prompt = """
Analizza la foto del pasto e stima calorie realistiche.
Rispondi SOLO in JSON valido con:
{
  "items": [{"name": "...", "portion": "...", "calories": number}],
  "total_calories": number,
  "notes": "breve nota su incertezza/stima"
}
Se non sei sicuro, fai una stima prudente e spiega in notes.
"""

    def _call():
        return client.responses.create(
            model="gpt-4o-mini",
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url},
                ],
            }],
        )

    resp = _retry_openai(_call)
    text = (resp.output_text or "").strip()

    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end+1])
        return {"items": [], "total_calories": 0, "notes": "Parsing JSON fallito", "raw": text}

def generate_weekly_plan(summary_text: str) -> str:
    prompt = f"""
Sei un coach nutrizione + allenamento.
Crea un piano della prossima settimana basato su questi dati.

REQUISITI:
- Piano alimentare 7 giorni (colazione/pranzo/cena/snack) con alternative
- Calorie target + macro (proteine/carbo/grassi)
- Piano allenamento 7 giorni (anche riposo) con durata/intensità
- Sezione: "Cosa cambiare rispetto alla scorsa settimana"

DATI:
{summary_text}
"""

    def _call():
        return client.responses.create(
            model="gpt-4o-mini",
            input=prompt
        )

    resp = _retry_openai(_call)
    return resp.output_text