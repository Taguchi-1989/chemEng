"""
ChemEng module entry point.
"""

from __future__ import annotations

import os
import sys

try:
    from .core.errors import safe_error_message
except ImportError:
    from core.errors import safe_error_message

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def _default_port() -> int:
    raw_port = os.environ.get("PORT", "8000")
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError(f"Invalid PORT environment variable: {raw_port}") from exc
    if not (1 <= port <= 65535):
        raise ValueError("PORT environment variable must be between 1 and 65535")
    return port


def _parse_port(argv: list[str]) -> int:
    port = _default_port()
    for i, arg in enumerate(argv):
        if arg in ("--port", "-p"):
            if i + 1 >= len(argv):
                raise ValueError("Port value is required after --port/-p")
            raw_port = argv[i + 1]
            try:
                port = int(raw_port)
            except ValueError as exc:
                raise ValueError(f"Invalid port: {raw_port}") from exc
            if not (1 <= port <= 65535):
                raise ValueError("Port must be between 1 and 65535")
    return port


def main() -> int:
    if "--api" in sys.argv or "api" in sys.argv:
        try:
            from interface.api import start_server

            port = _parse_port(sys.argv)
            print(f"Starting ChemEng API server on port {port}...")
            print(f"Docs: http://localhost:{port}/docs")
            start_server(port=port)
            return 0
        except Exception as exc:
            print(f"Error: {safe_error_message(exc)}", file=sys.stderr)
            return 1

    try:
        from interface.cli import main as cli_main

        cli_main()
        return 0
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        return code
    except Exception as exc:
        print(f"Error: {safe_error_message(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
