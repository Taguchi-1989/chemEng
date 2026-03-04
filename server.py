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


def main():
    parser = argparse.ArgumentParser(description="ChemEng Local Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
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

    print("=" * 50)
    print("ChemEng Local Server")
    print("=" * 50)
    print(f"Starting server at http://{args.host}:{args.port}")
    print(f"API docs available at http://localhost:{args.port}/docs")
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
