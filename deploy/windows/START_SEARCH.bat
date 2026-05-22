@echo off
title Chronicles of Ven - Search System
color 0A

echo.
echo  ================================================
echo   Chronicles of Ven -- Starting Search System
echo  ================================================
echo.

cd /d "%~dp0..\.."

echo  [1/2] Starting search API...
start "Novel API" cmd /k ".venv\Scripts\python.exe -m uvicorn api.server:app --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak > nul

echo  [2/2] Starting search UI...
start "Novel UI" cmd /k ".venv\Scripts\streamlit.exe run ui/app.py"

echo.
echo  Done! Your browser should open automatically.
echo  If it doesn't, go to: http://localhost:8501
echo.
echo  Keep this window open while you're using the search tool.
echo  Close it when you're done.
echo.
pause
