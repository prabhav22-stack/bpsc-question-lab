# Open BPSC Question Lab in Google Antigravity

## 1. Open this project
1. Extract the ZIP to a normal folder, for example `Documents\bpsc_question_lab_v0_1`.
2. Install and open Google Antigravity from https://antigravity.google/download.
3. Create a New Project and choose **Add Folder**. Select the extracted `bpsc_question_lab_v0_1` folder, then create the project.
4. Start in **Local mode** for direct editing of this folder. Keep a backup copy before allowing broad changes.
5. Antigravity should discover the project's root `AGENTS.md` instructions automatically.

You do not need GitHub just to open and work on this local folder.

## 2. First prompt to paste into Antigravity

Please inspect this BPSC Question Lab Version 0.1 codebase before changing anything. Read AGENTS.md and README.md, then inspect app.py, requirements.txt, and sample_questions.csv. Explain the current architecture and check for obvious correctness or runtime problems. Run safe, relevant checks where possible. Do not rewrite the app, add online search or AI features yet, delete/reset any database, or make broad changes. First return a short findings report and a proposed small plan for making Version 0.1 reliable. Clearly distinguish checks you actually ran from checks you could not run. Wait for my approval before implementing changes.

## 3. Run the app from Antigravity's terminal

On Windows, from the project folder run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Then open the local URL printed by Streamlit, usually `http://localhost:8501`.

Alternatively, double-click `start_windows.bat` in File Explorer.

## 4. Keep your work safe
- Back up the whole project folder periodically.
- Keep `question_lab.db` if you have already created questions or attempts; it contains local study data.
- Do not paste API keys or passwords into chat or commit them into the project.
- Review proposed file changes before accepting them, especially database and installation commands.
