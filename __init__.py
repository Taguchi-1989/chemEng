"""
ChemEng - 化学工学計算モジュール

AI対話ベースで要件を収集し、OSSライブラリ（thermo, Cantera, CoolProp）で
化学工学計算を実行するモジュール。

主な機能:
- 物性推算（蒸気圧、密度、粘度、熱容量など）
- 物質収支・熱収支計算
- 単位操作設計（蒸留塔、熱交換器、反応器）
- 反応工学（反応速度、化学平衡）
"""

__version__ = "0.1.0"
__author__ = "WalkTalk Hub Team"

from .core.registry import SkillRegistry, execute_skill, get_registry
from .core.requirement import CalculationType, Condition, RequirementSpec, Substance
from .core.skill import CalculationResult, ParameterSchema, SkillDefinition

__all__ = [
    "RequirementSpec",
    "Substance",
    "Condition",
    "CalculationType",
    "SkillDefinition",
    "ParameterSchema",
    "CalculationResult",
    "SkillRegistry",
    "get_registry",
    "execute_skill",
]
