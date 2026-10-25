@echo off
setlocal
cd /d "%~dp0"

echo ======================================
echo BPSC Question Lab - first-time setup
echo ======================================

where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher "py" was not found. Install Python 3.11 or newer from https://www.python.org/downloads/
  echo During installation, enable the Python launcher and Add Python to PATH.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating a local Python environment...
  py -m venv .venv
  if errorlevel 1 (
    echo Could not create the virtual environment.
    pause
    exit /b 1
  )
)

echo Installing or checking required packages...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Package installation failed. Check your internet connection and try again.
  pause
  exit /b 1
)

echo Starting BPSC Question Lab in your browser...
".venv\Scripts\python.exe" -m streamlit run app.py
pause
