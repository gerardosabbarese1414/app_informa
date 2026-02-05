import os, base64, json
from datetime import datetime
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def _b64_data_url(file_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def analyze_food_photo(file_bytes: bytes, mime: str = "image/jpeg") -> dict:
    """
    Ritorna dict:
    {
      "items":[{"name":"...", "portion":"...", "calories":123}],
      "total_calories": 456,
      "notes":"..."
    }
    """
    data_url = _b64_data_url(file_bytes, mime)

    prompt = """
Analizza la foto del pasto.
Obiettivo: stimare calorie realistiche.

Rispondi SOLO in JSON valido con questa struttura:
{
  "items": [{"name": "...", "portion": "...", "calories": number}],
  "total_calories": number,
  "notes": "breve nota su incertezza/stima"
}

Se non riconosci bene, fai una stima prudente e scrivi in notes cosa manca.
"""

    resp = client.responses.create(
        model="gpt-4o-mini",
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_url": data_url},
            ],
        }],
    )

    text = resp.output_text.strip()

    # Prova parsing JSON robusto
    try:
        return json.loads(text)
    except Exception:
        # fallback: prova a estrarre blocco JSON
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end+1])
        # se fallisce proprio:
        return {"items": [], "total_calories": 0, "notes": "Parsing JSON fallito", "raw": text}

def generate_weekly_plan(summary_text: str) -> str:
    prompt = f"""
Sei un coach nutrizione + allenamento.
Crea un piano della prossima settimana basato sui dati RIASSUNTI qui sotto.

REQUISITI:
- Piano alimentare 7 giorni (colazione/pranzo/cena/snack) con alternative
- Stima calorie target + macro (proteine/carbo/grassi)
- Piano allenamento 7 giorni (anche riposo) con durata/intensità
- Sezione: "Cosa cambiare rispetto alla scorsa settimana" (bullet)
- Stile pratico, sostenibile

DATI:
{summary_text}
"""
    resp = client.responses.create(
        model="gpt-4o-mini",
        input=prompt
    )
    return resp.output_text