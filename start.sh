#!/usr/bin/env bash
# ============================================================
#  ChemEng start.sh - Linux/macOS 起動スクリプト
#  Usage:
#    bash start.sh             通常起動
#    bash start.sh --port 8080 ポート指定
#    bash start.sh --repair    依存パッケージ再インストール
#    bash start.sh --reset     仮想環境を削除して再構築
# ============================================================

set -e

# スクリプトのあるディレクトリに移動
cd "$(dirname "$0")"

# --- 設定 ---
VERSION="0.1.0"
DEFAULT_PORT=8000
PORT=$DEFAULT_PORT
PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=10
VENV_DIR="venv"
REQ_FILE="requirements_full.txt"
LOG_FILE="chemeng_setup.log"
MODE="start"

# --- ANSI色 ---
GREEN='\033[32m'
RED='\033[31m'
YELLOW='\033[33m'
CYAN='\033[36m'
RESET='\033[0m'

# --- ログ関数 ---
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# --- 引数パース ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)
            PORT="$2"
            shift 2
            ;;
        --repair)
            MODE="repair"
            shift
            ;;
        --reset)
            MODE="reset"
            shift
            ;;
        --help|-h)
            echo "Usage: bash start.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --port PORT   ポート指定 (default: $DEFAULT_PORT)"
            echo "  --repair      依存パッケージ再インストール"
            echo "  --reset       仮想環境を削除して再構築"
            echo "  --help, -h    このヘルプを表示"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information."
            exit 1
            ;;
    esac
done

log "========== Session start (mode=$MODE) =========="

echo ""
echo -e "  ${CYAN}========================================${RESET}"
echo -e "  ${CYAN}  ChemEng v$VERSION - Chemical Engineering Tool  ${RESET}"
echo -e "  ${CYAN}========================================${RESET}"
echo ""

# --- リセットモード ---
if [ "$MODE" = "reset" ]; then
    echo -e "  ${YELLOW}[Reset] Deleting virtual environment...${RESET}"
    if [ -d "$VENV_DIR" ]; then
        rm -rf "$VENV_DIR"
        log "Reset: venv deleted"
        echo -e "  ${GREEN}[OK]${RESET} Virtual environment deleted."
    else
        echo "  No virtual environment found."
    fi
    echo "  Continuing with normal startup..."
    echo ""
    MODE="start"
fi

# --- ステップ 1/5: Python確認 ---
echo "  ----------------------------------------"
echo "    Step 1/5: Python environment check"
echo "  ----------------------------------------"
echo ""

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &> /dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "  ${RED}[NG]${RESET} Python is not installed."
    echo "  Install Python $PYTHON_MIN_MAJOR.$PYTHON_MIN_MINOR+ from https://www.python.org/downloads/"
    log "Python not found"
    exit 1
fi

# バージョンチェック
PY_VER=$($PYTHON --version 2>&1 | awk '{print $2}')
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)

log "Python found: $PYTHON $PY_VER"

if [ "$PY_MAJOR" -lt "$PYTHON_MIN_MAJOR" ] || { [ "$PY_MAJOR" -eq "$PYTHON_MIN_MAJOR" ] && [ "$PY_MINOR" -lt "$PYTHON_MIN_MINOR" ]; }; then
    echo -e "  ${RED}[NG]${RESET} Python $PY_VER is too old (need >= $PYTHON_MIN_MAJOR.$PYTHON_MIN_MINOR)"
    echo "  Install Python $PYTHON_MIN_MAJOR.$PYTHON_MIN_MINOR+ from https://www.python.org/downloads/"
    log "Python version too old: $PY_VER"
    exit 1
fi

echo -e "  ${GREEN}[OK]${RESET} Python $PY_VER detected."
echo ""

# --- ステップ 2/5: 仮想環境 ---
echo "  ----------------------------------------"
echo "    Step 2/5: Virtual environment"
echo "  ----------------------------------------"
echo ""

if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
    # 壊れていないか確認
    if ! python -c "print('ok')" &>/dev/null; then
        echo -e "  ${YELLOW}[!]${RESET} Virtual environment is broken. Recreating..."
        log "Broken venv detected, recreating"
        rm -rf "$VENV_DIR"
        $PYTHON -m venv "$VENV_DIR"
        source "$VENV_DIR/bin/activate"
    fi
    log "Existing venv activated"
else
    echo "  Creating virtual environment..."
    $PYTHON -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    log "New venv created and activated"
    echo "  Virtual environment created."
fi

echo -e "  ${GREEN}[OK]${RESET} Virtual environment is active."
echo ""

# --- ステップ 3/5: 依存パッケージ ---
echo "  ----------------------------------------"
echo "    Step 3/5: Dependencies"
echo "  ----------------------------------------"
echo ""

if [ "$MODE" = "repair" ]; then
    echo -e "  ${YELLOW}[Repair]${RESET} Force-reinstalling all packages..."
    log "Repair mode: force-reinstalling packages"
    pip install --force-reinstall -r "$REQ_FILE" >> "$LOG_FILE" 2>&1
    echo -e "  ${GREEN}[OK]${RESET} Packages reinstalled."
elif ! python -c "import uvicorn; import thermo; import fastapi; import scipy" 2>/dev/null; then
    echo "  Installing dependencies..."
    echo "  (This may take 5-10 minutes on first run)"
    echo ""
    log "Installing packages from $REQ_FILE"
    python -m pip install --upgrade pip >> "$LOG_FILE" 2>&1
    pip install -r "$REQ_FILE" >> "$LOG_FILE" 2>&1
    log "Package installation complete"
    echo "  Installation complete."
else
    log "All packages already installed"
fi

echo -e "  ${GREEN}[OK]${RESET} All packages are installed."
echo ""

# --- ステップ 4/5: ポートチェック ---
echo "  ----------------------------------------"
echo "    Step 4/5: Port check"
echo "  ----------------------------------------"
echo ""

port_in_use() {
    if command -v lsof &>/dev/null; then
        lsof -i ":$1" &>/dev/null
    elif command -v ss &>/dev/null; then
        ss -tlnp 2>/dev/null | grep -q ":$1 "
    else
        # チェックできない場合はOKとみなす
        return 1
    fi
}

if port_in_use "$PORT"; then
    echo -e "  ${YELLOW}[!]${RESET} Port $PORT is in use."
    log "Port $PORT is in use"
    # 空きポートを探す
    for try_port in 8000 8080 8888 9000; do
        if ! port_in_use "$try_port"; then
            PORT=$try_port
            echo -e "  ${GREEN}[OK]${RESET} Using port $PORT instead."
            log "Found free port: $PORT"
            break
        fi
    done
else
    echo -e "  ${GREEN}[OK]${RESET} Port $PORT is available."
    log "Port $PORT is available"
fi
echo ""

# --- ステップ 5/5: サーバー起動 ---
echo "  ----------------------------------------"
echo "    Step 5/5: Starting server"
echo "  ----------------------------------------"
echo ""
echo -e "  ${GREEN}========================================${RESET}"
echo -e "  ${GREEN}  Ready! Starting server...             ${RESET}"
echo -e "  ${GREEN}========================================${RESET}"
echo ""
echo "    URL:  http://localhost:$PORT"
echo "    API:  http://localhost:$PORT/docs"
echo ""
echo "    Press Ctrl+C to stop."
echo ""
echo "  ========================================"
echo ""

log "Server starting on port $PORT"

# ブラウザを3秒後に開く
(sleep 3 && python -c "import webbrowser; webbrowser.open('http://localhost:$PORT')" ) &

# サーバー起動
python server.py --port "$PORT"
