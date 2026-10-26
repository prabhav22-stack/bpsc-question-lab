# BPSC Question Lab · Version 2.0.0

An AI-powered, personal examination laboratory for **BPSC Combined Competitive Exam (CCE)** and **UPSC Civil Services Prelims**.

Combines official Google Gemini generative AI, deterministic examination analytics, metacognitive confidence calibration, interactive CBT simulation, adaptive spaced-repetition scheduling, and dual-mode persistence (Local SQLite + Cloud Supabase PostgreSQL).

---

## 🌟 Key Features in v2.0

1. **Dual-Mode Examination Engine & Interactive CBT Simulation:**
   - **Interactive CBT Mode / OMR Question Palette:** Step-by-step examination view with live question jump palette (Answered 🟢, Unanswered ⚪, Marked for Review 🟣), live countdown/elapsed timers, and optional Instant Answer Reveal in Study Mode.
   - **Classic Full Paper Scroll Mode:** Complete single-page test format for rapid offline-style mock drill.
   - Standard negative marking defaulting to authentic **-0.33 (1/3rd penalty)**.
   - Immediate **"Retry Missed / Skipped Questions"** action on test completion.

2. **Metacognitive Calibration & Guesswork Risk Analysis:**
   - Confidence levels (`High`, `Medium`, `Guess`) evaluated across post-test scorecards and dashboard.
   - **Blind Spot Alert:** Automatically pinpoints questions answered incorrectly despite marking `High` confidence.
   - **Guess Impact Telemetry:** Measures expected value per guess under negative marking rules to prevent negative penalty bleed.

3. **Complete 4-Option Context Preservation in AI Tutor & Diagnosis:**
   - Full option maps (`A` through `D`) are preserved across test sessions, Error Notebook, and the AI Study Tutor.
   - AI Tutor breaks down all four choices with distractors, analogies, mnemonics, or Socratic follow-up quiz questions.

4. **Dedicated Revision Vault & Saved Research Dossiers:**
   - **Pinned Questions Vault:** Dedicated tab in Error Notebook for drilling bookmarked questions with 1-click test launches.
   - **Saved Research Dossiers:** Stored policy analyses in Current Affairs Lab with instant 3-MCQ generation.
   - **Manual Question & Official PYQ Creator:** Add verified questions directly with complete exam provenance metadata.

5. **AI Question Studio & 10-Year PYQ RAG Retrieval:**
   - Calibrated against **101+ authentic BPSC Prelims questions** spanning the last 10 years (**60th through 70th CCE**, including 70th BPSC Prelims held in December 2024).
   - **10-Year Official PYQ Vault & Exam Browser**: Filter, inspect, and practice questions specifically by edition (70th, 69th, 68th, 67th, 66th, 65th, 64th, 63rd, 60-62nd).
   - Enhanced multi-keyword exemplar retrieval (up to 5 benchmarks) with side-by-side inspection drawers.
   - Interactive preview, distractor notes, and 1-click "Save & Practice This Set Now".

6. **Mock Questions Bank & Multimodal PDF OCR Extractor:**
   - **Dedicated Mock Questions Bank**: Browse, filter, search, and practice third-party test series questions and mock exams with distinct provenance tracking.
   - **Automated PDF Question Extraction**: Supports both digital OCR text PDFs and scanned image PDFs using Gemini 2.5 / 1.5 Multimodal Vision and `pypdf`.
   - **Deterministic Syllabus Subject Sorting**: Automatically sorts extracted questions into the 10 standard syllabus subjects (`Modern History`, `Ancient & Medieval History`, `Bihar Special`, `Geography`, `Indian Polity`, `Economy`, `General Science`, `Environment`, `Current Affairs`, `Other`).
   - **No Upload File Size Limit**: Configured for high-capacity files up to 2GB with streaming chunk processing.
   - **Direct Practice Drills**: Launch mock test simulation drills directly from the Mock Questions Bank or practice mode.

7. **Cloud-First Architecture & Dual Mode:**
   - Operates offline in local SQLite (`question_lab.db`).
   - GitHub Actions keep-alive workflow (`.github/workflows/keep_alive.yml`) to keep cloud instances active.
   - Seamlessly connects to Supabase PostgreSQL & Supabase Auth when configured.

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

Run all 47 tests (19 legacy regression tests + 24 v1.0 feature tests + 4 mock questions & PDF extractor tests):

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
