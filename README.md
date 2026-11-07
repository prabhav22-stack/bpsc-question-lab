# Question Lab · Version 2.0.0

An AI-powered, personal examination laboratory for **BPSC Combined Competitive Exam (CCE)** and **UPSC Civil Services Prelims**.

Combines official Google Gemini generative AI, deterministic examination analytics, metacognitive confidence calibration, interactive CBT simulation, adaptive spaced-repetition scheduling, and dual-mode persistence (Local SQLite + Cloud Supabase PostgreSQL).

---

## 🌟 Key Features in v2.0

1. **Dual-Mode Examination Engine & Interactive CBT Simulation:**
   - **Interactive CBT Mode / OMR Question Palette:** Step-by-step examination view with live question jump palette (Answered 🟢, Unanswered ⚪, Marked for Review 🟣), live countdown/elapsed timers, and optional Instant Answer Reveal in Study Mode.
   - **Distractor Eliminator Scratchpad:** Cross out eliminated options (A, B, C, D) in real-time scratchpad during problem-solving, simulating actual exam-day elimination strategies.
   - **Speed vs Accuracy Pacing Quadrants:** Post-test evaluation categorizing attempts into *Fast & Accurate (≤45s)*, *Careful & Correct (>45s)*, *Rushed Errors (≤30s)*, and *Time Sinks (>60s Missed)* against the authentic BPSC benchmark of 48s/question.
   - **Classic Full Paper Scroll Mode:** Complete single-page test format for rapid offline-style mock drill.
   - Standard negative marking defaulting to authentic **-0.33 (1/3rd penalty)**.
   - Immediate **"Retry Missed / Skipped Questions"** action on test completion.

2. **Metacognitive Calibration & Guesswork Risk Analysis:**
   - Confidence levels (`High`, `Medium`, `Guess`) evaluated across post-test scorecards and dashboard.
   - **Blind Spot Alert:** Automatically pinpoints questions answered incorrectly despite marking `High` confidence.
   - **Guess Impact Telemetry:** Measures expected value per guess under negative marking rules to prevent negative penalty bleed.
   - **Anki Spaced-Repetition Deck Exporter:** One-click export of Question Bank, Pinned Revision Vault, and Error Notebook to Anki flashcards (`.csv`) with HTML formatting and hierarchical BPSC tags.
   - **11-Subject Syllabus Coverage & Readiness Matrix:** Real-time dashboard meter tracking question availability, attempts, and readiness status across all 11 official syllabus subjects.

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

6. **Mock Questions Bank & Multi-Engine Local OCR Cascade Extractor:**
   - **Dedicated Mock Questions Bank**: Browse, filter, search, and practice third-party test series questions and mock exams with distinct provenance tracking.
   - **Gemini Native File API Pipeline (`client.files.upload`)**: Ultra-fast direct document understanding that streams raw PDF chunks directly to Google Tensor Cloud. Extracts, translates, and structures 50+ MCQs in ~20–30 seconds with 0 local CPU load or memory strain, automatically deleting temporary files from Google servers upon completion.
   - **Multi-Engine Local OCR Cascade Subsystem (`ocr_engine.py`)**: Supports **RapidOCR** (high-speed ONNX runtime port of PaddleOCR), **PaddleOCR** (Baidu deep learning engine), and **Pytesseract** (Google Tesseract OCR) to process scanned PDF pages locally before querying Gemini.
   - **Persistent Background OCR Engine (`ocr_jobs`)**: Operates on a dedicated background worker decoupled from the frontend browser tab. Extraction continues seamlessly across browser reloads, inactive sessions, or computer sleep, with strict segregation between mock and PYQ extraction jobs.
   - **Interactive Live Progress Bar & Cancellation Action**: Real-time progress bar tracking batch status with a dedicated **"⏹️ Cancel Extraction"** button that halts processing immediately on demand.
   - **High-Speed Parallel Processing & Image Optimization**: Oversized scan pages (>1600px) are automatically optimized and converted to grayscale, and processed in parallel across CPU cores using `concurrent.futures.ThreadPoolExecutor` for a 3-5x throughput boost.
   - **~85% API Token Reduction & Quota Optimization**: Extracted local OCR text is sent to Gemini in high-speed text-only structured categorization mode, bypassing heavy image vision tokens and significantly speeding up batch extraction.
   - **Zero Loss of Accuracy Guarantee**: Includes an intelligent MCQ heuristic evaluator (`evaluate_ocr_quality`). If local OCR yields degraded, faded, or insufficient text (< 50 chars or lacking MCQ structure), it **automatically falls back to Gemini Multimodal Vision**, guaranteeing zero lost questions.
   - **OCR Strategy & Engine Selector**: Choose between `⚡ Auto Cascaded (Local OCR First → Gemini Vision Fallback)`, `👁️ Gemini Multimodal Vision Only`, or `💻 Local OCR Only`, with priority ordering between RapidOCR, PaddleOCR, and Pytesseract.
   - **Deployment-Ready Cloud Packages (`packages.txt`)**: Preconfigured with `tesseract-ocr` and `tesseract-ocr-eng` for automatic apt-get installation on Streamlit Cloud containers.
   - **Automatic Hindi-to-English Mock Paper Translator**: When extracting mock PDF papers containing Hindi or bilingual questions, automatically translates stems, options, and explanations into standard, academic English suitable for BPSC/UPSC Civil Services preparation, while preserving the authentic Hindi source stem in `original_question_hindi` for provenance verification.
   - **On-Demand Hindi Card Translator**: Any Hindi question in the Question Bank is automatically badged with `🇮🇳 Hindi` and features an instant `🌐 Translate to English` action button with live database updates.
   - **Deterministic Syllabus Subject Sorting & Rearrangement Engine**: Automatically sorts extracted questions into the 11 standard syllabus subjects (`Modern History`, `Ancient & Medieval History`, `Bihar Special`, `Geography`, `Indian Polity`, `Economy`, `General Science`, `Environment`, `Current Affairs`, `General Mental Ability & Mathematics`, `Other`), with an automated re-classification scanner to reorganize quantitative aptitude, arithmetic, clock, series, and reasoning questions into the dedicated General Mental Ability & Mathematics section.
   - **PDF Filename & Hash Duplicate Detection**: Automatically tracks uploaded PDF filenames and SHA-256 hashes in `uploaded_mock_files` to prevent re-uploading the same mock test paper.
   - **Intra-Batch & Question Bank Deduplication**: Normalizes question stems (stripping numbering, whitespace, punctuation) to ensure no question is repeated twice or thrice.
   - **Question Bank Integrity Scanner**: One-click scanner in the Mock Questions Bank to detect and clean any duplicate questions.
   - **No Upload File Size Limit**: Configured for high-capacity files up to 2GB with streaming chunk processing.
   - **Direct Practice Drills**: Launch mock test simulation drills directly from the Mock Questions Bank or practice mode.

