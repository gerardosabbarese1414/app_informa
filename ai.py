from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_weekly_plan(summary):
    response = client.responses.create(
        model="gpt-4o-mini",
        input=f"""
Sei un coach fitness.
Dati settimana precedente:
{summary}

Genera:
- piano alimentare settimanale
- piano allenamento settimanale
- spiegazione
"""
    )
    return response.output_text