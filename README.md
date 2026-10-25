# 🎓 Exam Prep Agent (Powered by Sarvam AI)

An autonomous AI agent that reads real past exam question papers, mathematically models topic frequency and marks weightage, reviews low-confidence extractions, and generates a personalized, data-backed weekly study plan with multilingual audio playback via Sarvam Bulbul.

---

## 🌟 Key Features

1. **Autonomous Agent Loop (Not a Hardcoded Pipeline)**
   - Powered by **Sarvam-105B** (`sarvam-105b` chat completions in JSON mode).
   - Autonomous decision-making: at each step, the model chooses whether to call a tool, ask the student a clarifying question, or synthesize the final answer.
   - Enforces a strict **10-step execution limit**.
   - Full explainability: every step is recorded in a structured trace with tool name, inputs, outputs, and the model's 1-line rationale.

2. **Milestone 1: High-Accuracy Question Extraction**
   - Uses **Sarvam Vision 1.5** (`doc-ai/v1/job/digitise`).
   - Extracts CBSE question papers into structured database records (`paper`, `year`, `q_no`, `marks`, `text`, `confidence`, `evidence_source`).
   - Grounded evidence: tracks source down to `filename:page:question_number`.

3. **Milestone 2: Strict Syllabus Topic Tagging**
   - Tags questions strictly against the official CBSE Class 10 curriculum (or flags `"unclear"`).
   - Zero hallucinated topics.

4. **Milestone 3: Topic Frequency & Marks Weightage Modeling**
   - Strictly computed using **pandas** (the LLM never invents numbers):
     $$\text{Weightage \%} = \frac{\sum \text{Marks in Topic}}{\text{Total Marks Across Papers}} \times 100$$
     $$\text{Frequency \%} = \frac{\text{Question Count in Topic}}{\text{Total Question Count}} \times 100$$
   - Visualized using **Seaborn / Matplotlib** (`data/topic_weightage.png`).

5. **Milestone 4: Personalized Weekly Study Plan**
   - Proportional hour distribution preserving total study budget: $\sum \text{Allocated Hours} = \text{Weekly Hours} \times \text{Weeks}$.
   - Priority boost (+35%) for student's identified weak areas.
   - Week-by-week roadmap.

6. **Milestone 7: Multilingual Audio Summary**
   - Synthesizes natural spoken summaries in Hindi or English using **Sarvam Bulbul** (`bulbul:v4-flash`, speaker `shubh_enhi_ads`).

7. **Milestone 8: Quantitative Evaluation Suite**
   - **Part A**: 30 hand-labeled questions benchmark test set from official CBSE papers: **83.3% Accuracy**.
   - **Part B**: 10 autonomous agent behavioral test scenarios: **100% Pass Rate (10/10)**.

---

## 🏗️ Project Architecture

```
d:/sargam/
├── data/
│   ├── papers/                  # Official CBSE Class 10 Maths Papers (2020-2024)
│   ├── exam_papers.db           # SQLite database of extracted questions
│   ├── syllabus.json            # Official 14 CBSE Class 10 chapters
│   ├── test_set_draft.csv       # 30-question ground truth test set
│   ├── topic_weightage.png      # Seaborn weightage distribution chart
│   ├── evaluation_report.md     # Milestone 8 quantitative validation report
│   └── evaluation_report.json   # Milestone 8 raw metrics
├── src/
│   ├── sarvam_client.py         # Sarvam Vision, Sarvam-105B, Bulbul TTS client
│   ├── extractor.py             # Vision document intelligence parser
│   ├── tools.py                 # Core tools: extract, tag, stats, plan, speak
│   └── agent.py                 # Autonomous agent loop & step trace logger
├── app.py                       # High-end Streamlit web application
├── eval_suite.py                # Milestone 8 evaluation test runner
├── run_agent_cli.py             # Terminal agent runner
└── README.md
```

---

## 🚀 Quickstart

### 1. Requirements & Setup
Ensure dependencies are installed:
```bash
pip install sarvamai python-dotenv requests pandas matplotlib seaborn streamlit beautifulsoup4 pypdf
```

Set your API key in `.env`:
```ini
SARVAM_API_KEY=your_sarvam_api_key_here
```

### 2. Launch the Streamlit Web Application
```bash
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

### 3. Run the Evaluation Suite (M8)
```bash
python eval_suite.py
```

### 4. Run the Agent in Terminal (M5)
```bash
python run_agent_cli.py
```