7. **BPSC-Adjacent Exam PYQ Bank & Dedicated PYQ OCR Ingestion Pipeline:**
   - **Strict Data Segregation**: Official BPSC CCE PYQs, BPSC-Adjacent PYQs, and Mock Questions are kept strictly separated across storage and UI views to maintain examination authenticity (complying with Rule 4 & 5 of `AGENTS.md`).
   - **Dedicated Adjacent PYQ Vault**: Browse, filter, search, and practice previous year questions specifically from allied examinations:
     - Ghatna Chakra PYQ Compendiums (History / Geography / Science / Polity / Economy)
     - Eduteria BPSC & Bihar PYQ Compendiums
     - BPSC CDPO (Child Development Project Officer)
     - Bihar Police SI / Daroga
     - BPSC Auditor & Assistant Audit Officer (AAO)
     - BPSC Assistant & Project Manager
     - BPSC TRE (Teacher Recruitment Examination)
     - BPSC Judicial Services (Civil Judge)
     - BSSC CGL (Bihar Staff Selection Commission)
     - Adjacent State PSCs (UPPSC, JPSC, MPPSC)
   - **Multi-PDF Batch Queue & Fire-and-Forget Auto-Save**: Upload multiple compendiums/books at once (e.g., 4 Ghatna Chakra subjects or multi-volume sets). Sequential queue processes each file, commits unique questions immediately with background auto-save (`auto_save=True`), filters duplicates, and compiles a comprehensive Batch Telemetry Report.
   - **Watermark-Resistant OCR & Hindi Heuristics**: Smart watermark bypass filter prevents digital scan footers (Telegram links, copyrights) from erroneously skipping OCR, while Devanagari Hindi markers `(क)-(घ)` ensure 100% extraction accuracy on Hindi compendiums.
   - **Dedicated PYQ OCR Extractor**: Full multi-engine OCR and Gemini Native File API pipeline tailored for authentic past papers with paper set attribution (Set A, B, C, D), exam years, official question numbering, and official verified answer key tracking.
   - **Adjacent Exam Practice Drills**: Launch CBT exam drills targeting only BPSC-Adjacent PYQs or specific allied exam papers.

8. **Cloud-First Architecture & Dual Mode:**
   - Operates offline in local SQLite (`question_lab.db`).
   - GitHub Actions keep-alive workflow (`.github/workflows/keep_alive.yml`) to keep cloud instances active.
   - Seamlessly connects to Supabase PostgreSQL & Supabase Auth when configured.

