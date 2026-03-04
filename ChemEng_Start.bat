@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title ChemEng - 化学工学計算ツール

REM ============================================================
REM  ChemEng_Start.bat - 初心者フレンドリー起動スクリプト
REM  ダブルクリックするだけで環境構築からサーバー起動まで実行
REM ============================================================

REM スクリプトのあるディレクトリに移動
cd /d "%~dp0"

REM --- 設定変数 ---
set "VERSION=0.1.0"
set "DEFAULT_PORT=8000"
set "PORT=%DEFAULT_PORT%"
set "PYTHON_MIN_MAJOR=3"
set "PYTHON_MIN_MINOR=10"
set "VENV_DIR=venv"
set "REQ_FILE=requirements_full.txt"
set "LOG_FILE=chemeng_setup.log"
set "PYTHON_CMD="
set "PY_VER="
set "PY_MAJOR="
set "PY_MINOR="

REM --- ANSI色サポート（Windows 10+） ---
set "GREEN="
set "RED="
set "YELLOW="
set "CYAN="
set "RESET="
set "ESC="
for /f %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"
if defined ESC (
    set "GREEN=!ESC![32m"
    set "RED=!ESC![31m"
    set "YELLOW=!ESC![33m"
    set "CYAN=!ESC![36m"
    set "RESET=!ESC![0m"
)

REM --- ログセッション開始 ---
echo [%date% %time%] ========== Session start ========== >> "%LOG_FILE%"

goto MAIN_MENU

REM ============================================================
REM  メインメニュー
REM ============================================================
:MAIN_MENU
cls
echo.
echo   !CYAN!========================================!RESET!
echo   !CYAN!  ChemEng v%VERSION% - 化学工学計算ツール  !RESET!
echo   !CYAN!========================================!RESET!
echo.
echo     [1] 起動（通常スタート）
echo     [2] 修復（依存パッケージ再インストール）
echo     [3] リセット（仮想環境を削除して再構築）
echo     [4] ヘルプ・トラブルシューティング
echo     [5] 終了
echo.
set "MENU_CHOICE="
set /p "MENU_CHOICE=  選択してください (1-5): "
if "!MENU_CHOICE!"=="1" goto FLOW_NORMAL
if "!MENU_CHOICE!"=="2" goto FLOW_REPAIR
if "!MENU_CHOICE!"=="3" goto FLOW_RESET
if "!MENU_CHOICE!"=="4" goto HELP
if "!MENU_CHOICE!"=="5" goto EXIT
echo.
echo   !YELLOW![注意] 1〜5の数字を入力してください。!RESET!
timeout /t 2 >nul
goto MAIN_MENU

REM ============================================================
REM  通常起動フロー
REM ============================================================
:FLOW_NORMAL
cls
echo.
echo   !CYAN!========================================!RESET!
echo   !CYAN!  通常起動 - 環境チェック開始           !RESET!
echo   !CYAN!========================================!RESET!
echo.

REM --- ステップ 1/5: Python環境の確認 ---
:STEP1
echo   ----------------------------------------
echo     ステップ 1/5: Python環境の確認
echo   ----------------------------------------
echo.
call :CHECK_PYTHON
set "STEP1_RESULT=!errorlevel!"
if !STEP1_RESULT! equ 0 (
    echo   !GREEN![OK]!RESET! Python !PY_VER! を検出しました。
    echo.
    goto STEP2
)
if !STEP1_RESULT! equ 2 (
    goto STEP1_FAIL_VERSION
)
goto STEP1_FAIL_MISSING

REM --- ステップ 2/5: 仮想環境の準備 ---
:STEP2
echo   ----------------------------------------
echo     ステップ 2/5: 仮想環境の準備
echo   ----------------------------------------
echo.
call :CHECK_VENV
if !errorlevel! equ 0 (
    echo   !GREEN![OK]!RESET! 仮想環境が有効です。
    echo.
    goto STEP3
)
goto STEP2_FAIL

