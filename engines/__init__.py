"""
ChemEng 計算エンジンモジュール

利用可能なOSSライブラリのラッパーを提供。

エンジン:
- thermo: 物性推算、VLE（30,000+化合物）
- cantera: 反応速度、化学平衡、燃焼
- coolprop: 冷媒・純物質の高精度物性（120+流体）
"""

from __future__ import annotations

import logging

from .base import (
    CalculationEngine,
    ConditionsOutOfRangeError,
    EngineCapability,
    EngineError,
    PropertyNotAvailableError,
    SubstanceNotFoundError,
)

__all__ = [
    "CalculationEngine",
    "EngineCapability",
    "EngineError",
    "SubstanceNotFoundError",
    "PropertyNotAvailableError",
    "ConditionsOutOfRangeError",
    "get_available_engines",
    "get_engine",
    "select_engine",
]

# 冷媒リスト（CoolProp優先）
REFRIGERANTS = {
    "r134a", "r410a", "r32", "r22", "r404a", "r407c", "r507a",
    "r717", "r744", "r290", "r600a", "ammonia", "co2", "propane",
}

# 燃焼・反応用物質（Cantera優先）
COMBUSTION_SPECIES = {
    "ch4", "methane", "c2h6", "ethane", "c3h8", "propane",
    "h2", "hydrogen", "co", "co2", "no", "no2", "n2o",
}

logger = logging.getLogger("chemeng")


def get_available_engines() -> list[CalculationEngine]:
    """利用可能な計算エンジンを取得"""
    engines = []

    try:
        from .thermo_engine import ThermoEngine
        engine = ThermoEngine()
        if engine.is_available():
            engines.append(engine)
    except ImportError:
        logger.debug("thermo engine not available (thermo/chemicals not installed)")

    try:
        from .cantera_engine import CanteraEngine
        engine = CanteraEngine()
        if engine.is_available():
            engines.append(engine)
    except ImportError:
        logger.debug("cantera engine not available (cantera not installed)")

    try:
        from .coolprop_engine import CoolPropEngine
        engine = CoolPropEngine()
        if engine.is_available():
            engines.append(engine)
    except ImportError:
        logger.debug("coolprop engine not available (CoolProp not installed)")

    return engines


def get_engine(name: str) -> CalculationEngine | None:
    """名前でエンジンを取得"""
    for engine in get_available_engines():
        if engine.name == name:
            return engine
    return None


def select_engine(
    substance: str | list[str] | None = None,
    calculation_type: str | None = None,
    property_name: str | None = None,
) -> CalculationEngine | None:
    """
    条件に基づいて最適なエンジンを自動選択

    Args:
        substance: 物質名または物質リスト
        calculation_type: 計算タイプ
        property_name: 物性名

    Returns:
        最適なエンジン、または None
    """
    engines = get_available_engines()
    if not engines:
        return None

    # 物質名を正規化
    substances = []
    if substance:
        if isinstance(substance, str):
            substances = [substance.lower()]
        else:
            substances = [s.lower() for s in substance]

    # 1. 計算タイプによる選択
    if calculation_type:
        calc_type = calculation_type.lower()

        # 燃焼・反応速度 → Cantera
        if calc_type in ("kinetics", "combustion", "adiabatic_flame", "reactor"):
            cantera = get_engine("cantera")
            if cantera:
                return cantera

        # 冷凍サイクル → CoolProp
        if calc_type in ("refrigeration_cycle", "saturation"):
            coolprop = get_engine("coolprop")
            if coolprop:
                return coolprop

        # VLE・混合物 → thermo
        if calc_type in ("vle", "lle", "flash", "bubble_point", "dew_point"):
            thermo = get_engine("thermo")
            if thermo:
                return thermo

    # 2. 物質による選択
    if substances:
        # 冷媒 → CoolProp
        if any(s in REFRIGERANTS for s in substances):
            coolprop = get_engine("coolprop")
            if coolprop:
                return coolprop

        # 燃焼関連物質 → Cantera
        if any(s in COMBUSTION_SPECIES for s in substances):
            cantera = get_engine("cantera")
            if cantera:
                return cantera

    # 3. 物性による選択
    if property_name:
        prop = property_name.lower()

        # 高精度が必要な物性 → CoolProp
        if prop in ("saturation_temperature", "vapor_pressure", "quality"):
            coolprop = get_engine("coolprop")
            if coolprop:
                return coolprop

    # 4. デフォルト: thermo（最も汎用的）
    thermo = get_engine("thermo")
    if thermo:
        return thermo

    # フォールバック: 最初の利用可能なエンジン
    return engines[0] if engines else None
