# BPSC Question Lab · Version 1.0.0

An AI-powered, personal examination laboratory for **BPSC Combined Competitive Exam (CCE)** and **UPSC Civil Services Prelims**.

Combines official Google Gemini generative AI, deterministic examination analytics, adaptive spaced-repetition scheduling, and dual-mode persistence (Local SQLite + Cloud Supabase PostgreSQL).

---

## 🌟 Key Features in v1.0

1. **AI Question Studio & RAG Exemplar Retrieval:**
   - Calibrated strictly against authentic **BPSC Prelims (68th, 69th, and 70th CCE)** and UPSC Prelims examination patterns.
   - **Few-Shot RAG Pipeline:** Automatically queries and injects authentic official BPSC PYQs from the database into the prompt to enforce high-rigor multi-statement formats, deep historical/geographic nuance, and sophisticated distractor traps.
   - Formats: Standard 4-option MCQs, Statement-based (1 and 2, 2 and 3), Chronology, Matching Columns, Assertion-Reason, and Bihar Special.
   - Interactive preview, distractor notes, and editing before saving to the question bank.
   - Distinctly labeled as practice questions (never falsified as official PYQs).

2. **AI Study Tutor:**
   - Pedagogical modes: First principles, BPSC exam-oriented summary, Option-by-option breakdown, Socratic hints without spoilers, Analogies, Comparison tables, and Timelines.
   - In-session conversation memory.

3. **Practice & Mock Examination Engine:**
   - Practice (untimed), Timed Drill (1 min/Q), and Full Mock Exams.
   - Configurable negative marking (`0.0`, `0.25`, `0.33` marks).
   - Per-question confidence rating (`High`, `Medium`, `Guess`).
   - "Explain My Mistake" action connecting directly to the AI Tutor.

4. **Deterministic Analytics & AI Performance Coach:**
   - Pure Python/SQL computation: Scores, accuracy rates, net scores, and weak area detection.
   - Transparent sample-size reliability indicators (`Preliminary n<5`, `Moderate 5-15`, `High 15+`).
   - Post-test diagnostic reports evaluating knowledge gaps, conceptual misunderstandings, and guessing patterns.

5. **Error Notebook:**
   - Systematic mistake classification (Knowledge gap, Conceptual confusion, Misread question, Incorrect elimination / guess, Careless error, Calculation error, Similar fact confusion, Other).
   - AI-assisted mistake diagnosis with suggested root cause.
   - Pin tricky questions to your personal revision notebook.
   - "Practice My Mistakes" drill for rapid remediation.

6. **Adaptive Revision Planner:**
   - Spaced-repetition scheduling based on empirical performance (SM-2 principles).
   - Customizable target exam date and daily revision budget.
   - Empirical retention tracking: Measures accuracy gains on retried topics.

7. **Current Affairs & Source Research:**
   - Verified topic research using Google Search grounding (where supported).
   - High-yield factual summaries, syllabus linkages, and Bihar-specific angles.

8. **Cloud-First Architecture & Dual Mode:**
   - Operates offline in local SQLite (`question_lab.db`).
   - Seamlessly connects to Supabase PostgreSQL & Supabase Auth when configured.
   - Built-in SQLite-to-Supabase migration without modifying local data.

---

## 🚀 Running on Windows

### Prerequisites
- Python 3.11 or newer (installed with "Add Python to PATH").

### Setup and Launch
In PowerShell or Command Prompt from this directory:

```powershell
# 1. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 2. Run the application
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Alternatively, double-click `start_windows.bat`.

The app will open automatically at `http://localhost:8501`.

---

## 🧪 Running the Automated Test Suite

Run all 43 tests (19 legacy regression tests + 24 v1.0 feature tests):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

All tests execute against in-memory SQLite instances and mocked AI services, requiring no network connection or paid API calls.

---

## 🔐 API Key & Secrets Configuration

All secrets are kept out of source files and Git history.

### Local Development
Configure `.streamlit/secrets.toml`:

```toml
# .streamlit/secrets.toml
GEMINI_API_KEY = "your-gemini-api-key-here"
GEMINI_MODEL = "gemini-3.5-flash-lite"

# Optional: Supabase Cloud credentials
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your-anon-public-key"
```

Alternatively, copy `.env.example` to `.env` in the project root.

> [!IMPORTANT]
> Never commit `.streamlit/secrets.toml` or `.env`. Both are included in `.gitignore`.

---

## ☁️ Cloud Deployment & Supabase Setup

### 1. Supabase PostgreSQL & Auth Setup
1. Create a project at [supabase.com](https://supabase.com).
2. Open the **SQL Editor** in your Supabase dashboard.
3. Paste and run the contents of [`migrations/001_initial_schema.sql`](file:///c:/Users/prabh/OneDrive/Documents/bpsc_question_lab_v0_1/migrations/001_initial_schema.sql).
4. Copy your project **URL** and **Anon Public Key** from `Project Settings > API`.
5. Enter them into `.streamlit/secrets.toml`.

### 2. Streamlit Community Cloud Deployment
1. Push your project to GitHub (ensure `.gitignore` excludes `question_lab.db`, `.env`, and `.streamlit/secrets.toml`).
2. Go to [share.streamlit.io](https://share.streamlit.io) and create a New App pointing to your repository and `app.py`.
3. In App Settings > **Secrets**, paste:
   ```toml
   GEMINI_API_KEY = "..."
   GEMINI_MODEL = "gemini-2.5-flash"
   SUPABASE_URL = "https://your-project.supabase.co"
   SUPABASE_ANON_KEY = "your-anon-key"
   ```
4. Deploy! Your app will now be available online with persistent cloud authentication.

---

## 💾 Local Backup & Disaster Recovery

- **Automated Backup:** Before updating schemas, a timestamped copy of source files and database is stored in `backups/`.
- **JSON Export:** Open **Settings & Data** in the app and click **Download Complete SQLite Database Snapshot (JSON)**.
- **CSV Export:** Download question bank and attempt history anytime from the **Question Bank** page.