REM --- ステップ 3/5: 依存パッケージの確認 ---
:STEP3
echo   ----------------------------------------
echo     ステップ 3/5: 依存パッケージの確認
echo   ----------------------------------------
echo.
call :CHECK_DEPS
if !errorlevel! equ 0 (
    echo   !GREEN![OK]!RESET! すべてのパッケージがインストール済みです。
    echo.
    goto STEP4
)
goto STEP3_FAIL

REM --- ステップ 4/5: ポートの確認 ---
:STEP4
echo   ----------------------------------------
echo     ステップ 4/5: ポートの確認
echo   ----------------------------------------
echo.
call :CHECK_PORT
if !errorlevel! equ 0 (
    echo   !GREEN![OK]!RESET! ポート !PORT! は利用可能です。
    echo.
    goto STEP5
)
goto STEP4_FAIL

REM --- ステップ 5/5: サーバー起動 ---
:STEP5
echo   ----------------------------------------
echo     ステップ 5/5: サーバー起動
echo   ----------------------------------------
echo.
echo   !GREEN!========================================!RESET!
echo   !GREEN!  準備完了！サーバーを起動します        !RESET!
echo   !GREEN!========================================!RESET!
echo.
echo     URL:  http://localhost:!PORT!
echo     API:  http://localhost:!PORT!/docs
echo.
echo     終了するには Ctrl+C を押すか、
echo     このウィンドウを閉じてください。
echo.
echo   ========================================
echo.

call :LOG "Server starting on port !PORT!"

REM 3秒後にブラウザを開く
start /b cmd /c "timeout /t 3 >nul && start http://localhost:!PORT!"

REM サーバー起動（ブロッキング）
python server.py --port !PORT!

goto AFTER_SERVER

REM ============================================================
REM  ステップ失敗ハンドラー
REM ============================================================

REM --- Step 1 失敗: Python未検出 ---
:STEP1_FAIL_MISSING
echo   !RED![NG]!RESET! Python が見つかりません。
echo.
echo   Python 3.10以上が必要です。
echo.
goto STEP1_INSTALL_OPTIONS

REM --- Step 1 失敗: バージョン不足 ---
:STEP1_FAIL_VERSION
echo   !RED![NG]!RESET! Python !PY_VER! が見つかりましたが、バージョンが古すぎます。
echo       必要: !PYTHON_MIN_MAJOR!.!PYTHON_MIN_MINOR! 以上
echo.
goto STEP1_INSTALL_OPTIONS

:STEP1_INSTALL_OPTIONS
REM winget が使えるか確認
winget --version >nul 2>&1
if !errorlevel! equ 0 (
    echo     [1] winget で Python 3.12 を自動インストール（推奨）
) else (
    echo     [1] !YELLOW!（winget が利用できません）!RESET!
)
echo     [2] ダウンロードページをブラウザで開く
echo     [3] メインメニューに戻る
echo.
set "PY_CHOICE="
set /p "PY_CHOICE=  選択してください (1-3): "

if "!PY_CHOICE!"=="1" (
    winget --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo.
        echo   !YELLOW![注意] winget が利用できません。[2] を選択してください。!RESET!
        timeout /t 2 >nul
        goto STEP1_INSTALL_OPTIONS
    )
    echo.
    echo   Python 3.12 をインストール中...
    echo   （数分かかることがあります）
    echo.
    call :LOG "Installing Python 3.12 via winget"
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    echo.
    echo   !GREEN!============================================!RESET!
    echo   !GREEN!  インストール完了！                        !RESET!
    echo   !GREEN!============================================!RESET!
    echo.
    echo   PATHを反映するため、このウィンドウを閉じてから
    echo   ChemEng_Start.bat を再度ダブルクリックしてください。
    echo.
    call :LOG "Python installed. Restart required."
    pause
    goto EXIT
)
if "!PY_CHOICE!"=="2" (
    start https://www.python.org/downloads/
    echo.
    echo   ブラウザでダウンロードページを開きました。
    echo.
    echo   !YELLOW!インストール時の注意:!RESET!
    echo     * 「Add Python to PATH」に必ずチェックを入れてください
    echo     * インストール完了後、このウィンドウを閉じて
    echo       ChemEng_Start.bat を再度ダブルクリックしてください
    echo.
    call :LOG "Directed user to Python download page"
    pause
    goto EXIT
)
goto MAIN_MENU

