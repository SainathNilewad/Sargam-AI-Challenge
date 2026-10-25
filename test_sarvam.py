import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

api_key = os.environ.get("SARVAM_API_KEY")
if not api_key:
    print("ERROR: SARVAM_API_KEY is not set in environment or .env file.")
    sys.exit(1)

# Masked check for user assurance
masked_key = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "***"
print(f"Loaded SARVAM_API_KEY: {masked_key}")

try:
    import requests

    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "model": "sarvam-105b",
        "messages": [
            {"role": "user", "content": "Respond in 5 words or fewer: 'Sarvam AI connection successful!'"}
        ],
        "temperature": 0.1
    }
    print("Testing connection to Sarvam 105B Chat Completion API (https://api.sarvam.ai/v1/chat/completions)...")
    response = requests.post("https://api.sarvam.ai/v1/chat/completions", json=payload, headers=headers, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        print("Success! Response from Sarvam 105B:")
        print(f"> {reply.strip()}")
    else:
        print(f"API Error {response.status_code}: {response.text}")
except Exception as e:
    print(f"Exception during API test: {e}")
