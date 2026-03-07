"""
単位変換ユーティリティ

外部ソース（PubChem等）の混在単位をSI単位に変換する。
"""

from __future__ import annotations

import re


def to_kelvin(value: float, from_unit: str) -> float:
    """温度をケルビンに変換"""
    u = from_unit.strip().lower().replace("°", "").replace("deg", "")
    if u in ("k", "kelvin"):
        return value
    if u in ("c", "celsius", "degc"):
        return value + 273.15
    if u in ("f", "fahrenheit", "degf"):
        return (value - 32) * 5 / 9 + 273.15
    raise ValueError(f"Unknown temperature unit: {from_unit}")


def to_pascal(value: float, from_unit: str) -> float:
    """圧力をパスカルに変換"""
    conversions = {
        "pa": 1.0,
        "kpa": 1000.0,
        "mpa": 1e6,
        "gpa": 1e9,
        "atm": 101325.0,
        "bar": 1e5,
        "mbar": 100.0,
        "mmhg": 133.322,
        "torr": 133.322,
        "psi": 6894.76,
        "inhg": 3386.39,
    }
    u = from_unit.strip().lower()
    factor = conversions.get(u)
    if factor is None:
        raise ValueError(f"Unknown pressure unit: {from_unit}")
    return value * factor


def to_kg_per_m3(value: float, from_unit: str) -> float:
    """密度をkg/m³に変換"""
    conversions = {
        "kg/m3": 1.0,
        "kg/m³": 1.0,
        "g/cm3": 1000.0,
        "g/cm³": 1000.0,
        "g/ml": 1000.0,
        "g/l": 1.0,
        "kg/l": 1000.0,
        "lb/ft3": 16.0185,
    }
    u = from_unit.strip().lower()
    factor = conversions.get(u)
    if factor is None:
        raise ValueError(f"Unknown density unit: {from_unit}")
    return value * factor


def to_pa_s(value: float, from_unit: str) -> float:
    """粘度をPa·sに変換"""
    conversions = {
        "pa·s": 1.0,
        "pa*s": 1.0,
        "pa.s": 1.0,
        "pas": 1.0,
        "mpa·s": 1e-3,
        "mpa*s": 1e-3,
        "mpas": 1e-3,
        "cp": 1e-3,
        "centipoise": 1e-3,
        "p": 0.1,
        "poise": 0.1,
    }
    u = from_unit.strip().lower()
    factor = conversions.get(u)
    if factor is None:
        raise ValueError(f"Unknown viscosity unit: {from_unit}")
    return value * factor


def to_j_per_mol(value: float, from_unit: str) -> float:
    """エネルギーをJ/molに変換"""
    conversions = {
        "j/mol": 1.0,
        "kj/mol": 1000.0,
        "cal/mol": 4.184,
        "kcal/mol": 4184.0,
        "btu/lbmol": 2326.0,
    }
    u = from_unit.strip().lower()
    factor = conversions.get(u)
    if factor is None:
        raise ValueError(f"Unknown energy unit: {from_unit}")
    return value * factor


def to_n_per_m(value: float, from_unit: str) -> float:
    """表面張力をN/mに変換"""
    conversions = {
        "n/m": 1.0,
        "mn/m": 1e-3,
        "dyn/cm": 1e-3,
        "dyne/cm": 1e-3,
    }
    u = from_unit.strip().lower()
    factor = conversions.get(u)
    if factor is None:
        raise ValueError(f"Unknown surface tension unit: {from_unit}")
    return value * factor


# 物性名→変換関数のマッピング
PROPERTY_CONVERTERS = {
    "boiling_point": ("K", to_kelvin),
    "melting_point": ("K", to_kelvin),
    "flash_point": ("K", to_kelvin),
    "autoignition_temperature": ("K", to_kelvin),
    "critical_temperature": ("K", to_kelvin),
    "vapor_pressure": ("Pa", to_pascal),
    "critical_pressure": ("Pa", to_pascal),
    "liquid_density": ("kg/m³", to_kg_per_m3),
    "gas_density": ("kg/m³", to_kg_per_m3),
    "density": ("kg/m³", to_kg_per_m3),
    "liquid_viscosity": ("Pa·s", to_pa_s),
    "gas_viscosity": ("Pa·s", to_pa_s),
    "viscosity": ("Pa·s", to_pa_s),
    "heat_of_vaporization": ("J/mol", to_j_per_mol),
    "heat_of_combustion": ("J/mol", to_j_per_mol),
    "surface_tension": ("N/m", to_n_per_m),
}


def convert_to_si(
    value: float, from_unit: str, property_name: str
) -> tuple[float, str]:
    """物性値をSI単位に変換

    Args:
        value: 元の値
        from_unit: 元の単位
        property_name: 物性名

    Returns:
        (SI単位の値, SI単位文字列)
    """
    entry = PROPERTY_CONVERTERS.get(property_name)
    if entry is None:
        return value, from_unit

    si_unit, converter = entry
    try:
        return converter(value, from_unit), si_unit
    except ValueError:
        # 変換できない場合はそのまま返す
        return value, from_unit


def parse_value_with_unit(text: str) -> tuple[float | None, str]:
    """テキストから数値と単位を抽出

    PubChem等が返す "0.7893 g/cu cm" のような文字列をパースする。

    Returns:
        (数値, 単位文字列) or (None, "") if parse fails
    """
    text = text.strip()
    if not text:
        return None, ""

    # "0.7893 g/cu cm" -> value=0.7893, unit="g/cu cm"
    # "-33.34 °C" -> value=-33.34, unit="°C"
    match = re.match(r"([+-]?\d+\.?\d*(?:[eE][+-]?\d+)?)\s*(.*)", text)
    if match:
        try:
            value = float(match.group(1))
            unit = match.group(2).strip()
            # "g/cu cm" -> "g/cm3" の正規化
            unit = _normalize_unit_string(unit)
            return value, unit
        except ValueError:
            pass

    return None, ""


def _normalize_unit_string(unit: str) -> str:
    """単位文字列の正規化"""
    replacements = {
        "g/cu cm": "g/cm3",
        "g/cu.cm": "g/cm3",
        "kg/cu m": "kg/m3",
        "mm hg": "mmHg",
        "mm Hg": "mmHg",
        "deg c": "°C",
        "deg C": "°C",
        "deg f": "°F",
        "deg F": "°F",
    }
    for old, new in replacements.items():
        if old in unit.lower() or old in unit:
            return new
    return unit
