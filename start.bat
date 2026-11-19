@echo off
title Wholesale Billing System
echo ========================================================
echo   Wholesale Billing System - All Services Coordinator
echo ========================================================
echo.
echo Starting Backend API (FastAPI on http://localhost:8000)...
start "Backend API Server" cmd /k "cd /d "%~dp0backend" && .\venv\Scripts\python.exe run.py"

echo Starting Frontend UI (Vite on http://localhost:8443)...
start "Frontend UI App" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ========================================================
echo   Both services started!
echo   - Backend Docs:  http://localhost:8000/docs
echo   - Frontend App:  http://localhost:8443/
echo.
echo   Demo Login PINs:
echo   - Owner:     1234
echo   - Manager:   2222
echo   - Employee:  3333
echo ========================================================
pause

