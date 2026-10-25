@echo off
title BPSC Question Lab - Internet Share
cd /d "%~dp0"

echo ========================================================
echo   Starting BPSC Question Lab with Free Internet Access
echo ========================================================
echo.

:: Start Streamlit in the background if not already running
netstat -ano | findstr :8501 >nul
if %errorlevel% neq 0 (
    echo [1/2] Starting local Streamlit server...
    start /b "" .\.venv\Scripts\python.exe -m streamlit run app.py --server.headless true --server.port 8501
    timeout /t 3 /nobreak >nul
) else (
    echo [1/2] Streamlit is already running on port 8501.
)

echo.
echo [2/2] Opening secure Cloudflare Internet Tunnel...
echo Look for the 'https://...trycloudflare.com' link below.
echo Share that link to access from your phone or any browser!
echo.
echo (Press Ctrl+C to stop sharing)
echo ========================================================
echo.

.\cloudflared.exe tunnel --url http://localhost:8501
pause
