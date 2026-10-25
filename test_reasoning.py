import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()
key = os.environ.get("SARVAM_API_KEY")
headers = {"api-subscription-key": key, "Content-Type": "application/json"}

payload = {
    "model": "sarvam-105b",
    "messages": [
        {"role": "system", "content": "You are a parser that outputs valid JSON."},
        {"role": "user", "content": "Extract in JSON: Question 1: What is the capital of India? [1 mark]"}
    ],
    "reasoning_effort": None,
    "temperature": 0.1,
    "response_format": {"type": "json_object"}
}

r = requests.post("https://api.sarvam.ai/v1/chat/completions", json=payload, headers=headers, timeout=30)
print("status:", r.status_code)
d = r.json()
print("content:", d["choices"][0]["message"].get("content"))
print("usage:", d.get("usage"))
