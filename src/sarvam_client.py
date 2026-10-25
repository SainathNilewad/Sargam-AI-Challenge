import os
import io
import json
import time
import zipfile
import requests
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

class SarvamClient:
    def __init__(self):
        self.api_key = os.environ.get("SARVAM_API_KEY")
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY not found in environment or .env file.")
        self.base_headers = {
            "api-subscription-key": self.api_key
        }

    def digitise_document(self, file_path: str, language: str = "en-IN", output_format: str = "md") -> dict:
        """
        Uses Sarvam Vision / Document Intelligence to extract text & structure from a PDF or image.
        Doc ref: https://docs.sarvam.ai/api/api-guides-tutorials/document-intelligence/overview
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_name = os.path.basename(file_path)
        mime_type = "application/pdf" if file_name.lower().endswith(".pdf") else "image/png"
        
        # 1. Submit digitise job
        url = "https://api.sarvam.ai/doc-ai/v1/job/digitise"
        with open(file_path, "rb") as f:
            files = {"file": (file_name, f, mime_type)}
            data = {"language": language, "output_format": output_format}
            resp = requests.post(url, headers=self.base_headers, files=files, data=data, timeout=60)
            
        if resp.status_code not in (200, 201, 202):
            raise RuntimeError(f"Sarvam Document AI error ({resp.status_code}): {resp.text}")

        job_info = resp.json()
        job_id = job_info.get("job_id")
        
        # 2. Poll until terminal state
        terminal_states = {"completed", "partially_completed", "failed", "rejected"}
        status_url = f"https://api.sarvam.ai/doc-ai/v1/job/{job_id}/status"
        
        for _ in range(30): # max 2.5 minutes
            st_resp = requests.get(status_url, headers=self.base_headers, timeout=30)
            if st_resp.status_code == 200:
                st_data = st_resp.json()
                status = st_data.get("status", "").lower()
                if status in terminal_states:
                    if status in ("failed", "rejected"):
                        raise RuntimeError(f"Sarvam Document AI job {job_id} {status}: {st_data}")
                    break
            time.sleep(3)
        else:
            raise TimeoutError(f"Sarvam Document AI job {job_id} timed out.")

        # 3. Get download URL
        dl_url_endpoint = f"https://api.sarvam.ai/doc-ai/v1/job/{job_id}/download-url"
        dl_resp = requests.get(dl_url_endpoint, headers=self.base_headers, timeout=30)
        if dl_resp.status_code != 200:
            raise RuntimeError(f"Failed to get download URL: {dl_resp.text}")
            
        download_info = dl_resp.json()
        direct_download_url = download_info.get("download_url") or download_info.get("url")
        
        # 4. Download output zip and unpack
        file_resp = requests.get(direct_download_url, timeout=60)
        if file_resp.status_code != 200:
            raise RuntimeError(f"Failed to download result zip: {file_resp.status_code}")
            
        z = zipfile.ZipFile(io.BytesIO(file_resp.content))
        full_markdown = ""
        pages_content = {}
        
        for name in z.namelist():
            if name.endswith(".md"):
                full_markdown = z.read(name).decode("utf-8", errors="replace")
            elif "page_" in name and name.endswith(".json"):
                # Page metadata / blocks
                try:
                    page_data = json.loads(z.read(name).decode("utf-8", errors="replace"))
                    pages_content[name] = page_data
                except Exception:
                    pass

        return {
            "job_id": job_id,
            "file_name": file_name,
            "markdown": full_markdown,
            "pages": pages_content
        }

    def chat_completion(self, messages: list, temperature: float = 0.1, json_mode: bool = True, max_retries: int = 2) -> dict:
        """
        Uses Sarvam-105B chat model for structured reasoning and tagging.
        Strict JSON validation with up to 2 retries.
        Doc ref: https://docs.sarvam.ai/api-reference/chat/chat-completions-v1
        """
        url = "https://api.sarvam.ai/v1/chat/completions"
        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "sarvam-105b",
            "messages": messages,
            "temperature": temperature,
            "reasoning_effort": None,
            "max_tokens": 4096
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        last_err = None
        for attempt in range(max_retries + 1):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=90)
                if resp.status_code != 200:
                    raise RuntimeError(f"Sarvam 105B API Error ({resp.status_code}): {resp.text}")
                    
                result = resp.json()
                message_obj = result.get("choices", [{}])[0].get("message", {})
                content = message_obj.get("content")
                if content is None:
                    content = message_obj.get("reasoning_content") or ""
                
                if json_mode:
                    # Clean markdown code blocks if model wrapped it in ```json ... ```
                    cleaned_content = (content or "").strip()
                    if cleaned_content.startswith("```json"):
                        cleaned_content = cleaned_content[7:]
                    if cleaned_content.startswith("```"):
                        cleaned_content = cleaned_content[3:]
                    if cleaned_content.endswith("```"):
                        cleaned_content = cleaned_content[:-3]
                    cleaned_content = cleaned_content.strip()
                    
                    parsed_json = json.loads(cleaned_content)
                    return parsed_json
                else:
                    return {"text": content}
            except Exception as e:
                last_err = e
                # Retry with an instruction emphasizing valid JSON
                if json_mode and attempt < max_retries:
                    messages = list(messages) + [
                        {"role": "assistant", "content": content if 'content' in locals() else ""},
                        {"role": "user", "content": f"Your previous response had invalid JSON format: {str(e)}. Please output ONLY valid, RFC 8259 compliant JSON."}
                    ]
                    payload["messages"] = messages
                    time.sleep(1.5)
                else:
                    break

        raise ValueError(f"Failed to obtain valid JSON from Sarvam 105B after {max_retries} retries: {last_err}")

    def text_to_speech(self, text: str, language_code: str = "hi-IN", model: str = "bulbul:v4-flash", speaker: str = "shubh_enhi_ads") -> bytes:
        """
        Uses Bulbul text-to-speech to synthesize natural Indic speech.
        Doc ref: https://docs.sarvam.ai/api-reference/text-to-speech/convert
        """
        import base64
        url = "https://api.sarvam.ai/text-to-speech"
        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Limit text length to Bulbul constraint
        text_truncated = text[:2400]
        payload = {
            "text": text_truncated,
            "language_code": language_code,
            "model": model,
            "speaker": speaker
        }
        
        resp = requests.post(url, headers=headers, json=payload, timeout=45)
        if resp.status_code != 200:
            # Fallback to bulbul:v3 with default speaker 'shubh' if v4-flash voice fails
            if model == "bulbul:v4-flash":
                payload["model"] = "bulbul:v3"
                payload["speaker"] = "shubh"
                resp = requests.post(url, headers=headers, json=payload, timeout=45)
            if resp.status_code != 200:
                raise RuntimeError(f"Bulbul TTS Error ({resp.status_code}): {resp.text}")

        data = resp.json()
        audios = data.get("audios", [])
        if not audios:
            raise ValueError("No audio returned from Bulbul API")
            
        return base64.b64decode(audios[0])
