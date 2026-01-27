"""
ChemEng モジュール実行エントリポイント

Usage:
    python -m chemeng                   # CLI（インタラクティブモード）
    python -m chemeng --help            # ヘルプ
    python -m chemeng property ...      # 物性値取得
    python -m chemeng calculate ...     # 計算実行
    python -m chemeng --api             # REST APIサーバー起動
"""

import sys


def main():
    # --api オプションでAPIサーバー起動
    if "--api" in sys.argv or "api" in sys.argv:
        from chemeng.interface.api import start_server

        # ポート指定
        port = 8000
        for i, arg in enumerate(sys.argv):
            if arg in ("--port", "-p") and i + 1 < len(sys.argv):
                port = int(sys.argv[i + 1])

        print(f"Starting ChemEng API server on port {port}...")
        print(f"Docs: http://localhost:{port}/docs")
        start_server(port=port)
    else:
        # CLI
        from chemeng.interface.cli import main as cli_main
        cli_main()


if __name__ == "__main__":
    main()
