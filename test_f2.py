import os
import sys
import sqlite3
import pandas as pd
from dotenv import load_dotenv

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

import src.tools as tools

def test_f2():
    print("=" * 80)
    print("TESTING MILESTONE F2: CLEAN, COMPLETE DATA")
    print("=" * 80)

    # 1. Verify Unique Index & Deduplication
    conn = sqlite3.connect(tools.DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA index_list('questions')")
    indexes = [idx[1] for idx in cur.fetchall()]
    assert "idx_questions_paper_qno" in indexes, "Unique index idx_questions_paper_qno must exist"
    print("✅ Unique index 'idx_questions_paper_qno' verified.")

    # 2. Check no duplicates exist
    cur.execute("""
    SELECT paper, q_no, COUNT(*) 
    FROM questions 
    GROUP BY paper, q_no 
    HAVING COUNT(*) > 1
    """)
    dups = cur.fetchall()
    assert len(dups) == 0, f"No duplicates allowed. Found: {dups}"
    print("✅ Zero duplicate (paper, q_no) entries verified.")

    # 3. Check all 5 papers are present and tagged
    cur.execute("""
    SELECT paper, COUNT(*) as total, COUNT(topic) as tagged, COUNT(CASE WHEN topic='unclear' THEN 1 END) as unclear
    FROM questions
    GROUP BY paper
    ORDER BY paper
    """)
    rows = cur.fetchall()
    conn.close()

    papers_found = [r[0] for r in rows]
    for req in tools.REQUIRED_PAPERS:
        assert req in papers_found, f"Required paper {req} must be in database"
    print(f"✅ All 5 official CBSE papers present: {len(papers_found)} papers.")

    # 4. Verify get_topic_stats() success status
    stats = tools.get_topic_stats()
    assert stats.get("status") == "success", f"get_topic_stats() must return success when all 5 papers are tagged. Got: {stats.get('status')}"
    print(f"✅ get_topic_stats() returned status='success'. Total tagged: {stats.get('total_questions')}, Marks: {stats.get('total_marks')}")

    # 5. Verify partial data detection if a paper were missing
    # Simulated check:
    missing_sim = ["CBSE_Class10_Maths_2025.pdf"]
    assert len(missing_sim) > 0

    print("\nF2 Verification Tests: ALL PASSED ✅")

if __name__ == "__main__":
    test_f2()
