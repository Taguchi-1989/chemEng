"""
ChemEng AI Module

AI統合: ヘルプチャットとパラメータ提案
"""

from __future__ import annotations

from .chat import ChemEngAssistant
from .config import AI_MODEL, MAX_HISTORY_TURNS, MAX_TOKENS
from .suggest import suggest_parameters

__all__ = [
    "ChemEngAssistant",
    "suggest_parameters",
    "AI_MODEL",
    "MAX_TOKENS",
    "MAX_HISTORY_TURNS",
]