REM --- Step 2 失敗: 仮想環境作成失敗 ---
:STEP2_FAIL
echo   !RED![NG]!RESET! 仮想環境の作成に失敗しました。
echo.
echo   考えられる原因:
echo     - ディスク容量不足
echo     - フォルダへの書き込み権限がない
echo     - ウイルス対策ソフトがブロックしている
echo.
echo     [1] 再試行
echo     [2] メインメニューに戻る
echo.
set "V_CHOICE="
set /p "V_CHOICE=  選択してください (1-2): "
if "!V_CHOICE!"=="1" goto STEP2
goto MAIN_MENU

REM --- Step 3 失敗: パッケージインストール失敗 ---
:STEP3_FAIL
echo   !RED![NG]!RESET! パッケージのインストールに失敗しました。
echo.
echo   考えられる原因:
echo     - インターネット接続がない
echo     - ファイアウォール/プロキシがpipをブロックしている
echo     - ディスク容量不足
echo.
echo   詳細はログファイルを確認: !LOG_FILE!
echo.
echo     [1] 再試行
echo     [2] メインメニューに戻る
echo.
set "D_CHOICE="
set /p "D_CHOICE=  選択してください (1-2): "
if "!D_CHOICE!"=="1" goto STEP3
goto MAIN_MENU

REM --- Step 4 失敗: ポート使用中 ---
:STEP4_FAIL
echo   !YELLOW![注意]!RESET! ポート !PORT! は現在使用中です。
echo.
echo     [1] 別のポートを自動選択
echo     [2] 再確認
echo     [3] メインメニューに戻る
echo.
set "P_CHOICE="
set /p "P_CHOICE=  選択してください (1-3): "
if "!P_CHOICE!"=="1" (
    call :FIND_FREE_PORT
    echo.
    echo   ポート !PORT! を使用します。
    echo.
    goto STEP4
)
if "!P_CHOICE!"=="2" (
    set "PORT=%DEFAULT_PORT%"
    goto STEP4
)
goto MAIN_MENU

REM --- サーバー停止後 ---
:AFTER_SERVER
echo.
echo   ========================================
echo     サーバーが停止しました。
echo   ========================================
echo.
echo     [1] 再起動
echo     [2] メインメニューに戻る
echo     [3] 終了
echo.
set "AFTER_CHOICE="
set /p "AFTER_CHOICE=  選択してください (1-3): "
if "!AFTER_CHOICE!"=="1" goto STEP5
if "!AFTER_CHOICE!"=="2" goto MAIN_MENU
goto EXIT

REM ============================================================
REM  修復モード
REM ============================================================
:FLOW_REPAIR
cls
echo.
echo   !CYAN!========================================!RESET!
echo   !CYAN!  修復モード                            !RESET!
echo   !CYAN!========================================!RESET!
echo.
echo   依存パッケージを強制的に再インストールします。
echo.

REM Python確認
call :CHECK_PYTHON
if !errorlevel! neq 0 (
    echo   !RED![エラー]!RESET! Pythonが見つかりません。通常起動を実行してください。
    echo.
    pause
    goto MAIN_MENU
)

REM venv確認
if not exist "!VENV_DIR!\Scripts\activate.bat" (
    echo   !YELLOW![注意]!RESET! 仮想環境が見つかりません。通常起動に切り替えます。
    echo.
    timeout /t 2 >nul
    goto FLOW_NORMAL
)

call "!VENV_DIR!\Scripts\activate.bat"

