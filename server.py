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
import sys


def main():
    parser = argparse.ArgumentParser(description="ChemEng Local Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is not installed.")
        print("Run: pip install uvicorn")
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
