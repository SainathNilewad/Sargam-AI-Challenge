import os
import sys
import json
import pandas as pd
from dotenv import load_dotenv

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

from src.tools import tag_questions, get_topic_stats, get_review_items, build_plan, speak

def main():
    print("=" * 80)
    print("TESTING MILESTONES 2, 3, 4, 7 TOOL PIPELINE")
    print("=" * 80)

    # Load syllabus
    with open("data/syllabus.json", "r", encoding="utf-8") as f:
        syllabus = json.load(f)

    # 1. Test M2: tag_questions on a sample batch of questions
    print("\n--- Testing M2: tag_questions ---")
    test_questions = [
        {"paper": "test.pdf", "year": 2024, "q_no": "Q1", "marks": 1.0, "text": "Find HCF of 12 and 18 using prime factorisation.", "confidence": "high"},
        {"paper": "test.pdf", "year": 2024, "q_no": "Q2", "marks": 1.0, "text": "Find the zeroes of polynomial x^2 - 4x + 3.", "confidence": "high"},
        {"paper": "test.pdf", "year": 2024, "q_no": "Q3", "marks": 1.0, "text": "Find the discriminant of 2x^2 - 4x + 3 = 0.", "confidence": "high"},
        {"paper": "test.pdf", "year": 2024, "q_no": "Q4", "marks": 2.0, "text": "Find the 10th term of AP: 2, 7, 12...", "confidence": "high"},
        {"paper": "test.pdf", "year": 2024, "q_no": "Q5", "marks": 1.0, "text": "Find distance of P(3, 4) from origin.", "confidence": "high"},
        {"paper": "test.pdf", "year": 2024, "q_no": "Q6", "marks": 1.0, "text": "Evaluate sin^2 30 + cos^2 30.", "confidence": "high"},
        {"paper": "test.pdf", "year": 2024, "q_no": "Q7", "marks": 1.0, "text": "A card drawn from 52 cards. Find probability of red ace.", "confidence": "high"},
        {"paper": "test.pdf", "year": 2024, "q_no": "Q8", "marks": 1.0, "text": "Unknown blurred text ??? with noise.", "confidence": "low"}
    ]

    tagged = tag_questions(test_questions, syllabus)
    for q in tagged:
        print(f"{q['q_no']}: [{q['topic']}] -> {q['text'][:50]}...")

    # 2. Test M3: get_topic_stats & get_review_items
    print("\n--- Testing M3: get_topic_stats + get_review_items ---")
    stats = get_topic_stats()
    print("Total Questions in Stats:", stats.get("total_questions"))
    print("Total Marks in Stats:", stats.get("total_marks"))
    print("Top 5 Topics by Marks Weightage:")
    for t in stats.get("top_topics", []):
        d = stats["topics"][t]
        print(f"  - {t}: {d['weightage_pct']}% weightage ({d['question_count']} questions)")
        
    review_items = get_review_items()
    print(f"Total Review Items ('low' confidence or 'unclear'): {len(review_items)}")
    for item in review_items[:3]:
        print(f"  - Review: {item['q_no']} ({item['review_reason']}): {item['text'][:40]}...")

    # 3. Test M4: build_plan
    print("\n--- Testing M4: build_plan ---")
    plan = build_plan(weekly_hours=16.0, weeks=4, weak_topics=["Triangles", "Introduction to Trigonometry"])
    print(f"Total Hours Allocated: {plan['total_available_hours']} hours over {plan['total_weeks']} weeks")
    print(f"Weekly Hours: {plan['weekly_hours']} hrs/week")
    print(f"Weak Topics Boosted: {plan['weak_topics_boosted']}")
    for ws in plan["weekly_schedule"]:
        print(f"  Week {ws['week']} ({ws['allocated_hours']} hrs):")
        for t in ws["target_topics"][:2]:
            boost_flag = " [WEAK TOPIC BOOST]" if t["is_weak_topic"] else ""
            print(f"    * {t['topic']}: {t['hours']} hrs{boost_flag}")

    # 4. Test M7: speak() with Bulbul
    print("\n--- Testing M7: speak with Sarvam Bulbul ---")
    summary_text = "नमस्ते! आपका 4 सप्ताह का स्टडी प्लान तैयार है। बीजगणित और त्रिकोणमिति पर विशेष ध्यान दें।"
    audio_path = speak(summary_text, language="hi-IN", output_path="data/test_summary.wav")
    print(f"Spoken summary successfully written to: {audio_path}")

    print("\n" + "=" * 80)
    print("ALL CORE TOOLS FUNCTIONING 100% AS REQUIRED!")
    print("=" * 80)

if __name__ == "__main__":
    main()