echo   パッケージを再インストール中...
echo   （数分かかることがあります）
echo.
call :LOG "Repair mode: force-reinstalling packages"
pip install --force-reinstall -r "!REQ_FILE!" >> "!LOG_FILE!" 2>&1
if !errorlevel! neq 0 (
    echo   !RED![エラー]!RESET! 再インストールに失敗しました。
    echo   ログファイル: !LOG_FILE!
    echo.
    pause
    goto MAIN_MENU
)

echo   !GREEN![OK]!RESET! 修復完了！
echo.
echo   サーバーを起動しますか？
set "REPAIR_START="
set /p "REPAIR_START=  起動する場合は Y を入力: "
if /i "!REPAIR_START!"=="Y" (
    set "PORT=%DEFAULT_PORT%"
    goto STEP4
)
goto MAIN_MENU

REM ============================================================
REM  リセットモード
REM ============================================================
:FLOW_RESET
cls
echo.
echo   !CYAN!========================================!RESET!
echo   !CYAN!  リセットモード                        !RESET!
echo   !CYAN!========================================!RESET!
echo.
echo   仮想環境を完全に削除して再構築します。
echo.
echo   !YELLOW![警告] venv フォルダが削除されます。!RESET!
echo.
set "RESET_CONFIRM="
set /p "RESET_CONFIRM=  続行しますか？ (Y/N): "
if /i not "!RESET_CONFIRM!"=="Y" goto MAIN_MENU

if exist "!VENV_DIR!" (
    echo.
    echo   仮想環境を削除中...
    call :LOG "Reset mode: deleting venv"
    rmdir /s /q "!VENV_DIR!"
    echo   !GREEN![OK]!RESET! 削除完了。
)

echo.
echo   通常起動を開始します...
timeout /t 2 >nul
goto FLOW_NORMAL

REM ============================================================
REM  ヘルプ
REM ============================================================
:HELP
cls
echo.
echo   !CYAN!========================================!RESET!
echo   !CYAN!  ヘルプ・トラブルシューティング        !RESET!
echo   !CYAN!========================================!RESET!
echo.
echo   [Q] 起動しない
echo   [A] Python 3.10以上がインストールされているか確認
echo       コマンドプロンプトで: python --version
echo.
echo   [Q] 計算できない・エラーが出る
echo   [A] メニューの「修復」または「リセット」を試してください
echo.
echo   [Q] ポート8000が使用中
echo   [A] 「起動」メニューで別ポートを自動選択できます
echo.
echo   [Q] 特定の物質が見つからない
echo   [A] 英語名またはCAS番号で検索してください
echo       例: "ethanol", "64-17-5"
echo.
echo   [Q] ログファイルの場所
echo   [A] %CD%\!LOG_FILE!
echo.
echo   ========================================
echo.
pause
goto MAIN_MENU

REM ============================================================
REM  終了
REM ============================================================
:EXIT
call :LOG "Session end"
echo.
echo   終了します。
endlocal
exit /b 0

REM ============================================================
REM  サブルーチン
REM ============================================================

REM --- Python検出 + バージョン検証 ---
REM 戻り値: 0=OK, 1=未検出, 2=バージョン不足
:CHECK_PYTHON
set "PYTHON_CMD="
set "PY_VER="
set "PY_MAJOR="
set "PY_MINOR="

REM python, py, python3 の順で試す
for %%c in (python py python3) do (
    if not defined PYTHON_CMD (
        %%c --version >nul 2>&1
        if !errorlevel! equ 0 (
            REM WindowsApps スタブ（Microsoft Store リダイレクト）を除外
            set "_IS_STORE="
            for /f "delims=" %%p in ('where %%c 2^>nul') do (
                echo %%p | findstr /i "WindowsApps" >nul 2>&1
                if !errorlevel! equ 0 set "_IS_STORE=1"
            )
            if not defined _IS_STORE (
                set "PYTHON_CMD=%%c"
            )
        )
    )
)

if not defined PYTHON_CMD (
    call :LOG "Python not found"
    exit /b 1
)

