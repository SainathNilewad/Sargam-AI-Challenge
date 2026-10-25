import os
import re
import json
import pandas as pd
from typing import List, Dict, Any
from src.sarvam_client import SarvamClient

class QuestionExtractor:
    def __init__(self, sarvam_client: SarvamClient = None):
        self.client = sarvam_client or SarvamClient()

    def extract_from_file(self, file_path: str, default_year: int = 2023) -> pd.DataFrame:
        """
        Processes a question paper (PDF, image, or text) using Sarvam Vision,
        then structures every question into a standardized pandas DataFrame.
        """
        file_name = os.path.basename(file_path)
        print(f"[Extractor] Processing '{file_name}' with Sarvam Vision...")
        
        # If it's already a text file, we can read it directly; if PDF/image, we use Sarvam Vision
        if file_path.lower().endswith(".txt"):
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            doc_info = {
                "file_name": file_name,
                "markdown": content,
                "pages": {}
            }
        else:
            doc_info = self.client.digitise_document(file_path, language="en-IN", output_format="md")

        markdown_text = doc_info.get("markdown", "")
        if not markdown_text.strip():
            raise ValueError(f"No text extracted from {file_name}")

        # Attempt to detect year from text
        year_match = re.search(r'\b(20[12][0-9])\b', markdown_text)
        detected_year = int(year_match.group(1)) if year_match else default_year

        # Now pass to Sarvam-105B for rigorous question-level breakdown
        print(f"[Extractor] Structuring questions using Sarvam-105B (Detected Year: {detected_year})...")
        
        prompt = f"""
You are an expert examination paper parser.
The following text is OCR-digitized from past exam paper '{file_name}'.
Extract every single question into a structured JSON list.

Rules:
1. 'question_number': Extract standard question identifier (e.g. 'Q1', 'Q2', 'Q10').
2. 'paper_year': Integer year ({detected_year}).
3. 'marks': Integer marks allotted (e.g. 1, 2, 3, 5). If marks are missing or unclear, set null.
4. 'question_text': Exact question text. Keep both Hindi and English if present.
5. 'page_number': Page number if identifiable, else estimated (1, 2, 3).
6. 'confidence_flag': 'OK' if the question is complete and legible. If the question is fragmentary, blurred, missing marks, or unreadable, set to 'needs review'.
7. 'evidence_source': Exact reference string format: "{file_name}:Page <page>:Q<num>"

OCR Document Content:
\"\"\"
{markdown_text[:12000]}
\"\"\"

Return ONLY a JSON object with a single key 'questions':
{{
  "questions": [
    {{
      "question_number": "Q1",
      "paper_year": {detected_year},
      "marks": 1,
      "question_text": "...",
      "page_number": 1,
      "confidence_flag": "OK",
      "evidence_source": "{file_name}:Page 1:Q1"
    }}
  ]
}}
"""
        messages = [
            {"role": "system", "content": "You are a precise data extraction system that strictly returns JSON."},
            {"role": "user", "content": prompt}
        ]

        extracted_json = self.client.chat_completion(messages, temperature=0.1, json_mode=True)
        raw_questions = extracted_json.get("questions", [])

        # Normalize and construct DataFrame
        records = []
        for q in raw_questions:
            q_num = str(q.get("question_number", "Unnumbered")).strip()
            marks_val = q.get("marks")
            try:
                marks_int = int(marks_val) if marks_val is not None else None
            except (ValueError, TypeError):
                marks_int = None
                
            flag = q.get("confidence_flag", "OK")
            # If marks are missing or question text indicates blurred/damaged content, mark 'needs review'
            q_text = str(q.get("question_text", "")).strip()
            if marks_int is None or "[BLURRED" in q_text or "???" in q_text or len(q_text) < 15:
                flag = "needs review"

            page_num = q.get("page_number", 1)
            evidence = q.get("evidence_source", f"{file_name}:Page {page_num}:{q_num}")

            records.append({
                "paper_year": int(q.get("paper_year", detected_year)),
                "question_number": q_num,
                "marks": marks_int,
                "question_text": q_text,
                "source_file": file_name,
                "page_number": page_num,
                "evidence_source": evidence,
                "confidence_flag": flag
            })

        df = pd.DataFrame(records)
        return df
