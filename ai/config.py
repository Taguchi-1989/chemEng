"""AI configuration."""

from __future__ import annotations

import os

ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
AI_MODEL: str = os.environ.get("CHEMENG_AI_MODEL", "claude-sonnet-4-20250514")
MAX_TOKENS: int = int(os.environ.get("CHEMENG_AI_MAX_TOKENS", "1024"))
MAX_HISTORY_TURNS: int = int(os.environ.get("CHEMENG_AI_MAX_HISTORY", "10"))
