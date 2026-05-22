@echo off
title Chronicles of Ven - Full System (with ChatGPT)
color 0A

echo.
echo  ================================================
echo   Chronicles of Ven -- Starting Full System
echo  ================================================
echo.

cd /d "%~dp0..\.."

echo  [1/3] Starting search API...
start "Novel API" cmd /k ".venv\Scripts\python.exe -m uvicorn api.server:app --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak > nul

echo  [2/3] Starting search UI...
start "Novel UI" cmd /k ".venv\Scripts\streamlit.exe run ui/app.py"

timeout /t 2 /nobreak > nul

echo  [3/3] Starting ChatGPT tunnel...
echo.
echo  *** IMPORTANT ***
echo  Once ngrok starts, your friend's Custom GPT will work automatically.
echo  Do NOT close the ngrok window while he is using it.
echo.

REM ── Replace the domain below with your actual ngrok static domain ──────────
set NGROK_DOMAIN=YOUR_STATIC_DOMAIN.ngrok-free.app

start "ngrok tunnel" cmd /k "ngrok http 8000 --domain=%NGROK_DOMAIN%"

echo  All systems running.
echo  Keep all three windows open.
echo.
pause
