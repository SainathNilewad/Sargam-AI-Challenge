import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()
key = os.environ.get("SARVAM_API_KEY")
headers = {"api-subscription-key": key, "Content-Type": "application/json"}

with open("sample_papers/CBSE_Class10_Maths_2023.txt", "r", encoding="utf-8") as f:
    text = f.read()

prompt = f"""You are an exam paper parser. Extract questions into JSON.
Document:
{text[:3000]}

Return JSON format: {{"questions": [{{"question_number": "Q1", "marks": 1, "question_text": "..."}}]}}"""

payload = {
    "model": "sarvam-105b",
    "messages": [
        {"role": "system", "content": "You are a parser that outputs valid JSON."},
        {"role": "user", "content": prompt}
    ],
    "max_tokens": 4096,
    "temperature": 0.1,
    "response_format": {"type": "json_object"}
}

print("Sending request to Sarvam 105B...")
r = requests.post("https://api.sarvam.ai/v1/chat/completions", json=payload, headers=headers, timeout=90)
print("Status:", r.status_code)
d = r.json()
msg = d["choices"][0]["message"]
print("Finish reason:", d["choices"][0].get("finish_reason"))
print("Usage:", d.get("usage"))
print("Content is None?", msg.get("content") is None)
if msg.get("content"):
    print("Content preview:", msg.get("content")[:300])
else:
    print("Full message:", msg)
