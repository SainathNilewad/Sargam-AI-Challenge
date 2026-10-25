import os
import sys
import pandas as pd
from dotenv import load_dotenv

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

from src.tools import extract_paper

def main():
    print("=" * 85)
    print("MILESTONE 1 (M1): extract_paper ON SAMPLE PAPER (CBSE Class 10 Maths 2024)")
    print("=" * 85)

    sample_pdf = os.path.join("data", "papers", "CBSE_Class10_Maths_2024.pdf")
    if not os.path.exists(sample_pdf):
        print(f"File not found: {sample_pdf}")
        sys.exit(1)

    print(f"Calling tool: extract_paper('{sample_pdf}')...")
    questions = extract_paper(sample_pdf)

    df = pd.DataFrame(questions)
    print(f"\nExtracted {len(df)} questions from {sample_pdf} using Sarvam Document AI.")
    print(f"Total Marks Extracted: {df['marks'].sum():.1f}")
    print(f"Confidence Breakdown:\n{df['confidence'].value_counts().to_string()}")

    print("\n" + "=" * 85)
    print("STRUCTURED QUESTIONS TABLE (Sample of extracted rows)")
    print("=" * 85)
    
    display_df = df[["q_no", "year", "marks", "confidence", "evidence_source", "text"]].copy()
    display_df["text"] = display_df["text"].apply(lambda t: (t[:65] + "...") if len(t) > 65 else t)
    
    # Print first 15 questions and last 5 questions
    print(pd.concat([display_df.head(12), display_df.tail(5)]).to_string(index=False))

    # Save to CSV for persistent inspection
    output_csv = os.path.join("data", "m1_extracted_table.csv")
    df.to_csv(output_csv, index=False, encoding="utf-8")
    print(f"\n[Saved full M1 table to]: {output_csv}")
    print("=" * 85)

if __name__ == "__main__":
    main()
