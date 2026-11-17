@echo off
echo ========================================================
echo   Starting AgriAI Smart Farming Assistant Services
echo ========================================================
echo.
echo Starting FastAPI Backend on port 8000...
start "AgriAI Backend" cmd /k "cd /d %~dp0backend && py -3.13 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 /nobreak >nul

echo Starting Vite Frontend on port 5173...
start "AgriAI Frontend" cmd /k "cd /d %~dp0 && npm run dev"

echo.
echo ========================================================
echo AgriAI services launched in separate windows!
echo - Desktop URL: http://localhost:5173
echo - Mobile URL:  http://192.168.1.45:5173  (Ensure phone is on same Wi-Fi)
echo - Backend API: http://localhost:8000/docs
echo ========================================================

