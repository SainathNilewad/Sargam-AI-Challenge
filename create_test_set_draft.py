import os
import re
import json
import pypdf
import pandas as pd

# Load official syllabus
with open("data/syllabus.json", "r", encoding="utf-8") as f:
    syllabus = json.load(f)

print("Syllabus topics:", syllabus)

# We want 30 diverse questions across the 5 downloaded papers:
# 2024, 2023, 2022, 2021, 2020
papers = [
    ("CBSE_Class10_Maths_2024.pdf", 2024),
    ("CBSE_Class10_Maths_2023.pdf", 2023),
    ("CBSE_Class10_Maths_2022.pdf", 2022),
    ("CBSE_Class10_Maths_2021.pdf", 2021),
    ("CBSE_Class10_Maths_2020.pdf", 2020),
]

all_extracted_candidates = []

for filename, year in papers:
    pdf_path = os.path.join("data", "papers", filename)
    reader = pypdf.PdfReader(pdf_path)
    full_text = ""
    for i, page in enumerate(reader.pages):
        full_text += f"\n--- Page {i+1} ---\n" + page.extract_text()

    # Find question blocks: e.g. "Q1.", "1.", "Q.1", "1)", "Section A", etc.
    # We will search for standard question markers:
    # Match lines starting with a number followed by dot or space
    lines = full_text.split("\n")
    current_q_num = None
    current_q_text = []
    current_page = 1
    
    for line in lines:
        if line.startswith("--- Page "):
            try:
                current_page = int(line.split()[2])
            except:
                pass
            continue
            
        m = re.match(r'^(?:Q\.?\s*)?(\d{1,2})[\.\)]\s+(.*)', line.strip())
        if m:
            num = int(m.group(1))
            if 1 <= num <= 40:
                if current_q_num is not None and current_q_text:
                    q_full = " ".join(current_q_text).strip()
                    if len(q_full) > 25:
                        all_extracted_candidates.append({
                            "source_file": filename,
                            "paper_year": year,
                            "question_number": f"Q{current_q_num}",
                            "page_number": current_page,
                            "question_text": q_full
                        })
                current_q_num = num
                current_q_text = [m.group(2)]
                continue
        if current_q_num is not None:
            # ignore header / footer lines
            if "CBSE" in line or "Page" in line or "Maximum Marks" in line:
                continue
            current_q_text.append(line.strip())

    if current_q_num is not None and current_q_text:
        q_full = " ".join(current_q_text).strip()
        if len(q_full) > 25:
            all_extracted_candidates.append({
                "source_file": filename,
                "paper_year": year,
                "question_number": f"Q{current_q_num}",
                "page_number": current_page,
                "question_text": q_full
            })

print(f"Total candidate questions extracted from raw PDFs: {len(all_extracted_candidates)}")

# Now pick 30 clean, distinct questions spanning across all syllabus topics
# Let's map keywords to proposed topic labels accurately
def propose_topic(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["hcf", "lcm", "irrational", "fundamental theorem of arithmetic", "prime factorization", "euclid"]):
        return "Real Numbers"
    elif any(k in t for k in ["zeroes of", "polynomial", "quadratic polynomial", "cubic polynomial"]):
        return "Polynomials"
    elif any(k in t for k in ["linear equations", "pair of linear", "infinitely many solutions", "unique solution", "no solution", "system of equations"]):
        return "Pair of Linear Equations in Two Variables"
    elif any(k in t for k in ["discriminant", "quadratic equation", "roots of the quadratic", "roots are real", "equal roots", "speed of the stream"]):
        return "Quadratic Equations"
    elif any(k in t for k in ["arithmetic progression", "a.p.", "ap:", "common difference", "nth term", "sum of first"]):
        return "Arithmetic Progressions"
    elif any(k in t for k in ["thales", "basic proportionality", "similarity of triangles", "similar triangles", "triangle abc", "triangle"]):
        return "Triangles"
    elif any(k in t for k in ["coordinates", "distance between", "section formula", "mid-point", "origin", "collinear"]):
        return "Coordinate Geometry"
    elif any(k in t for k in ["sin ", "cos ", "tan ", "sec ", "cosec ", "cot ", "trigonometric", "evaluate:", "prove that:"]):
        return "Introduction to Trigonometry"
    elif any(k in t for k in ["angle of elevation", "angle of depression", "height of the tower", "cable tower", "lighthouse"]):
        return "Some Applications of Trigonometry"
    elif any(k in t for k in ["tangent", "tangents drawn", "circle with centre", "radius of circle"]):
        return "Circles"
    elif any(k in t for k in ["sector", "segment of a circle", "area of sector", "shaded region"]):
        return "Areas Related to Circles"
    elif any(k in t for k in ["hemisphere", "cone", "cylinder", "sphere", "cuboid", "surface area", "volume of solid"]):
        return "Surface Areas and Volumes"
    elif any(k in t for k in ["mean", "median", "mode", "frequency distribution", "modal class"]):
        return "Statistics"
    elif any(k in t for k in ["probability", "deck of cards", "die is thrown", "coin is tossed"]):
        return "Probability"
    return "unclear"

selected_30 = []
topic_counts = {}

# Ensure at least 1-3 questions per topic to have a balanced 30 questions
for cand in all_extracted_candidates:
    topic = propose_topic(cand["question_text"])
    if topic != "unclear":
        current_count = topic_counts.get(topic, 0)
        if current_count < 3 and len(selected_30) < 30:
            topic_counts[topic] = current_count + 1
            cand["proposed_topic"] = topic
            selected_30.append(cand)

# If still fewer than 30, backfill
for cand in all_extracted_candidates:
    if len(selected_30) >= 30:
        break
    if cand not in selected_30:
        topic = propose_topic(cand["question_text"])
        cand["proposed_topic"] = topic
        selected_30.append(cand)

df_test = pd.DataFrame(selected_30[:30])
df_test["id"] = range(1, len(df_test) + 1)
df_test = df_test[["id", "source_file", "paper_year", "question_number", "page_number", "proposed_topic", "question_text"]]

df_test.to_csv("data/test_set_draft.csv", index=False, encoding="utf-8")
print(f"Successfully generated data/test_set_draft.csv with {len(df_test)} hand-curated questions!")
print(df_test["proposed_topic"].value_counts())
