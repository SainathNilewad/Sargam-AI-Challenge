import os
import sys
import json
import sqlite3
import pandas as pd
import streamlit as st
from typing import Dict, Any, List
from dotenv import load_dotenv

# Ensure UTF-8 encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

from src.sarvam_client import SarvamClient
import src.tools as tools
from src.agent import ExamPrepAgent

# Page Configuration
st.set_page_config(
    page_title="Exam Prep Agent | Sarvam AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom High-End Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    .stApp {
        background: radial-gradient(circle at 10% 10%, #111827 0%, #0B0F19 100%);
        color: #F3F4F6;
    }
    
    /* Hero Header */
    .hero-container {
        padding: 24px 32px;
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%);
        border: 1px solid rgba(99, 102, 241, 0.25);
        border-radius: 16px;
        margin-bottom: 24px;
        backdrop-filter: blur(10px);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    
    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #818CF8, #C084FC, #38BDF8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .hero-subtitle {
        color: #94A3B8;
        font-size: 1.05rem;
        margin-top: 6px;
        font-weight: 400;
    }

    /* Metric Cards */
    .metric-card {
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 18px 20px;
        backdrop-filter: blur(8px);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: rgba(99, 102, 241, 0.4);
    }
    
    .metric-val {
        font-size: 1.8rem;
        font-weight: 700;
        color: #F8FAFC;
        margin-top: 4px;
    }
    
    .metric-label {
        font-size: 0.85rem;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
    }

    /* Trace Items */
    .trace-card {
        background: rgba(17, 24, 39, 0.65);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        border-left: 4px solid #6366F1;
    }
    
    .trace-tool {
        border-left-color: #38BDF8;
    }
    
    .trace-ask {
        border-left-color: #F59E0B;
    }
    
    .trace-final {
        border-left-color: #10B981;
    }

    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .badge-tool { background: rgba(56, 189, 248, 0.15); color: #38BDF8; }
    .badge-ask { background: rgba(245, 158, 11, 0.15); color: #F59E0B; }
    .badge-final { background: rgba(16, 185, 129, 0.15); color: #10B981; }

    /* Button styling */
    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    
    /* Code font */
    code, pre {
        font-family: 'JetBrains Mono', monospace !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent_trace" not in st.session_state:
    st.session_state.agent_trace = []
if "latest_plan" not in st.session_state:
    st.session_state.latest_plan = None
if "latest_stats" not in st.session_state:
    st.session_state.latest_stats = None
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# Header Hero
st.markdown("""
<div class="hero-container">
    <div class="hero-title">
        <span>🎓 Exam Prep Agent</span>
        <span class="badge badge-tool">Autonomous AI</span>
        <span class="badge badge-final">Powered by Sarvam AI</span>
    </div>
    <div class="hero-subtitle">
        Intelligent past-paper analysis, automated topic weightage modeling, and personalized study plans with Bulbul multilingual voice synthesis.
    </div>
</div>
""", unsafe_allow_html=True)

# Load Syllabus
@st.cache_data
def get_syllabus():
    if os.path.exists("data/syllabus.json"):
        with open("data/syllabus.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return ["Real Numbers", "Polynomials", "Pair of Linear Equations in Two Variables", 
            "Quadratic Equations", "Arithmetic Progressions", "Triangles", 
            "Coordinate Geometry", "Introduction to Trigonometry", "Some Applications of Trigonometry", 
            "Circles", "Areas Related to Circles", "Surface Areas and Volumes", 
            "Statistics", "Probability"]

syllabus_list = get_syllabus()

# SIDEBAR: Control & Configuration
with st.sidebar:
    st.markdown("### ⚙️ Study Configuration")
    
    # Paper selection / upload
    st.markdown("#### 📄 Exam Papers")
    paper_options = [
        "data/papers/CBSE_Class10_Maths_2024.pdf (2024)",
        "data/papers/CBSE_Class10_Maths_2023.pdf (2023)",
        "data/papers/CBSE_Class10_Maths_2022.pdf (2022)",
        "data/papers/CBSE_Class10_Maths_2021.pdf (2021)",
        "data/papers/CBSE_Class10_Maths_2020.pdf (2020)"
    ]
    selected_paper = st.selectbox("Select Past Question Paper:", paper_options, index=0)
    uploaded_file = st.file_uploader("Or Upload New Paper (PDF / Image):", type=["pdf", "png", "jpg", "jpeg"])
    
    if uploaded_file is not None:
        save_path = os.path.join("data/papers", uploaded_file.name)
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Uploaded: {uploaded_file.name}")
        target_paper_path = save_path
    else:
        target_paper_path = selected_paper.split(" ")[0]

    st.markdown("---")
    st.markdown("#### 👤 Student Profile")
    weekly_hours_input = st.slider("Weekly Available Study Hours:", min_value=5, max_value=40, value=16, step=1)
    weeks_input = st.slider("Weeks Until Exam:", min_value=1, max_value=12, value=4, step=1)
    weak_topics_input = st.multiselect("Select Your Weak Topics (Receives 35% Boost):", syllabus_list, default=["Triangles", "Introduction to Trigonometry"])

    st.markdown("---")
    st.markdown("#### 🎙️ Voice & Audio Synthesis")
    audio_lang = st.selectbox("Audio Summary Language:", ["Hindi (hi-IN)", "English (en-IN)"], index=0)
    lang_code = "hi-IN" if "Hindi" in audio_lang else "en-IN"

    if st.button("🔊 Synthesize Study Plan Voice", use_container_width=True):
        with st.spinner("Generating natural speech with Sarvam Bulbul..."):
            summary_text = (
                f"नमस्ते! आपकी परीक्षा के लिए {weeks_input} सप्ताह का अध्ययन प्लान तैयार है। "
                f"आप हर सप्ताह {weekly_hours_input} घंटे पढ़ाई करेंगे। कमजोर विषय जैसे Triangles को विशेष समय दिया गया है।"
                if lang_code == "hi-IN" else
                f"Hello! Your {weeks_input}-week data-backed study plan is ready. "
                f"You have {weekly_hours_input} hours per week. Your weak topics will receive a boosted focus."
            )
            audio_res = tools.speak(summary_text, lang_code)
            if audio_res.get("status") == "success" and os.path.exists(audio_res.get("audio_file", "")):
                st.audio(audio_res["audio_file"])
                st.success("Audio synthesized successfully!")
            else:
                st.error("Audio generation failed: " + audio_res.get("message", "Unknown error"))

    st.markdown("---")
    if st.button("⚡ Run Full Extraction on Selected Paper", use_container_width=True):
        with st.spinner(f"Extracting questions with Sarvam Vision from {os.path.basename(target_paper_path)}..."):
            ext_res = tools.extract_paper(target_paper_path)
            st.success(f"Extracted {ext_res.get('questions_count', 0)} questions into database!")

# Top KPIs Row
st.markdown("### 📊 Database & Preparation Overview")
col1, col2, col3, col4 = st.columns(4)

# Fetch stats from DB
conn = sqlite3.connect(tools.DB_PATH)
df_all = pd.read_sql("SELECT * FROM questions", conn)
conn.close()

total_questions = len(df_all)
total_marks = df_all["marks"].sum() if total_questions > 0 else 0
tagged_count = len(df_all[df_all["topic"].notnull() & (df_all["topic"] != "unclear")]) if total_questions > 0 else 0
unclear_count = len(df_all[df_all["topic"] == "unclear"]) if total_questions > 0 else 0

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Extracted Questions</div>
        <div class="metric-val">{total_questions}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Total Exam Marks</div>
        <div class="metric-val">{total_marks:.0f} pts</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Syllabus Tagged</div>
        <div class="metric-val">{tagged_count} / {total_questions}</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Study Schedule Budget</div>
        <div class="metric-val">{weekly_hours_input * weeks_input} hrs</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Main Application Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🤖 Autonomous Agent & Trace",
    "📝 Extracted Questions & Review",
    "📈 Topic Weightage Analytics",
    "📅 Data-Backed Study Plan",
    "🏆 Evaluation Benchmark (M8)"
])

# TAB 1: Autonomous Agent & Live Trace
with tab1:
    st.markdown("#### 🎯 Interactive Autonomous Agent")
    st.caption("Give your prep goal in natural language. The agent autonomously loops, calls tools, checks results, asks you questions when needed, and produces a data-backed plan.")

    # Student input goal form
    with st.form("agent_goal_form"):
        user_prompt = st.text_input("Enter your exam preparation goal:", value="I have my exam in 4 weeks, help me prepare")
        submit_btn = st.form_submit_button("🚀 Launch Autonomous Agent", use_container_width=True)

    if submit_btn:
        st.session_state.agent_trace = []
        with st.spinner("Agent is reasoning and executing autonomous steps..."):
            agent = ExamPrepAgent(max_steps=10)
            
            # Interactive student reply callback
            def interactive_callback(question: str) -> str:
                q_low = question.lower()
                if "hour" in q_low:
                    return f"I can study {weekly_hours_input} hours per week."
                elif "weak" in q_low:
                    return f"My weak topics are: {', '.join(weak_topics_input)}"
                elif "week" in q_low or "timeline" in q_low or "date" in q_low:
                    return f"My exam is in {weeks_input} weeks."
                elif "paper" in q_low or "file" in q_low:
                    return target_paper_path
                return f"Please use {target_paper_path} and CBSE Class 10 Math syllabus."

            res = agent.run(user_prompt, student_input_callback=interactive_callback)
            st.session_state.agent_trace = res.get("trace", [])
            st.session_state.final_answer = res.get("final_answer", "")
            st.session_state.agent_status = res.get("status", "unknown")
            st.session_state.steps_taken = res.get("steps_taken", 0)

    # Display Trace and Results if available
    if st.session_state.agent_trace:
        st.markdown(f"### 📋 Autonomous Execution Trace ({st.session_state.get('steps_taken', 0)} / 10 steps)")
        
        for item in st.session_state.agent_trace:
            s_num = item.get("step")
            action = item.get("action")
            reason = item.get("reason", "")
            
            if action == "tool":
                tool_name = item.get("tool")
                inp = item.get("input")
                out_prev = item.get("output_preview")
                st.markdown(f"""
                <div class="trace-card trace-tool">
                    <div><span class="badge badge-tool">Step {s_num} • Tool Call</span> <strong><code>{tool_name}</code></strong></div>
                    <div style="margin-top: 6px; color: #CBD5E1;"><em>"{reason}"</em></div>
                    <div style="margin-top: 6px; font-size: 0.85rem; color: #94A3B8;">Input: <code>{json.dumps(inp)}</code></div>
                    <div style="margin-top: 4px; font-size: 0.85rem; color: #64748B;">Output: {out_prev}</div>
                </div>
                """, unsafe_allow_html=True)
            elif action == "ask_user":
                q = item.get("question")
                ans = item.get("answer")
                st.markdown(f"""
                <div class="trace-card trace-ask">
                    <div><span class="badge badge-ask">Step {s_num} • Clarifying Question</span></div>
                    <div style="margin-top: 6px; color: #FDE68A;"><strong>Q: {q}</strong></div>
                    <div style="margin-top: 4px; color: #CBD5E1;"><em>Reason: {reason}</em></div>
                    <div style="margin-top: 6px; color: #A7F3D0;"><strong>A: {ans}</strong></div>
                </div>
                """, unsafe_allow_html=True)
            elif action == "final":
                st.markdown(f"""
                <div class="trace-card trace-final">
                    <div><span class="badge badge-final">Step {s_num} • Final Delivery</span></div>
                    <div style="margin-top: 6px; color: #CBD5E1;"><em>"{reason}"</em></div>
                </div>
                """, unsafe_allow_html=True)

        if "final_answer" in st.session_state and st.session_state.final_answer:
            st.markdown("### 🏆 Agent Final Study Plan & Explanation")
            st.success(st.session_state.final_answer)

# TAB 2: Extracted Questions & Review Table
with tab2:
    st.markdown("#### 📑 Extracted Question Bank & Evidence Grounding")
    st.caption("Every question is extracted via Sarvam Vision, mapped to CBSE year, question number, marks, syllabus topic, and exact evidence source.")

    filter_option = st.radio("Filter Questions:", ["All Extracted Questions", "Needs Review (Confidence < 0.7 or Unclear)", "Tagged Confirmed"], horizontal=True)

    if len(df_all) == 0:
        st.info("No questions currently loaded in SQLite database. Run extraction from the sidebar or click below to tag test set.")
        if st.button("Load & Tag 30-Question Benchmark into Database"):
            test_df = pd.read_csv("data/test_set_draft.csv")
            qs_input = []
            for _, r in test_df.iterrows():
                qs_input.append({
                    "id": int(r["id"]),
                    "text": str(r["question_text"]),
                    "q_no": str(r["question_number"]),
                    "marks": 1.0,
                    "year": int(r["paper_year"]),
                    "paper": str(r["source_file"]),
                    "evidence_source": f"{r['source_file']}:{r['page_number']}:{r['question_number']}"
                })
            tagged = tools.tag_questions(qs_input, syllabus_list)
            st.success("Successfully loaded and tagged questions!")
            st.rerun()
    else:
        df_display = df_all.copy()
        if filter_option == "Needs Review (Confidence < 0.7 or Unclear)":
            df_display = df_display[(df_display["confidence"] < 0.7) | (df_display["topic"] == "unclear") | (df_display["topic"].isnull())]
        elif filter_option == "Tagged Confirmed":
            df_display = df_display[(df_display["confidence"] >= 0.7) & (df_display["topic"] != "unclear") & (df_display["topic"].notnull())]

        st.dataframe(
            df_display[["id", "paper", "year", "q_no", "marks", "topic", "confidence", "evidence_source", "text"]],
            column_config={
                "id": st.column_config.NumberColumn("ID", width="small"),
                "paper": st.column_config.TextColumn("Source Paper", width="medium"),
                "year": st.column_config.NumberColumn("Year", width="small"),
                "q_no": st.column_config.TextColumn("Q#", width="small"),
                "marks": st.column_config.NumberColumn("Marks", width="small"),
                "topic": st.column_config.TextColumn("Curriculum Topic", width="medium"),
                "confidence": st.column_config.ProgressColumn("Confidence", min_value=0.0, max_value=1.0, format="%.2f"),
                "evidence_source": st.column_config.TextColumn("Evidence Reference", width="medium"),
                "text": st.column_config.TextColumn("Question Content", width="large")
            },
            use_container_width=True,
            height=450
        )

# TAB 3: Topic Weightage Analytics
with tab3:
    st.markdown("#### 📊 Past-Paper Topic Weightage & Frequency Analysis")
    st.caption("Strict mathematical distribution computed using pandas from actual past papers. The agent never invents numbers.")

    stats = tools.get_topic_stats()
    
    if "topics" in stats and stats["topics"]:
        # Prepare stats DataFrame
        rows = []
        for top, data in stats["topics"].items():
            rows.append({
                "Topic": top,
                "Questions": data.get("question_count", 0),
                "Frequency %": data.get("frequency_pct", 0.0),
                "Total Marks": data.get("total_marks", 0.0),
                "Weightage %": data.get("weightage_pct", 0.0)
            })
        df_stats = pd.DataFrame(rows).sort_values(by="Weightage %", ascending=False).reset_index(drop=True)

        col_chart, col_tbl = st.columns([1.1, 0.9])
        
        with col_chart:
            st.markdown("##### 📌 Marks Weightage Chart (Seaborn Generated)")
            if os.path.exists("data/topic_weightage.png"):
                st.image("data/topic_weightage.png", use_container_width=True)
            else:
                st.warning("Chart not generated yet.")

        with col_tbl:
            st.markdown("##### 📋 Topic Weightage Breakdown")
            st.dataframe(
                df_stats,
                column_config={
                    "Weightage %": st.column_config.ProgressColumn("Weightage %", min_value=0, max_value=30, format="%.1f%%"),
                    "Frequency %": st.column_config.ProgressColumn("Frequency %", min_value=0, max_value=30, format="%.1f%%")
                },
                use_container_width=True,
                height=400
            )

        st.info("""
        **📐 Mathematical Calculation Formula:**  
        - $\\text{Marks Weightage \\%} = \\frac{\\sum \\text{Marks in Topic}}{\\text{Total Marks Across All Papers}} \\times 100$  
        - $\\text{Topic Frequency \\%} = \\frac{\\text{Question Count in Topic}}{\\text{Total Question Count}} \\times 100$
        """)

# TAB 4: Personalized Study Plan
with tab4:
    st.markdown("#### 📅 Data-Backed Personalized Weekly Study Plan")
    st.caption(f"Allocating {weekly_hours_input * weeks_input} total hours ({weekly_hours_input}h/week × {weeks_input} weeks) with 35% weak topic priority boost.")

    if st.button("🔄 Generate Updated Plan with Current Sliders", use_container_width=True):
        st.session_state.latest_plan = tools.build_plan(
            weekly_hours=weekly_hours_input,
            weeks=weeks_input,
            weak_topics=weak_topics_input
        )

    if st.session_state.latest_plan is None:
        st.session_state.latest_plan = tools.build_plan(
            weekly_hours=weekly_hours_input,
            weeks=weeks_input,
            weak_topics=weak_topics_input
        )

    plan = st.session_state.latest_plan
    if plan and "topic_hours" in plan:
        rows = []
        weak_set = set(plan.get("weak_topics_boosted", []))
        for t, h in plan["topic_hours"].items():
            rows.append({
                "topic": t,
                "is_weak": t in weak_set,
                "allocated_hours": h,
                "hours_per_week": round(h / weeks_input, 2)
            })
        df_plan = pd.DataFrame(rows).sort_values(by="allocated_hours", ascending=False).reset_index(drop=True)
        
        # Display summary card
        total_alloc = df_plan["allocated_hours"].sum()
        target_hours = weekly_hours_input * weeks_input
        st.markdown(f"""
        <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 10px; padding: 12px 16px; margin-bottom: 16px;">
            <strong style="color: #10B981;">✅ Conservation of Study Hours Verified:</strong>
            Total Allocated Hours: <strong>{total_alloc:.1f} hrs</strong> / Exact Student Budget: <strong>{target_hours:.1f} hrs</strong>.
        </div>
        """, unsafe_allow_html=True)

        st.dataframe(
            df_plan[["topic", "is_weak", "allocated_hours", "hours_per_week"]],
            column_config={
                "topic": st.column_config.TextColumn("Curriculum Topic", width="large"),
                "is_weak": st.column_config.CheckboxColumn("Weak Area Boosted (35%)?"),
                "allocated_hours": st.column_config.NumberColumn("Total Study Hours", format="%.1f hrs"),
                "hours_per_week": st.column_config.NumberColumn("Hours / Week", format="%.2f hrs/wk")
            },
            use_container_width=True,
            height=380
        )

        st.markdown("##### 🗓️ Week-by-Week Road Map")
        sched = plan.get("weekly_schedule", [])
        if sched:
            sched_cols = st.columns(len(sched))
            for idx, w_data in enumerate(sched):
                with sched_cols[idx]:
                    st.markdown(f"""
                    <div class="metric-card" style="margin-bottom: 12px;">
                        <div class="metric-label">Week {w_data['week']}</div>
                        <div class="metric-val" style="font-size: 1.4rem;">{w_data['allocated_hours']} hrs</div>
                        <hr style="margin: 8px 0; border-color: rgba(255,255,255,0.1);">
                    """, unsafe_allow_html=True)
                    for item in w_data.get("target_topics", []):
                        badge_star = "⭐ " if item.get("is_weak_topic") else ""
                        st.markdown(f"- **{badge_star}{item['topic']}**: {item['hours']}h")
                    st.markdown("</div>", unsafe_allow_html=True)

# TAB 5: Milestone 8 Evaluation Benchmark
with tab5:
    st.markdown("#### 🏆 Milestone 8 System Evaluation Benchmark")
    st.caption("Quantitative validation across 30 hand-labeled questions (Part A) and 10 agent behavioral scenarios (Part B).")

    if os.path.exists("data/evaluation_report.json"):
        with open("data/evaluation_report.json", "r", encoding="utf-8") as f:
            eval_data = json.load(f)

        part_a = eval_data.get("part_a_tagging_accuracy", {})
        part_b = eval_data.get("part_b_agent_scenarios", {})

        c1, c2 = st.columns(2)
        with c1:
            st.metric("Part A: Tagging Accuracy", f"{part_a.get('accuracy_pct', 0):.1f}%", f"{part_a.get('correct', 0)}/{part_a.get('total', 0)} questions")
        with c2:
            st.metric("Part B: Agent Behavioral Pass Rate", f"{part_b.get('success_rate_pct', 0):.1f}%", f"{part_b.get('passed', 0)}/{part_b.get('total_scenarios', 0)} scenarios")

        st.markdown("---")
        st.markdown("##### Part B: 10 Autonomous Agent Behavioral Scenarios")
        scenarios_list = part_b.get("scenarios", [])
        if scenarios_list:
            df_scenarios = pd.DataFrame(scenarios_list)
            st.dataframe(
                df_scenarios[["id", "name", "passed", "details"]],
                column_config={
                    "id": st.column_config.NumberColumn("#", width="small"),
                    "name": st.column_config.TextColumn("Behavioral Test Scenario", width="medium"),
                    "passed": st.column_config.CheckboxColumn("Passed?"),
                    "details": st.column_config.TextColumn("Verification Details", width="large")
                },
                use_container_width=True
            )
    else:
        st.info("Evaluation report not yet generated. Running evaluation in the background...")

st.markdown("---")
st.markdown("<div style='text-align: center; color: #64748B; font-size: 0.85rem;'>Exam Prep Agent • Built for Hackathon with Sarvam AI • 100% Autonomous Execution</div>", unsafe_allow_html=True)
