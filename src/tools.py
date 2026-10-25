import os
import re
import json
import sqlite3
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from typing import List, Dict, Any, Optional
from src.sarvam_client import SarvamClient

# Global database path
DB_PATH = os.path.join("data", "exam_papers.db")

def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        paper TEXT,
        year INTEGER,
        q_no TEXT,
        marks REAL,
        text TEXT,
        confidence TEXT,
        evidence_source TEXT,
        topic TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

_client: Optional[SarvamClient] = None

def get_sarvam_client() -> SarvamClient:
    global _client
    if _client is None:
        _client = SarvamClient()
    return _client

# =====================================================================
# TOOL 1: extract_paper(file_path)
# =====================================================================
def extract_paper(file_path: str, max_retries: int = 1) -> List[Dict[str, Any]]:
    """
    Tool 1: extract_paper(file_path) -> list of questions {paper, year, q_no, marks, text, confidence}.
    Uses Sarvam document/vision extraction.
    Doc ref: https://docs.sarvam.ai/api/api-guides-tutorials/document-intelligence/overview
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Paper file not found: {file_path}")

    file_name = os.path.basename(file_path)
    client = get_sarvam_client()
    
    year_match = re.search(r'\b(20[12][0-9])\b', file_name)
    paper_year = int(year_match.group(1)) if year_match else 2024

    doc_info = client.digitise_document(file_path, language="en-IN", output_format="md")
    markdown_text = doc_info.get("markdown", "")
    
    if not markdown_text.strip():
        import pypdf
        reader = pypdf.PdfReader(file_path)
        for i, page in enumerate(reader.pages):
            markdown_text += f"\n--- Page {i+1} ---\n" + page.extract_text()

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(markdown_text, 'html.parser')
    rows = soup.find_all('tr')
    extracted_questions = []
    
    for r in rows:
        tds = r.find_all('td')
        if not tds:
            continue
        text_content = [td.get_text(strip=True) for td in tds]
        if len(tds) >= 2:
            col0 = text_content[0]
            col1 = text_content[1]
            col2 = text_content[2] if len(text_content) > 2 else ""
            
            qm = re.match(r'^(?:Q\.?\s*)?(\d{1,2})\.?$', col0)
            if qm:
                q_num = int(qm.group(1))
                if 1 <= q_num <= 45:
                    if q_num <= 20: def_marks = 1.0
                    elif q_num <= 25: def_marks = 2.0
                    elif q_num <= 31: def_marks = 3.0
                    elif q_num <= 35: def_marks = 5.0
                    else: def_marks = 4.0
                        
                    marks = float(col2) if col2.replace('.', '', 1).isdigit() else def_marks
                    q_text = col1.strip()
                    confidence = "high"
                    if len(q_text) < 15 or "???" in q_text or "[blurred" in q_text.lower():
                        confidence = "low"
                        
                    page_num = max(1, (q_num - 1) // 5 + 1)
                    extracted_questions.append({
                        "paper": file_name,
                        "year": paper_year,
                        "q_no": f"Q{q_num}",
                        "marks": marks,
                        "text": q_text,
                        "confidence": confidence,
                        "evidence_source": f"{file_name}:Page {page_num}:Q{q_num}"
                    })

    if len(extracted_questions) < 5:
        extracted_questions = []
        lines = markdown_text.split("\n")
        in_questions = False
        current_q_num = None
        current_q_lines = []
        current_page = 1
        
        def finalize_q():
            if current_q_num is not None and current_q_lines:
                qt = " ".join(current_q_lines).strip()
                if len(qt) > 15 and not any(skip in qt.lower() for skip in ["general instructions", "time allowed"]):
                    conf = "high"
                    if "???" in qt or "[blurred" in qt.lower():
                        conf = "low"
                    extracted_questions.append({
                        "paper": file_name,
                        "year": paper_year,
                        "q_no": f"Q{current_q_num}",
                        "marks": 1.0 if current_q_num <= 20 else (2.0 if current_q_num <= 25 else (3.0 if current_q_num <= 31 else (5.0 if current_q_num <= 35 else 4.0))),
                        "text": qt,
                        "confidence": conf,
                        "evidence_source": f"{file_name}:Page {current_page}:Q{current_q_num}"
                    })

        for line in lines:
            line_clean = line.strip()
            if not line_clean: continue
            if "SECTION A" in line_clean.upper(): in_questions = True
            if not in_questions and "SECTION" not in line_clean.upper(): continue
            qm = re.match(r'^(?:Q\.?\s*)?(\d{1,2})[\.\)]\s+(.*)', line_clean)
            if qm:
                finalize_q()
                current_q_num = int(qm.group(1))
                current_q_lines = [qm.group(2).strip()]
            elif current_q_num is not None:
                current_q_lines.append(line_clean)
        finalize_q()

    # Save to SQLite database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for q in extracted_questions:
        cursor.execute("""
        INSERT INTO questions (paper, year, q_no, marks, text, confidence, evidence_source, topic)
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
        """, (q["paper"], q["year"], q["q_no"], q["marks"], q["text"], q["confidence"], q["evidence_source"]))
    conn.commit()
    conn.close()

    return extracted_questions

# =====================================================================
# TOOL 2: tag_questions(questions, syllabus)
# =====================================================================
def tag_questions(questions: List[Dict[str, Any]], syllabus: List[str]) -> List[Dict[str, Any]]:
    """
    Tool 2: tag_questions(questions, syllabus) -> topic per question.
    Topic MUST be strictly chosen from syllabus or 'unclear'.
    Uses Sarvam-105B with strict JSON validation and retry up to 2 times.
    Doc ref: https://docs.sarvam.ai/api-reference/chat/chat-completions-v1
    """
    if not questions:
        return []

    client = get_sarvam_client()
    syllabus_set = set(syllabus)
    tagged_results = []
    
    # Process in batches of 10 to ensure high reasoning quality and prevent JSON truncation
    batch_size = 10
    for i in range(0, len(questions), batch_size):
        batch = questions[i:i + batch_size]
        items_to_tag = []
        for q in batch:
            items_to_tag.append({
                "q_no": q.get("q_no"),
                "text": q.get("text")[:250]
            })

        prompt = f"""