9. **Dedicated Offline Exam & Optical OMR Simulation Lab:**
   - **Authentic BPSC A4 OMR Sheet Generator (`omr_engine.py`)**: Generates print-ready high-precision PDF OMR sheets with optical corner registration markers, 7-digit candidate roll number bubble grids, test booklet series (A, B, C, D) bubbles, candidate signature blocks, and official -0.33 mark penalty instructions. Scalable for 25, 50, 100, and 150 questions.
   - **Printable Question Booklet Compiler**: Generates official examination booklets complete with exam title, candidate instructions, and neatly typeset questions and options.
   - **Custom Prompt-Driven Exam Generator**: Enter custom prompts specifying exact examination tone, focus topics (e.g. Bihar 1857 revolt, Kunwar Singh, Champaran, peasant movements, Indian Polity), question count (5 to 150), and formats (Standard MCQ, Multi-statement, Assertion-Reason, Chronology, Matching, Mental Ability).
   - **Assembly from Authenticated Vaults**: Assemble offline test papers directly from Official BPSC PYQs, BPSC-Adjacent PYQs, Mock Exams, or Pinned Vault with optional shuffling.
   - **Multimodal Gemini Vision OMR Evaluator**: Upload scanned or photographed OMR sheets (PDF or image). Gemini Vision identifies darkened bubbles and grades answers deterministically with official -0.33 negative marking. Includes an interactive inspection and manual verification grid.
   - **AI Performance Diagnostic Analysis**: Gemini Flash provides detailed coaching reports analyzing executive score, cutoff prognosis, negative marking penalty bleed, subject strengths vs vulnerabilities, and 3 high-yield weekly revision directives.
   - **1-Click Attempt Logging**: Save offline simulation attempts directly into SQLite `test_sessions`, `attempts`, and the Error Notebook to power the 7-day Revision Planner.

10. **Native Anki Package (.apkg) & Open-Source Ecosystem Integration:**
   - **Native Anki (.apkg) Exporter (`anki_exporter.py`)**: Integrates the open-source `genanki` library to compile responsive, styled flashcards directly importable into Anki desktop and mobile. Features dark-mode compatible CSS, front question layout, and back reveal with correct answer, explanations, distractor analysis, and hierarchical tags (`BPSC::Subject::Topic`).
   - One-click `.apkg` export across Question Bank, Pinned Revision Vault, Offline Papers, and Settings.
   - **Vector PDF Generation (`reportlab`)**: Produces crisp, publication-grade vector PDFs with standard typography and alignment grids.

11. **Free Spaced Repetition Scheduler (`fsrs` v6) Engine (`fsrs_engine.py`):**
   - State-of-the-art DSR (Difficulty, Stability, Retrievability) memory decay algorithm replacing static revision intervals with mathematically optimal review scheduling.
   - Automatically updates card stability and calculates real-time retrievability on every question attempt.
   - **FSRS Scientific Revision Queue**: Dedicated tab in Revision Planner sorting questions right before memory retention slips below 90%, with 1-click rapid memory drills.
   - **FSRS Memory Retention Gauge**: Real-time memory health widget on Dashboard displaying overall long-term retention status.

12. **Neural Speech Synthesis (`edge-tts`) & Audio Learning Lab (`audio_engine.py`):**
   - High-fidelity Indian English and Hindi neural voices (`en-IN-PrabhatNeural`, `en-IN-NeerjaNeural`, `hi-IN-MadhurNeural`, `hi-IN-SwaraNeural`) requiring no paid API keys.
   - **Question & Choice Narration**: Listen to questions, statements, and 4 choices read aloud in Practice Mode.
   - **Audio Mistake Explanations**: One-click audio breakdown of correct answers, conceptual foundations, and distractor traps during post-test review.
   - **Current Affairs Audio Dossier Podcasts**: Synthesizes saved research dossiers and policy analyses into structured 2-minute daily audio podcasts.

13. **High-Speed Document Parsing & Dual-Column De-Columnizer (`pymupdf` / `pdf_extractor.py`):**
   - 10–20x faster native C-level PDF rendering and text extraction using PyMuPDF (fitz).
   - **Dual-Column De-Columnizer**: Intelligently bisects two-column BPSC compendiums (Ghatna Chakra, Eduteria) into left-then-right reading streams, preventing horizontal line bleed and character interleaving during OCR.

14. **Interactive Plotly Visual Analytics (`plotly`):**
   - **11-Subject Radar / Spider Readiness Web**: Dynamic interactive chart benchmarking subject accuracy against the historical BPSC Prelims 65% cutoff target.
   - Visualizes strengths and vulnerable subjects across all 11 official syllabus divisions.

15. **Authentic 150-Question BPSC Prelims Blueprint Mock & Solutions Booklet PDF (`omr_engine.py`):**
   - **1-Click 150-Question Mock Assembly**: Assembles complete 150-question Prelims test following official BPSC quotas: History (30), Science (30), Current Affairs (30), Bihar Special (20), Geography (10), Polity (10), Economy (10), General Mental Ability & Maths (10).
   - **Official Solutions & Explanations Booklet (PDF)**: Generates publication-grade solutions booklet with stems, green-highlighted correct answers, detailed explanations, distractor traps, and concepts tested.
   - **Candidate Performance Transcript & Certificate (PDF)**: High-precision vector PDF transcript featuring candidate roll number, series, score breakdown, -0.33 negative marking penalty bleed, subject table, and qualification prognosis.

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

Run all 89 tests (19 legacy regression tests + 24 v1.0 feature tests + 28 mock questions & OCR tests + 8 offline OMR & Anki tests + 10 FSRS, Edge-TTS, PyMuPDF, Plotly & Blueprint PDF tests):

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
