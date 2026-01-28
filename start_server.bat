@echo off
chcp 65001 >nul 2>&1
echo ================================================
echo ChemEng Local Server
echo ================================================

REM Check if uvicorn is installed
python -c "import uvicorn" 2>nul
if errorlevel 1 (
    echo Installing required packages...
    pip install uvicorn fastapi
)

echo.
echo Starting server at http://localhost:8000
echo API docs: http://localhost:8000/docs
echo.
echo To expose to internet, run in another terminal:
echo   ngrok http 8000
echo ================================================
echo.

python server.py --port 8000

pause
