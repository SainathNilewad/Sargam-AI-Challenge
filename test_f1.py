import os
import sys
import json
from dotenv import load_dotenv

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

from src.agent import ExamPrepAgent
import src.tools as tools

def main():
    print("=" * 80)
    print("TESTING MILESTONE F1: AGENT SEES REAL DATA & HONESTY VERIFICATION")
    print("=" * 80)

    agent = ExamPrepAgent(max_steps=8)

    # 1. Test Compact Output vs 200-char UI Trace preview
    raw_stats = tools.get_topic_stats()
    compact_json = agent._compact_tool_output(raw_stats)
    short_preview = (str(raw_stats)[:200] + "...") if len(str(raw_stats)) > 200 else str(raw_stats)

    print("\n[F1 Feature 1: Compact JSON Feed vs UI Trace Preview]")
    print(f"Original length: {len(str(raw_stats))} chars")
    print(f"Compact JSON length fed to model: {len(compact_json)} chars")
    print(f"UI Trace preview length: {len(short_preview)} chars")
    print(f"Compact JSON sample (first 160 chars):\n  {compact_json[:160]}...")
    print(f"UI Preview sample:\n  {short_preview[:160]}...")
    assert "chart_path" not in compact_json, "chart_path should be dropped in compact JSON"

    # 2. Test Honesty Verification Check
    print("\n[F1 Feature 2: Honesty Verification Engine]")
    agent.allowed_numbers = {16.0, 4.0, 64.0, 12.0, 6.3, 10.0, 1.0, 2.0, 3.0}
    agent.allowed_topics = {"Triangles", "Circles", "Arithmetic Progressions"}

    # Supported answer
    clean_answer = "You have 64 total study hours across 4 weeks (16 hours/week). You should focus on Triangles for 12 hours and Circles for 6.3 hours."
    unsupp_nums, unsupp_topics = agent._check_honesty(clean_answer)
    print(f"Test A (Clean Answer): Unsupported Nums: {unsupp_nums}, Topics: {unsupp_topics}")
    assert len(unsupp_nums) == 0 and len(unsupp_topics) == 0, "Clean answer should have 0 unsupported items"

    # Unsupported hallucinated answer
    hallucinated_answer = "You have 99 total study hours across 7 weeks. Focus on Calculus for 45 hours and Trigonometry for 28 hours."
    unsupp_nums_h, unsupp_topics_h = agent._check_honesty(hallucinated_answer)
    print(f"Test B (Hallucinated Answer): Detected Unsupported Nums: {unsupp_nums_h}")
    assert 99.0 in unsupp_nums_h and 45.0 in unsupp_nums_h, "Hallucinated numbers must be flagged"

    print("\nF1 Logic Unit Tests: ALL PASSED ✅")

if __name__ == "__main__":
    main()
