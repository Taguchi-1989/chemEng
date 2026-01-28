@echo off
chcp 65001 >nul 2>&1
echo ================================================
echo ChemEng - ngrok Tunnel
echo ================================================
echo.
echo Exposing local server (port 8000) to internet...
echo.
echo After ngrok starts:
echo   1. Copy the "Forwarding" URL (e.g., https://xxxx.ngrok-free.app)
echo   2. Set it as BACKEND_URL in Vercel environment variables
echo.
echo ================================================
echo.

ngrok http 8000

pause
