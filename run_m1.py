import os
import sys
import sqlite3
import pandas as pd
from dotenv import load_dotenv

# Ensure stdout handles UTF-8 on Windows
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

from src.extractor import QuestionExtractor

def main():
    print("=" * 80)
    print("MILESTONE 1 (M1): EXTRACT QUESTIONS FROM ONE SAMPLE PAPER INTO A TABLE")
    print("=" * 80)
    
    sample_pdf = os.path.join("sample_papers", "CBSE_Class10_Maths_2023.pdf")
    if not os.path.exists(sample_pdf):
        print(f"Sample PDF not found at {sample_pdf}")
        sys.exit(1)

    extractor = QuestionExtractor()
    df = extractor.extract_from_file(sample_pdf, default_year=2023)

    print("\nExtraction Complete! Summary:")
    print(f"- Total questions extracted: {len(df)}")
    print(f"- Confidence status counts:\n{df['confidence_flag'].value_counts().to_string()}")
    print(f"- Marks sum (valid): {df['marks'].sum()} marks")
    
    # Save to CSV
    csv_path = os.path.join("data", "extracted_questions_m1.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"\n[Saved to CSV]: {csv_path}")

    # Save to SQLite
    db_path = os.path.join("data", "exam_papers.db")
    conn = sqlite3.connect(db_path)
    df.to_sql("questions_m1", conn, if_exists="replace", index=False)
    conn.close()
    print(f"[Saved to SQLite]: {db_path} (table 'questions_m1')")

    print("\n" + "=" * 80)
    print("EXTRACTED QUESTIONS TABLE (SAMPLE)")
    print("=" * 80)
    
    # Display columns: question_number, paper_year, marks, confidence_flag, evidence_source, question_text (truncated)
    display_df = df[["question_number", "paper_year", "marks", "confidence_flag", "evidence_source", "question_text"]].copy()
    display_df["question_text"] = display_df["question_text"].apply(lambda t: (t[:65] + "...") if len(t) > 65 else t)
    print(display_df.to_string(index=False))
    
    print("\n" + "=" * 80)
    print("ITEMS MARKED 'needs review':")
    needs_review = df[df["confidence_flag"] == "needs review"]
    if not needs_review.empty:
        for idx, row in needs_review.iterrows():
            print(f"- {row['question_number']} (Source: {row['evidence_source']}): {row['question_text']} [Marks: {row['marks']}]")
    else:
        print("None. All questions extracted with high confidence.")
    print("=" * 80)

if __name__ == "__main__":
    main()
