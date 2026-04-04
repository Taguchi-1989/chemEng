"""
ChemEng Local Server

ローカルPC上でFastAPIサーバーを起動するエントリーポイント。
ngrokと組み合わせて外部からアクセス可能にする。

Usage:
    python server.py
    python server.py --port 8000
    python server.py --host 0.0.0.0 --port 8000
"""

import argparse
import os
import sys

# プロジェクトルートを sys.path に追加（どのディレクトリから起動しても動作するように）
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# .env ファイルから環境変数を読み込み（ローカル開発用）
_env_file = os.path.join(_PROJECT_ROOT, ".env")
if os.path.exists(_env_file):
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_file)
    except ImportError:
        # python-dotenv がなくても .env を手動パース
        with open(_env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and not os.environ.get(key):
                        os.environ[key] = value


def _default_port() -> int:
    raw_port = os.environ.get("PORT", "8000")
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError(f"Invalid PORT environment variable: {raw_port}") from exc
    if not (1 <= port <= 65535):
        raise ValueError("PORT environment variable must be between 1 and 65535")
    return port


def _default_host() -> str:
    return os.environ.get("HOST", "0.0.0.0")


def main():
    parser = argparse.ArgumentParser(description="ChemEng Local Server")
    parser.add_argument("--host", default=_default_host(), help="Host to bind")
    parser.add_argument("--port", type=int, default=_default_port(), help="Port to bind")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is not installed.")
        print("Run: pip install uvicorn")
        sys.exit(1)

    # コア依存パッケージの確認
    missing = []
    for pkg in ["fastapi", "yaml", "pydantic"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"Error: Required packages not installed: {', '.join(missing)}")
        print("Run: pip install -r requirements_full.txt")
        sys.exit(1)

    # AI機能の状態チェック
    ai_key = os.environ.get("ANTHROPIC_API_KEY", "")
    ai_status = "Enabled" if ai_key and not ai_key.startswith("sk-ant-api03-xxxxx") else "Disabled (set ANTHROPIC_API_KEY in .env)"

    print("=" * 50)
    print("ChemEng Local Server")
    print("=" * 50)
    print(f"  Server:  http://{args.host}:{args.port}")
    print(f"  API docs: http://localhost:{args.port}/docs")
    print(f"  AI chat:  {ai_status}")
    print()
    print("To expose to internet, run in another terminal:")
    print(f"  ngrok http {args.port}")
    print("=" * 50)

    uvicorn.run(
        "interface.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
