import os
import sys
import json
import sqlite3
import pandas as pd
from dotenv import load_dotenv

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

import src.tools as tools

def main():
    print("=" * 80)
    print("TAGGING ALL 5 PAPERS (2020-2024) AND GENERATING COVERAGE REPORT (F2)")
    print("=" * 80)

    # 1. Load syllabus
    with open("data/syllabus.json", "r", encoding="utf-8") as f:
        syllabus = json.load(f)

    # 2. Query untagged questions from database
    conn = sqlite3.connect(tools.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, paper, year, q_no, marks, text, confidence, evidence_source
    FROM questions
    WHERE topic IS NULL OR topic = ''
    ORDER BY paper, q_no
    """)
    rows = cursor.fetchall()
    conn.close()

    untagged_qs = []
    for r in rows:
        untagged_qs.append({
            "id": r[0],
            "paper": r[1],
            "year": r[2],
            "q_no": r[3],
            "marks": r[4],
            "text": r[5],
            "confidence": r[6],
            "evidence_source": r[7]
        })

    print(f"Found {len(untagged_qs)} untagged questions across all 5 papers.")

    # 3. Batch tag questions with Sarvam-105B
    batch_size = 15
    for i in range(0, len(untagged_qs), batch_size):
        batch = untagged_qs[i:i + batch_size]
        print(f"Tagging batch {i//batch_size + 1}/{(len(untagged_qs)-1)//batch_size + 1} ({len(batch)} questions)...")
        tools.tag_questions(batch, syllabus)

    # 4. Generate coverage report
    conn = sqlite3.connect(tools.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT 
        paper, 
        COUNT(*) as extracted, 
        COUNT(CASE WHEN topic IS NOT NULL AND topic != '' THEN 1 END) as tagged,
        COUNT(CASE WHEN topic = 'unclear' THEN 1 END) as unclear
    FROM questions
    GROUP BY paper
    ORDER BY paper
    """)
    coverage_rows = cursor.fetchall()

    print("\n" + "=" * 80)
    print("COVERAGE REPORT PER PAPER (2020-2024)")
    print("=" * 80)
    print(f"{'Paper Name':<32} | {'Extracted':<10} | {'Tagged':<10} | {'Unclear':<10}")
    print("-" * 80)
    for r in coverage_rows:
        print(f"{r[0]:<32} | {r[1]:<10} | {r[2]:<10} | {r[3]:<10}")
    print("-" * 80)

    # 5. Check syllabus topic representation
    cursor.execute("""
    SELECT topic, COUNT(*) as cnt
    FROM questions
    WHERE topic IS NOT NULL AND topic != 'unclear'
    GROUP BY topic
    """)
    topic_counts = dict(cursor.fetchall())
    conn.close()

    zero_topics = [t for t in syllabus if t not in topic_counts or topic_counts[t] == 0]
    present_topics = {t: topic_counts.get(t, 0) for t in syllabus if topic_counts.get(t, 0) > 0}

    print("\nSYLLABUS TOPICS COVERAGE:")
    print(f"Topics with questions ({len(present_topics)}/{len(syllabus)}):")
    for t, c in sorted(present_topics.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {t:<35}: {c} questions")

    print(f"\nSyllabus Topics with ZERO questions ({len(zero_topics)}):")
    if zero_topics:
        for t in zero_topics:
            print(f"  ⚠️  {t}")
    else:
        print("  None! Every syllabus topic is represented in the dataset.")

    # 6. Verify get_topic_stats status
    print("\n" + "=" * 80)
    print("VERIFYING get_topic_stats() SUCCESS STATUS")
    print("=" * 80)
    stats = tools.get_topic_stats()
    print(f"get_topic_stats() status: '{stats.get('status')}'")
    if stats.get("status") == "success":
        print(f"✅ Success! Total questions: {stats.get('total_questions')}, Total marks: {stats.get('total_marks')}")
    else:
        print(f"⚠️ Incomplete: {stats.get('partial_data')}")

if __name__ == "__main__":
    main()