REM バージョン取得
for /f "tokens=2 delims= " %%v in ('!PYTHON_CMD! --version 2^>^&1') do set "PY_VER=%%v"
for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
    set "PY_MAJOR=%%a"
    set "PY_MINOR=%%b"
)

call :LOG "Python found: !PYTHON_CMD! !PY_VER!"

REM バージョンチェック: >= 3.10
if !PY_MAJOR! LSS !PYTHON_MIN_MAJOR! (
    exit /b 2
)
if !PY_MAJOR! EQU !PYTHON_MIN_MAJOR! (
    if !PY_MINOR! LSS !PYTHON_MIN_MINOR! (
        exit /b 2
    )
)

exit /b 0

REM --- 仮想環境チェック/作成/アクティベート ---
REM 戻り値: 0=OK, 1=失敗
:CHECK_VENV
REM 既存のvenvが壊れていないか確認
if exist "!VENV_DIR!\Scripts\activate.bat" (
    call "!VENV_DIR!\Scripts\activate.bat"
    python -c "print('ok')" >nul 2>&1
    if !errorlevel! equ 0 (
        call :LOG "Existing venv activated"
        exit /b 0
    )
    REM venvが壊れている場合は再作成
    echo   !YELLOW![注意]!RESET! 仮想環境が壊れています。再作成します...
    call :LOG "Broken venv detected, recreating"
    rmdir /s /q "!VENV_DIR!"
)

REM 新規作成
echo   仮想環境を作成しています...
!PYTHON_CMD! -m venv "!VENV_DIR!"
if !errorlevel! neq 0 (
    call :LOG "Failed to create venv"
    exit /b 1
)

call "!VENV_DIR!\Scripts\activate.bat"
if !errorlevel! neq 0 (
    call :LOG "Failed to activate venv"
    exit /b 1
)

call :LOG "New venv created and activated"
echo   仮想環境を作成しました。
exit /b 0

REM --- 依存パッケージチェック/インストール ---
REM 戻り値: 0=OK, 1=失敗
:CHECK_DEPS
REM クイックチェック: 主要パッケージがimportできるか
python -c "import uvicorn; import thermo; import fastapi; import scipy" 2>nul
if !errorlevel! equ 0 (
    call :LOG "All packages already installed"
    exit /b 0
)

REM インストール実行
echo   依存パッケージをインストール中...
echo   （初回は5〜10分かかることがあります）
echo.

call :LOG "Installing packages from !REQ_FILE!"

REM pipをアップグレード
python -m pip install --upgrade pip >> "!LOG_FILE!" 2>&1

REM パッケージインストール
pip install -r "!REQ_FILE!" >> "!LOG_FILE!" 2>&1
if !errorlevel! neq 0 (
    call :LOG "Package installation failed"
    exit /b 1
)

REM 再確認
python -c "import uvicorn; import thermo; import fastapi; import scipy" 2>nul
if !errorlevel! neq 0 (
    call :LOG "Package verification failed after install"
    exit /b 1
)

call :LOG "Package installation complete"
echo   インストール完了。
exit /b 0

REM --- ポートチェック ---
REM 戻り値: 0=空き, 1=使用中
:CHECK_PORT
netstat -ano 2>nul | findstr ":!PORT! " | findstr "LISTENING" >nul 2>&1
if !errorlevel! equ 0 (
    call :LOG "Port !PORT! is in use"
    exit /b 1
)
call :LOG "Port !PORT! is available"
exit /b 0

REM --- 空きポート自動検索 ---
:FIND_FREE_PORT
for %%p in (8000 8080 8888 9000) do (
    set "PORT=%%p"
    netstat -ano 2>nul | findstr ":%%p " | findstr "LISTENING" >nul 2>&1
    if !errorlevel! neq 0 (
        call :LOG "Found free port: %%p"
        goto :eof
    )
)
REM 全て使用中の場合は最後のポートを使う
call :LOG "WARNING: No standard port available, using !PORT!"
goto :eof

REM --- ログ書き込み ---
:LOG
echo [%date% %time%] %~1 >> "!LOG_FILE!" 2>&1
goto :eof
