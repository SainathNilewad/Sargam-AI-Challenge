import os
import re
import json
import traceback
import pandas as pd
from typing import List, Dict, Any, Callable, Optional, Tuple, Set
from src.sarvam_client import SarvamClient
import src.tools as tools

class ExamPrepAgent:
    def __init__(self, sarvam_client: Optional[SarvamClient] = None, max_steps: int = 10):
        self.client = sarvam_client or SarvamClient()
        self.max_steps = max_steps
        self.trace: List[Dict[str, Any]] = []
        self.student_context: Dict[str, Any] = {}
        self.student_input_callback: Optional[Callable[[str], str]] = None
        self.history: List[Dict[str, str]] = []
        
        # Load official syllabus topics
        self.syllabus_topics: List[str] = []
        if os.path.exists("data/syllabus.json"):
            with open("data/syllabus.json", "r", encoding="utf-8") as f:
                self.syllabus_topics = json.load(f)

        # Allowed numbers and topics tracking for honesty verification
        self.allowed_numbers: Set[float] = {0.0, 100.0, 35.0, 2020.0, 2021.0, 2022.0, 2023.0, 2024.0}
        self.allowed_topics: Set[str] = set()
        
        # Register available tools
        self.tool_map = {
            "extract_paper": tools.extract_paper,
            "tag_questions": tools.tag_questions,
            "get_topic_stats": tools.get_topic_stats,
            "get_review_items": tools.get_review_items,
            "ask_student": tools.ask_student,
            "build_plan": tools.build_plan,
            "speak": tools.speak
        }

    def _compact_tool_output(self, data: Any) -> str:
        """
        Converts tool output into compact JSON:
        - Rounds float numbers to 1 decimal place.
        - Drops chart paths, file paths, image/audio binary outputs.
        - Truncates excessively long text fields (> 60 chars) to prevent token bloat.
        """
        def _compact(item: Any) -> Any:
            if isinstance(item, float):
                return round(item, 1)
            elif isinstance(item, dict):
                compact_dict = {}
                for k, v in item.items():
                    if k in ("chart_path", "image_path", "audio_file", "audio_path", "log_file", "output_path"):
                        continue
                    if k == "text" and isinstance(v, str) and len(v) > 60:
                        compact_dict[k] = v[:60] + "..."
                    else:
                        compact_dict[k] = _compact(v)
                return compact_dict
            elif isinstance(item, list):
                return [_compact(x) for x in item]
            elif isinstance(item, str) and len(item) > 250:
                return item[:250] + "..."
            return item

        compacted = _compact(data)
        if isinstance(compacted, (dict, list)):
            return json.dumps(compacted, separators=(',', ':'))
        return str(compacted)

    def _extract_numbers_from_obj(self, obj: Any) -> None:
        """Recursively extracts all numbers from an object and adds to allowed_numbers."""
        if isinstance(obj, (int, float)):
            self.allowed_numbers.add(round(float(obj), 1))
        elif isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(k, str) and k.replace('.', '', 1).isdigit():
                    try:
                        self.allowed_numbers.add(round(float(k), 1))
                    except ValueError:
                        pass
                self._extract_numbers_from_obj(v)
        elif isinstance(obj, (list, tuple, set)):
            for item in obj:
                self._extract_numbers_from_obj(item)

    def _extract_topics_from_obj(self, obj: Any) -> None:
        """Recursively extracts topic names from tool outputs."""
        if isinstance(obj, dict):
            if "topic" in obj and isinstance(obj["topic"], str):
                self.allowed_topics.add(obj["topic"])
            if "topics" in obj and isinstance(obj["topics"], dict):
                for t in obj["topics"].keys():
                    self.allowed_topics.add(t)
            if "topic_hours" in obj and isinstance(obj["topic_hours"], dict):
                for t in obj["topic_hours"].keys():
                    self.allowed_topics.add(t)
            if "weak_topics_boosted" in obj and isinstance(obj["weak_topics_boosted"], list):
                for t in obj["weak_topics_boosted"]:
                    self.allowed_topics.add(t)
            for v in obj.values():
                self._extract_topics_from_obj(v)
        elif isinstance(obj, list):
            for item in obj:
                self._extract_topics_from_obj(item)

    def _check_honesty(self, answer_text: str) -> Tuple[List[float], List[str]]:
        """
        Extracts numbers and syllabus topics from the answer and verifies
        they appear in tool outputs or student context.
        """
        # 1. Extract all numbers
        raw_numbers = re.findall(r'\b\d+(?:\.\d+)?\b', answer_text)
        unsupported_nums = []
        for num_str in raw_numbers:
            val = round(float(num_str), 1)
            # Check against allowed_numbers within 0.15 tolerance
            supported = any(abs(val - allowed) < 0.15 for allowed in self.allowed_numbers)
            if not supported:
                unsupported_nums.append(val)

        # 2. Extract topics mentioned
        unsupported_topics = []
        for topic in self.syllabus_topics:
            if topic.lower() in answer_text.lower():
                if topic not in self.allowed_topics:
                    unsupported_topics.append(topic)

        return unsupported_nums, unsupported_topics

    def _get_system_prompt(self) -> str:
        return f"""You are the autonomous "Exam Prep Agent" powered by Sarvam AI.
Your purpose: Help students prepare for their exams through data-backed study plans using real past papers and syllabus analysis.

AVAILABLE TOOLS:
1. extract_paper(file_path): Extracts questions from an exam paper using Sarvam Vision.
2. tag_questions(questions, syllabus): Tags questions with syllabus topics.
3. get_topic_stats(): Computes topic frequency %, marks weightage %, and trends using pandas.
4. get_review_items(): Retrieves questions with low confidence or unclear topics.
5. ask_student(question): Asks the student clarifying questions (weekly study hours, exam timeline, weak topics).
6. build_plan(weekly_hours, weeks, weak_topics): Builds a weekly study schedule based strictly on tool stats.
7. speak(text, language): Generates spoken audio summary via Sarvam Bulbul.

OFFICIAL SYLLABUS TOPICS:
{json.dumps(self.syllabus_topics)}

AVAILABLE PAST QUESTION PAPERS (in repository):
- data/papers/CBSE_Class10_Maths_2024.pdf
- data/papers/CBSE_Class10_Maths_2023.pdf
- data/papers/CBSE_Class10_Maths_2022.pdf
- data/papers/CBSE_Class10_Maths_2021.pdf
- data/papers/CBSE_Class10_Maths_2020.pdf

CRITICAL BEHAVIOUR RULES:
1. Autonomous Decision-Making: At every step, choose ONE action based on previous results.
2. Mandatory Checks:
   - Before building a study plan, you MUST know the student's weekly hours and exam date/weeks. If missing, use action 'ask_user' or call 'ask_student'.
   - NEVER give a final answer before get_topic_stats has been called.
   - If more than 20% of questions are "unclear", ask the student to confirm syllabus.
   - You may only explain numbers returned by tools. NEVER invent topics, marks, counts, or percentages.
3. Step Limit: You have at most 10 steps.
4. Response Format: Reply ONLY with valid JSON in one of these three formats:

Option A (Call a tool):
{{
  "action": "tool",
  "name": "<tool_name>",
  "input": {{ ... }},
  "reason": "<One-line explanation of why this tool was chosen>"
}}

Option B (Ask student a question):
{{
  "action": "ask_user",
  "question": "<Question to ask student>",
  "reason": "<One-line explanation of why this question is required>"
}}

Option C (Final answer once plan & stats are complete):
{{
  "action": "final",
  "answer": "<Comprehensive, data-backed study plan and explanation based only on tool numbers>",
  "reason": "Final answer completed"
}}
"""

    def run(self, user_goal: str, student_input_callback: Optional[Callable[[str], str]] = None) -> Dict[str, Any]:
        """
        Executes the agent loop until final answer is reached or max_steps is hit.
        """
        self.trace = []
        self.student_input_callback = student_input_callback
        stats_called = False
        plan_built = False
        
        # Reset allowed numbers & topics for this run
        self.allowed_numbers = {0.0, 100.0, 35.0, 2020.0, 2021.0, 2022.0, 2023.0, 2024.0}
        self.allowed_topics = set()
        
        # Add numbers from user goal
        for n in re.findall(r'\b\d+(?:\.\d+)?\b', user_goal):
            self.allowed_numbers.add(round(float(n), 1))
        
        system_prompt = self._get_system_prompt()
        self.history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Student Goal: {user_goal}"}
        ]

        print(f"\n[Agent] Starting run for goal: '{user_goal}' (Max steps: {self.max_steps})")

        for step in range(1, self.max_steps + 1):
            print(f"\n--- [Step {step}/{self.max_steps}] ---")
            
            # Request model decision
            try:
                decision = self.client.chat_completion(self.history, temperature=0.1, json_mode=True, max_retries=2)
            except Exception as e:
                print(f"[Agent Step {step}] Model call failed: {e}")
                self.trace.append({
                    "step": step,
                    "action": "error",
                    "error": str(e),
                    "reason": "Model communication failed"
                })
                break

            action = decision.get("action")
            reason = decision.get("reason", "No reason provided")

            # CASE A: CALL A TOOL
            if action == "tool":
                tool_name = decision.get("name")
                tool_input = decision.get("input", {})
                
                print(f"-> Model decided to call tool: '{tool_name}'")
                print(f"   Reason: {reason}")
                print(f"   Input: {tool_input}")

                if tool_name not in self.tool_map:
                    output = f"Error: Tool '{tool_name}' does not exist."
                else:
                    try:
                        tool_func = self.tool_map[tool_name]
                        # Handle tool execution
                        if tool_name == "get_topic_stats":
                            output = tool_func()
                            stats_called = True
                        elif tool_name == "get_review_items":
                            output = tool_func()
                        elif tool_name == "extract_paper":
                            file_p = tool_input.get("file_path", "data/papers/CBSE_Class10_Maths_2024.pdf")
                            output = tool_func(file_p)
                        elif tool_name == "tag_questions":
                            qs = tool_input.get("questions", [])
                            if not qs:
                                import sqlite3
                                conn = sqlite3.connect(tools.DB_PATH)
                                df_db = pd.read_sql("SELECT paper, year, q_no, marks, text, confidence, evidence_source FROM questions WHERE topic IS NULL LIMIT 20", conn)
                                conn.close()
                                qs = df_db.to_dict(orient="records")
                            output = tool_func(qs, self.syllabus_topics)
                        elif tool_name == "build_plan":
                            wh = float(tool_input.get("weekly_hours", self.student_context.get("weekly_hours", 15)))
                            wks = int(tool_input.get("weeks", self.student_context.get("weeks", 4)))
                            wt = tool_input.get("weak_topics", self.student_context.get("weak_topics", []))
                            output = tool_func(wh, wks, wt)
                            plan_built = True
                        elif tool_name == "speak":
                            txt = tool_input.get("text", "Here is your data-backed exam study plan.")
                            lang = tool_input.get("language", "hi-IN")
                            output = tool_func(txt, lang)
                        elif tool_name == "ask_student":
                            q_text = tool_input.get("question", "")
                            if self.student_input_callback:
                                ans = self.student_input_callback(q_text)
                            else:
                                ans = tools.ask_student(q_text, self.student_context)
                            output = {"question": q_text, "student_answer": ans}
                            # Store in context
                            ans_str = str(ans)
                            if "hour" in q_text.lower():
                                m = re.search(r'(\d+)', ans_str)
                                if m: 
                                    self.student_context["weekly_hours"] = float(m.group(1))
                                    self.allowed_numbers.add(float(m.group(1)))
                            if "week" in q_text.lower():
                                m = re.search(r'(\d+)', ans_str)
                                if m: 
                                    w_val = int(m.group(1))
                                    self.student_context["weeks"] = w_val
                                    self.allowed_numbers.add(float(w_val))
                                    for wi in range(1, w_val + 1):
                                        self.allowed_numbers.add(float(wi))
                        else:
                            output = tool_func(**tool_input)
                    except Exception as err:
                        output = f"Tool execution error: {err}\n{traceback.format_exc()}"

                # Extract allowed numbers and topics from real tool output
                self._extract_numbers_from_obj(output)
                self._extract_topics_from_obj(output)
                
                # Update total budget if hours & weeks are known
                if "weekly_hours" in self.student_context and "weeks" in self.student_context:
                    tot_budget = round(self.student_context["weekly_hours"] * self.student_context["weeks"], 1)
                    self.allowed_numbers.add(tot_budget)
                    for wi in range(1, int(self.student_context["weeks"]) + 1):
                        self.allowed_numbers.add(float(wi))

                # Format compact JSON for model observation (F1)
                compact_tool_json = self._compact_tool_output(output)

                # Format 200-char preview ONLY for the UI trace (F1)
                output_str = str(output)
                short_output = (output_str[:200] + "...") if len(output_str) > 200 else output_str

                self.trace.append({
                    "step": step,
                    "action": "tool",
                    "tool": tool_name,
                    "input": tool_input,
                    "output_preview": short_output,
                    "reason": reason
                })

                # Feed full compact JSON back to conversation history
                self.history.append({"role": "assistant", "content": json.dumps(decision)})
                self.history.append({"role": "user", "content": f"Tool '{tool_name}' returned: {compact_tool_json}"})

            # CASE B: ASK STUDENT A QUESTION
            elif action == "ask_user":
                question = decision.get("question", "")
                print(f"-> Model decided to ask student: '{question}'")
                print(f"   Reason: {reason}")
                
                if self.student_input_callback:
                    answer = self.student_input_callback(question)
                else:
                    answer = tools.ask_student(question, self.student_context)

                print(f"   Student replied: '{answer}'")
                
                # Context extraction & number registration
                ans_str = str(answer)
                for n in re.findall(r'\b\d+(?:\.\d+)?\b', ans_str):
                    self.allowed_numbers.add(round(float(n), 1))

                if "hour" in question.lower():
                    m = re.search(r'(\d+)', ans_str)
                    if m: 
                        self.student_context["weekly_hours"] = float(m.group(1))
                        self.allowed_numbers.add(float(m.group(1)))
                if "week" in question.lower() or "when" in question.lower() or "date" in question.lower():
                    m = re.search(r'(\d+)', ans_str)
                    if m: 
                        w_val = int(m.group(1))
                        self.student_context["weeks"] = w_val
                        self.allowed_numbers.add(float(w_val))
                        for wi in range(1, w_val + 1):
                            self.allowed_numbers.add(float(wi))

                if "weekly_hours" in self.student_context and "weeks" in self.student_context:
                    tot_budget = round(self.student_context["weekly_hours"] * self.student_context["weeks"], 1)
                    self.allowed_numbers.add(tot_budget)

                self.trace.append({
                    "step": step,
                    "action": "ask_user",
                    "question": question,
                    "answer": answer,
                    "reason": reason
                })

                self.history.append({"role": "assistant", "content": json.dumps(decision)})
                self.history.append({"role": "user", "content": f"Student Answer: {answer}"})

            # CASE C: FINAL ANSWER
            elif action == "final":
                final_answer = decision.get("answer", "")
                
                # Enforcement: Never give final answer before get_topic_stats has been called
                if not stats_called:
                    print("[Agent Safety Check]: Attempted final answer before get_topic_stats! Redirecting model.")
                    self.history.append({"role": "assistant", "content": json.dumps(decision)})
                    self.history.append({"role": "user", "content": "Rule Violation: You MUST call get_topic_stats() to get real data before providing the final answer."})
                    continue

                # Honesty Verification in code (F1)
                unsupported_nums, unsupported_topics = self._check_honesty(final_answer)
                
                if unsupported_nums or unsupported_topics:
                    print(f"\n[Agent Honesty Verification]: Unsupported items detected!")
                    print(f"  - Numbers: {unsupported_nums}")
                    print(f"  - Topics:  {unsupported_topics}")
                    
                    correction_prompt = (
                        f"HONESTY CORRECTION: Your final answer contained unsupported numbers or topics that were not returned by tools in this run:\n"
                        f"- Unsupported numbers: {unsupported_nums}\n"
                        f"- Unsupported topics: {unsupported_topics}\n"
                        f"- Allowed numbers from tool outputs: {sorted(list(self.allowed_numbers))}\n"
                        f"- Allowed topics from tool outputs: {sorted(list(self.allowed_topics))}\n\n"
                        f"Please revise your final answer to ONLY use these verified numbers and topics. Do not invent any values."
                    )
                    
                    self.history.append({"role": "assistant", "content": json.dumps(decision)})
                    self.history.append({"role": "user", "content": correction_prompt})
                    
                    try:
                        retry_dec = self.client.chat_completion(self.history, temperature=0.0, json_mode=True, max_retries=2)
                        revised_answer = retry_dec.get("answer", "")
                        if revised_answer:
                            final_answer = revised_answer
                    except Exception as e:
                        print(f"[Agent Honesty Retry]: Error in revision call: {e}")

                    # Re-check revised answer
                    still_unsupported_nums, still_unsupported_topics = self._check_honesty(final_answer)
                    if still_unsupported_nums or still_unsupported_topics:
                        print("[Agent Honesty Verification]: Still contains unverified numbers. Adding warning tag.")
                        warning = f"⚠️ [Unverified Numbers Warning: {still_unsupported_nums}]\n\n"
                        final_answer = warning + final_answer

                print(f"-> Model provided Final Answer!")
                print(f"   Reason: {reason}")
                self.trace.append({
                    "step": step,
                    "action": "final",
                    "answer": final_answer,
                    "reason": reason
                })
                
                return {
                    "status": "completed",
                    "steps_taken": step,
                    "final_answer": final_answer,
                    "trace": self.trace,
                    "context": self.student_context
                }

            else:
                self.history.append({"role": "user", "content": "Invalid response format. Must contain 'action': 'tool' | 'ask_user' | 'final'."})

        # Max steps reached without final
        print(f"[Agent] Hit maximum step limit of {self.max_steps} steps.")
        return {
            "status": "max_steps_exceeded",
            "steps_taken": self.max_steps,
            "final_answer": "Agent reached maximum step limit (10 steps) while executing workflow.",
            "trace": self.trace,
            "context": self.student_context
        }
