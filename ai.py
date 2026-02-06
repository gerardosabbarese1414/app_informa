import base64, json
import streamlit as st
from openai import OpenAI

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def _b64(img):
    return base64.b64encode(img).decode()

def analyze_food_photo(img_bytes, mime, note):
    prompt = f"""
Analizza il pasto in foto.
Nota utente: {note}
Rispondi SOLO JSON:
{{"total_calories": number, "description": string}}
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{_b64(img_bytes)}"}}
            ]
        }]
    )
    txt = res.choices[0].message.content
    return json.loads(txt[txt.find("{"):txt.rfind("}")+1])

def estimate_from_text(text):
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":f"Stima calorie per: {text}. Rispondi solo JSON {{total_calories}}"}]
    )
    txt = res.choices[0].message.content
    return json.loads(txt[txt.find("{"):txt.rfind("}")+1])

def generate_weekly_plan(summary):
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":summary}]
    )
    return res.choices[0].message.content