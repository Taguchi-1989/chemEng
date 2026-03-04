@echo off
chcp 65001 >nul 2>&1
title ChemEng - 化学工学計算ツール

REM スクリプトのあるディレクトリに移動（ショートカットやタスクスケジューラからの起動対応）
cd /d "%~dp0"

echo ========================================
echo   ChemEng - 化学工学計算ツール
echo ========================================
echo.

REM Python確認
python --version >nul 2>&1
if errorlevel 1 (
    echo [エラー] Pythonがインストールされていません。
    echo Python 3.9以上をインストールしてください。
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 仮想環境の確認・作成
if not exist "venv" (
    echo [初回セットアップ] 仮想環境を作成しています...
    python -m venv venv
    echo 仮想環境を作成しました。
)

REM 仮想環境を有効化
call venv\Scripts\activate.bat

REM 依存パッケージのインストール確認
python -c "import uvicorn; import thermo" 2>nul
if errorlevel 1 (
    echo [セットアップ] 依存パッケージをインストールしています...
    pip install -r requirements_full.txt
    echo インストール完了。
)

echo.
echo サーバーを起動しています...
echo ブラウザで http://localhost:8000 を開きます
echo.
echo 終了するには Ctrl+C を押すか、このウィンドウを閉じてください。
echo ========================================

REM 3秒後にブラウザを開く
start /b cmd /c "timeout /t 3 >nul && start http://localhost:8000"

REM サーバー起動
python server.py --port 8000
