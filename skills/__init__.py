"""
ChemEng スキルモジュール

計算スキル（テンプレート）を提供する。

利用可能なスキル:
- property_estimation: 物性推算
- mass_balance: 物質収支
- heat_balance: 熱収支
- distillation: 蒸留塔設計
"""

from pathlib import Path

SKILLS_DIR = Path(__file__).parent
SCHEMA_DIR = SKILLS_DIR / "schema"
TEMPLATES_DIR = SKILLS_DIR / "templates"
DEFAULTS_DIR = SKILLS_DIR / "defaults"

__all__ = [
    "SKILLS_DIR",
    "SCHEMA_DIR",
    "TEMPLATES_DIR",
    "DEFAULTS_DIR",
]
