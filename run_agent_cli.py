import os
import sys
import json
from dotenv import load_dotenv

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

from src.agent import ExamPrepAgent

def main():
    print("=" * 85)
    print("MILESTONE 5 (M5): AUTONOMOUS AGENT LOOP TEST IN TERMINAL")
    print("=" * 85)

    goal = "I have my exam in 4 weeks, help me prepare"
    print(f"Student Goal: '{goal}'\n")

    agent = ExamPrepAgent(max_steps=10)

    # Provide realistic interactive answers when agent asks the student
    def student_callback(question: str) -> str:
        q_low = question.lower()
        if "hour" in q_low:
            return "I can study 16 hours per week."
        elif "weak" in q_low:
            return "My weak topics are Triangles and Introduction to Trigonometry."
        elif "file" in q_low or "path" in q_low or "paper" in q_low:
            return "data/papers/CBSE_Class10_Maths_2024.pdf"
        elif "week" in q_low or "exam" in q_low:
            return "My exam is in 4 weeks."
        return "Please use the CBSE Class 10 Mathematics Standard past papers in data/papers/."

    result = agent.run(goal, student_input_callback=student_callback)

    print("\n" + "=" * 85)
    print("AGENT EXECUTION TRACE LOG (Step-by-Step)")
    print("=" * 85)
    
    for item in result.get("trace", []):
        step_no = item.get("step")
        action = item.get("action")
        reason = item.get("reason", "")
        
        if action == "tool":
            print(f"[Step {step_no} | Tool Call]: '{item.get('tool')}'")
            print(f"  Reason: {reason}")
            print(f"  Input:  {json.dumps(item.get('input'))}")
            print(f"  Output: {item.get('output_preview')[:120]}...\n")
        elif action == "ask_user":
            print(f"[Step {step_no} | Ask Student]: \"{item.get('question')}\"")
            print(f"  Reason: {reason}")
            print(f"  Student Reply: \"{item.get('answer')}\"\n")
        elif action == "final":
            print(f"[Step {step_no} | Final Output]: Answer Delivered")
            print(f"  Reason: {reason}\n")

    print("=" * 85)
    print(f"TOTAL STEPS TAKEN: {result.get('steps_taken')}/10 | STATUS: {result.get('status')}")
    print("=" * 85)
    print("\nFINAL AGENT ANSWER:\n")
    print(result.get("final_answer"))
    print("\n" + "=" * 85)

    # Save trace to data/agent_trace.json
    with open("data/agent_trace.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print("Trace log saved to: data/agent_trace.json")

if __name__ == "__main__":
    main()