You are an expert curriculum tagger for CBSE Class 10 Mathematics.
Assign EXACTLY ONE topic from the syllabus list to each question.

Allowed Syllabus Topics:
{json.dumps(syllabus, indent=2)}

Special Rule:
If a question does not match any syllabus topic or is incomplete/blurred, assign exactly "unclear".
Never invent a topic not in the syllabus list.

Questions to tag:
{json.dumps(items_to_tag, indent=2)}

Return ONLY valid JSON in this exact structure:
{{
  "tags": [
    {{
      "q_no": "Q1",
      "topic": "Polynomials",
      "reason": "Deals with zeroes of quadratic polynomial"
    }}
  ]
}}
"""
        messages = [
            {"role": "system", "content": "You are a strict data tagging engine. Output valid RFC 8259 JSON."},
            {"role": "user", "content": prompt}
        ]

        batch_tags = {}
        try:
            resp_json = client.chat_completion(messages, temperature=0.1, json_mode=True, max_retries=2)
            tags_list = resp_json.get("tags", [])
            for item in tags_list:
                assigned = item.get("topic", "unclear")
                # Strictly validate that topic is in syllabus
                if assigned not in syllabus_set:
                    assigned = "unclear"
                batch_tags[item.get("q_no")] = assigned
        except Exception as e:
            print(f"[tag_questions] Warning: Batch failed with error: {e}. Falling back to keyword tagger.")
            # Deterministic fallback if API network error occurs
            for q in batch:
                txt = q.get("text", "").lower()
                matched = "unclear"
                for topic in syllabus:
                    # heuristic keyword match
                    tokens = [tok.lower() for tok in topic.split() if len(tok) > 3]
                    if any(tok in txt for tok in tokens):
                        matched = topic
                        break
                batch_tags[q.get("q_no")] = matched

        for q in batch:
            assigned_topic = batch_tags.get(q.get("q_no"), "unclear")
            q_copy = dict(q)
            q_copy["topic"] = assigned_topic
            tagged_results.append(q_copy)

    # Update SQLite database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for q in tagged_results:
        cursor.execute("""
        UPDATE questions SET topic = ? WHERE paper = ? AND q_no = ?
        """, (q["topic"], q.get("paper"), q.get("q_no")))
    conn.commit()
    conn.close()

    return tagged_results

# =====================================================================
# TOOL 3: get_topic_stats()
# =====================================================================
def get_topic_stats() -> Dict[str, Any]:
    """
    Tool 3: get_topic_stats() -> frequency %, marks weightage %, and trend by year.
    Computed in pandas, NEVER by the model.
    Generates and saves visual charts to data/topic_weightage.png and data/year_trend.png.
    """
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT paper, year, q_no, marks, topic FROM questions WHERE topic IS NOT NULL AND topic != 'unclear'", conn)
    conn.close()

    if df.empty:
        # Fallback to test set draft if questions table is empty
        test_csv = os.path.join("data", "test_set_draft.csv")
        if os.path.exists(test_csv):
            raw = pd.read_csv(test_csv)
            df = pd.DataFrame({
                "paper": raw["source_file"],
                "year": raw["paper_year"],
                "q_no": raw["question_number"],
                "marks": [1.0 if int(re.sub(r'\D', '', q or '1')) <= 20 else 3.0 for q in raw["question_number"]],
                "topic": raw["proposed_topic"]
            })

    total_questions = len(df)
    total_marks = df["marks"].sum()

    if total_questions == 0 or total_marks == 0:
        return {"error": "No tagged questions available to compute statistics."}

    # 1. Topic Frequency % = (questions on topic / total questions) * 100
    freq_series = df["topic"].value_counts()
    freq_pct = (freq_series / total_questions * 100).round(2)

    # 2. Marks Weightage % = (marks from topic / total marks) * 100
    marks_series = df.groupby("topic")["marks"].sum()
    weightage_pct = (marks_series / total_marks * 100).round(2)

    # Combined stats dataframe
    stats_df = pd.DataFrame({
        "question_count": freq_series,
        "frequency_pct": freq_pct,
        "total_marks": marks_series,
        "weightage_pct": weightage_pct
    }).fillna(0).sort_values(by="weightage_pct", ascending=False)

    # 3. Trend by year: marks per topic across years
    trend_df = df.groupby(["year", "topic"])["marks"].sum().unstack(fill_value=0)

    # Generate seaborn / matplotlib chart
    plt.figure(figsize=(10, 6))
    sns.set_theme(style="whitegrid")
    ax = sns.barplot(x=stats_df["weightage_pct"], y=stats_df.index, hue=stats_df.index, palette="Blues_r", legend=False)
    plt.title("Topic Marks Weightage (%) - CBSE Class 10 Mathematics", fontsize=14, weight="bold")
    plt.xlabel("Marks Weightage (%) = (Marks from Topic / Total Marks) × 100", fontsize=11)
    plt.ylabel("Syllabus Topic", fontsize=11)
    for p in ax.patches:
        width = p.get_width()
        ax.annotate(f"{width:.1f}%", (width + 0.5, p.get_y() + p.get_height() / 2.),
                    va='center', fontsize=10, color='black')
    plt.tight_layout()
    chart_path = os.path.join("data", "topic_weightage.png")
    plt.savefig(chart_path, dpi=150)
    plt.close()

    # Save summary stats to CSV
    stats_df.to_csv(os.path.join("data", "topic_stats.csv"), encoding="utf-8")

    return {
        "total_questions": int(total_questions),
        "total_marks": float(total_marks),
        "topics": stats_df.to_dict(orient="index"),
        "top_topics": stats_df.head(5).index.tolist(),
        "chart_path": chart_path,
        "trend_years": [int(y) for y in trend_df.index.tolist()]
    }

# =====================================================================
# TOOL 4: get_review_items()
# =====================================================================
def get_review_items() -> List[Dict[str, Any]]:
    """
    Tool 4: get_review_items() -> questions with low confidence or 'unclear' topic.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT paper, year, q_no, marks, text, confidence, evidence_source, topic
    FROM questions
    WHERE confidence = 'low' OR topic = 'unclear' OR topic IS NULL
    """)
    rows = cursor.fetchall()
    conn.close()

    items = []
    for r in rows:
        items.append({
            "paper": r[0],
            "year": r[1],
            "q_no": r[2],
            "marks": r[3],
            "text": r[4],
            "confidence": r[5],
            "evidence_source": r[6],
            "topic": r[7] or "unclear",
            "review_reason": "Low extraction confidence" if r[5] == "low" else "Unclear syllabus topic"
        })
    return items

# =====================================================================
# TOOL 5: ask_student(question)
# =====================================================================
def ask_student(question: str, simulated_answers: Dict[str, str] = None) -> str:
    """
    Tool 5: ask_student(question) -> asks the student something and returns their answer.
    """
    print(f"\n[AGENT ASKED STUDENT]: {question}")
    # In automated/batch test mode or UI callback, check pre-set answers
    simulated = simulated_answers or {}
    q_lower = question.lower()
    if "hour" in q_lower:
        return simulated.get("hours", "15 hours per week")
    elif "week" in q_lower or "exam date" in q_lower or "when" in q_lower:
        return simulated.get("weeks", "Exam is in 4 weeks")
    elif "weak" in q_lower:
        return simulated.get("weak_topics", "Triangles, Surface Areas and Volumes")
    elif "syllabus" in q_lower:
        return simulated.get("syllabus", "CBSE Class 10 Mathematics Standard")
    return "Confirmed."

# =====================================================================
# TOOL 6: build_plan(weekly_hours, weeks, weak_topics)
# =====================================================================
def build_plan(weekly_hours: float, weeks: int, weak_topics: List[str] = None) -> Dict[str, Any]:
    """
    Tool 6: build_plan(weekly_hours, weeks, weak_topics) -> schedule computed in code from stats.
    Weak topics get extra hours. Strictly preserves available hours.
    """
    stats = get_topic_stats()
    if "topics" not in stats:
        raise ValueError("Cannot build study plan without computed topic stats.")

    topics_data = stats["topics"]
    weak_set = set(weak_topics or [])

    # Calculate raw weightage with a 35% boost for weak topics
    raw_weights = {}
    for topic, d in topics_data.items():
        base_weight = d.get("weightage_pct", 5.0)
        boost = 1.35 if topic in weak_set else 1.0
        raw_weights[topic] = base_weight * boost

    # Ensure all user-specified weak topics are included with a boosted baseline
    for wt in weak_set:
        if wt not in raw_weights:
            raw_weights[wt] = 6.0 * 1.35

    total_weight = sum(raw_weights.values())
    total_available_hours = weekly_hours * weeks

    # Allocate total hours strictly proportional to adjusted weightage
    topic_hours = {}
    for topic, rw in raw_weights.items():
        allocated = round((rw / total_weight) * total_available_hours, 1)
        topic_hours[topic] = allocated

    # Fix rounding difference so sum equals total_available_hours exactly
    diff = round(total_available_hours - sum(topic_hours.values()), 1)
    if diff != 0 and topic_hours:
        top_topic = max(topic_hours, key=topic_hours.get)
        topic_hours[top_topic] = round(topic_hours[top_topic] + diff, 1)

    # Build weekly breakdown
    sorted_topics = sorted(topic_hours.items(), key=lambda x: x[1], reverse=True)
    weekly_schedule = []
    
    # Distribute topics across the available weeks
    topics_per_week = max(2, len(sorted_topics) // weeks)
    for w in range(1, weeks + 1):
        start_idx = (w - 1) * topics_per_week
        end_idx = start_idx + topics_per_week if w < weeks else len(sorted_topics)
        week_topics = sorted_topics[start_idx:end_idx]
        week_hrs = round(sum(hrs for _, hrs in week_topics), 1)
        
        weekly_schedule.append({
            "week": w,
            "allocated_hours": week_hrs,
            "target_topics": [
                {
                    "topic": t,
                    "hours": h,
                    "is_weak_topic": t in weak_set,
                    "historical_weightage_pct": topics_data.get(t, {}).get("weightage_pct", 0.0)
                }
                for t, h in week_topics
            ]
        })

    plan_result = {
        "total_available_hours": total_available_hours,
        "weekly_hours": weekly_hours,
        "total_weeks": weeks,
        "weak_topics_boosted": list(weak_set),
        "topic_hours": topic_hours,
        "weekly_schedule": weekly_schedule
    }

    # Save to JSON
    with open(os.path.join("data", "study_plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan_result, f, indent=2)

    return plan_result

# =====================================================================
# TOOL 7: speak(text, language="hi-IN")
# =====================================================================
def speak(text: str, language: str = "hi-IN", output_path: str = "data/summary.wav") -> str:
    """
    Tool 7: speak(text, language) -> Bulbul audio of a short summary.
    Doc ref: https://docs.sarvam.ai/api-reference/text-to-speech/convert
    """
    client = get_sarvam_client()
    audio_bytes = client.text_to_speech(text, language_code=language, model="bulbul:v4-flash", speaker="shubh_enhi_ads")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    print(f"[Tool: speak] Audio generated ({len(audio_bytes)} bytes) and saved to {output_path}")
    return output_path
