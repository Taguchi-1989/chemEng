#!/usr/bin/env bash
set -e

echo "========================================"
echo "  ChemEng - Chemical Engineering Tool"
echo "========================================"
echo ""

# Python check
if ! command -v python3 &> /dev/null; then
    echo "[Error] Python 3 is not installed."
    echo "Install Python 3.10+ from https://www.python.org/downloads/"
    exit 1
fi

PYTHON=python3

# Create venv if not exists
if [ ! -d "venv" ]; then
    echo "[Setup] Creating virtual environment..."
    $PYTHON -m venv venv
    echo "Virtual environment created."
fi

# Activate venv
source venv/bin/activate

# Install dependencies if needed
if ! python -c "import uvicorn; import thermo" 2>/dev/null; then
    echo "[Setup] Installing dependencies..."
    pip install -r requirements_full.txt
    echo "Installation complete."
fi

echo ""
echo "Starting server..."
echo "Open http://localhost:8000 in your browser"
echo ""
echo "Press Ctrl+C to stop."
echo "========================================"

# Open browser after 3 seconds
(sleep 3 && python -c "import webbrowser; webbrowser.open('http://localhost:8000')" ) &

# Start server
python server.py --port 8000
