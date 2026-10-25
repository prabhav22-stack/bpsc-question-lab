# BPSC Question Lab: project instructions for Antigravity

## Project goal
Build a local-first study tool for BPSC and UPSC preparation. The current release is Version 0.1. Keep changes small, testable, and compatible with later versions.

## Current stack
- Python 3.11+
- Streamlit UI (`app.py`)
- SQLite database (`question_lab.db`, created locally at runtime)
- CSV import/export

## Rules for changes
1. Before editing, inspect `README.md`, `app.py`, `requirements.txt`, and `sample_questions.csv`. Summarize the current architecture and identify the smallest safe implementation plan.
2. Do not rewrite the application from scratch or remove working features unless explicitly asked.
3. Preserve existing question-bank data and attempt history. Never delete, reset, or migrate `question_lab.db` destructively. Back up a database before any schema migration.
4. Keep authentic official PYQs, third-party questions, and AI-generated practice questions clearly distinguished. Never label generated questions as authentic PYQs.
5. Preserve source attribution: source name, URL, exam/year where known, and verification status. Do not invent sources, questions, answer keys, or verification claims.
6. Keep API keys and credentials out of source files. Use environment variables or a local `.env` file that is ignored by Git.
7. For every code change, run the relevant tests or syntax checks and report exactly what was tested and what was not tested. Do not claim the app was launched or visually tested unless that happened.
8. Prefer simple, readable Python and small modules. Avoid unnecessary dependencies.
9. Make the UI usable for a beginner and keep student-facing text in English.
10. Keep the weekly revision plan transparent. Explain which recorded attempts, accuracy, recency, or error categories drove each recommendation; do not imply that it predicts the actual exam paper.

## Development workflow
- Start by reviewing the code and proposing a short plan.
- Ask before broad refactors, destructive data operations, or adding paid services.
- Implement one milestone at a time.
- Add regression tests for bug fixes and core question-scoring/revision logic where practical.
- Update `README.md` whenever setup steps, dependencies, data format, or features change.
- Keep the version number and roadmap consistent with the implemented features.

## Current roadmap
- 0.1: Local question bank, MCQ practice, attempts, error log, rule-based weekly revision.
- 0.2: Better imports, deduplication, bulk editing, improved topic tagging.
- 0.3: Online search and source-aware question extraction.
- 0.4: AI-generated BPSC-style questions with answer verification and clear labels.
- 1.0: Tests, reliability, backups, polished workflow, optional hosting.
