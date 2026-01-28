"""
計算結果フォーマッター

化学工学計算結果を人が読みやすい形式で表示する。

ベストプラクティス:
- SI単位を基本とし、適切な接頭辞を使用
- 有効数字を考慮した表示
- 表形式での整理
- 単位の明示

参考:
- NIST Guide to the SI (https://www.nist.gov/pml/special-publication-811)
- Chemical Engineering unit conventions
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from chemeng.core.skill import CalculationResult


@dataclass
class UnitInfo:
    """単位情報"""
    name: str           # 単位名
    symbol: str         # 単位記号
    si_symbol: str      # SI基本単位
    factor: float = 1.0 # SI変換係数


# 物性の単位と表示設定
PROPERTY_DISPLAY = {
    # Pressure
    "vapor_pressure": {
        "name": "Vapor Pressure",
        "si_unit": "Pa",
        "display_unit": "kPa",
        "factor": 0.001,
        "precision": 2,
    },
    "pressure": {
        "name": "Pressure",
        "si_unit": "Pa",
        "display_unit": "kPa",
        "factor": 0.001,
        "precision": 1,
    },
    "critical_pressure": {
        "name": "Critical Pressure",
        "si_unit": "Pa",
        "display_unit": "MPa",
        "factor": 1e-6,
        "precision": 3,
    },
    # Temperature
    "temperature": {
        "name": "Temperature",
        "si_unit": "K",
        "display_unit": "K",
        "factor": 1.0,
        "precision": 1,
    },
    "critical_temperature": {
        "name": "Critical Temperature",
        "si_unit": "K",
        "display_unit": "K",
        "factor": 1.0,
        "precision": 1,
    },
    "boiling_point": {
        "name": "Boiling Point",
        "si_unit": "K",
        "display_unit": "K",
        "factor": 1.0,
        "precision": 1,
    },
    # Density
    "liquid_density": {
        "name": "Liquid Density",
        "si_unit": "kg/m3",
        "display_unit": "kg/m3",
        "factor": 1.0,
        "precision": 1,
    },
    "gas_density": {
        "name": "Gas Density",
        "si_unit": "kg/m3",
        "display_unit": "kg/m3",
        "factor": 1.0,
        "precision": 3,
    },
    # Viscosity
    "liquid_viscosity": {
        "name": "Liquid Viscosity",
        "si_unit": "Pa.s",
        "display_unit": "mPa.s",
        "factor": 1000,
        "precision": 3,
    },
    "gas_viscosity": {
        "name": "Gas Viscosity",
        "si_unit": "Pa.s",
        "display_unit": "uPa.s",
        "factor": 1e6,
        "precision": 2,
    },
    # Heat capacity
    "heat_capacity_liquid": {
        "name": "Liquid Heat Capacity",
        "si_unit": "J/(mol.K)",
        "display_unit": "J/(mol.K)",
        "factor": 1.0,
        "precision": 1,
    },
    "heat_capacity_gas": {
        "name": "Gas Heat Capacity",
        "si_unit": "J/(mol.K)",
        "display_unit": "J/(mol.K)",
        "factor": 1.0,
        "precision": 1,
    },
    # Thermal conductivity
    "thermal_conductivity_liquid": {
        "name": "Liquid Thermal Conductivity",
        "si_unit": "W/(m.K)",
        "display_unit": "W/(m.K)",
        "factor": 1.0,
        "precision": 3,
    },
    # Surface tension
    "surface_tension": {
        "name": "Surface Tension",
        "si_unit": "N/m",
        "display_unit": "mN/m",
        "factor": 1000,
        "precision": 2,
    },
    # Heat of vaporization
    "heat_of_vaporization": {
        "name": "Heat of Vaporization",
        "si_unit": "J/mol",
        "display_unit": "kJ/mol",
        "factor": 0.001,
        "precision": 2,
    },
    # Molecular weight
    "molecular_weight": {
        "name": "Molecular Weight",
        "si_unit": "g/mol",
        "display_unit": "g/mol",
        "factor": 1.0,
        "precision": 2,
    },
    # Flow rate
    "flow_rate": {
        "name": "Flow Rate",
        "si_unit": "kmol/h",
        "display_unit": "kmol/h",
        "factor": 1.0,
        "precision": 2,
    },
    # Heat duties
    "condenser_duty": {
        "name": "Condenser Duty",
        "si_unit": "W",
        "display_unit": "kW",
        "factor": 0.001,
        "precision": 1,
    },
    "reboiler_duty": {
        "name": "Reboiler Duty",
        "si_unit": "W",
        "display_unit": "kW",
        "factor": 0.001,
        "precision": 1,
    },
    # Dimensions
    "column_diameter": {
        "name": "Column Diameter",
        "si_unit": "m",
        "display_unit": "m",
        "factor": 1.0,
        "precision": 2,
    },
}


def format_value(value: float | None, precision: int = 3, factor: float = 1.0) -> str:
    """数値をフォーマット"""
    if value is None:
        return "-"

    converted = value * factor

    # 非常に大きいまたは小さい値は指数表記
    if abs(converted) >= 1e6 or (abs(converted) < 0.001 and converted != 0):
        return f"{converted:.{precision}e}"

    # 通常の数値
    if abs(converted) >= 1000:
        # 千単位区切り（NISTスタイル）
        formatted = f"{converted:,.{precision}f}"
        return formatted.replace(",", " ")  # カンマの代わりにスペース

    return f"{converted:.{precision}f}"


def format_property_result(result: CalculationResult) -> str:
    """物性推算結果をフォーマット"""
    if not result.success:
        return _format_error(result)

    out = result.outputs
    prop_name = out.get("property", "")
    substance = out.get("substance", "")
    value = out.get("value")
    conditions = out.get("conditions", {})

    # 表示設定を取得
    display = PROPERTY_DISPLAY.get(prop_name, {
        "name": prop_name,
        "display_unit": "",
        "factor": 1.0,
        "precision": 4,
    })

    lines = []
    lines.append("")
    lines.append("+" + "-" * 50 + "+")
    lines.append(f"|  Property Estimation Result{' ' * 22}|")
    lines.append("+" + "-" * 50 + "+")
    lines.append(f"|  Substance: {substance:<37}|")
    lines.append("+" + "-" * 50 + "+")

    # 物性値
    display_value = format_value(value, display["precision"], display["factor"])
    unit = display.get("display_unit", "")
    prop_label = display.get("name", prop_name)
    lines.append(f"|  {prop_label}: {display_value} {unit:<20}|")

    # 条件
    if conditions:
        lines.append("+" + "-" * 50 + "+")
        lines.append(f"|  Conditions:{' ' * 37}|")
        if "temperature" in conditions:
            T = conditions["temperature"]
            T_C = T - 273.15
            lines.append(f"|    Temperature: {T:.1f} K ({T_C:.1f} C){' ' * 14}|")
        if "pressure" in conditions:
            P = conditions["pressure"]
            lines.append(f"|    Pressure: {P/1000:.1f} kPa{' ' * 25}|")

    lines.append("+" + "-" * 50 + "+")

    return "\n".join(lines)


def format_mass_balance_result(result: CalculationResult) -> str:
    """物質収支結果をフォーマット"""
    if not result.success:
        return _format_error(result)

    out = result.outputs

    lines = []
    lines.append("")
    lines.append("+" + "=" * 60 + "+")
    lines.append("|" + "  Mass Balance Result".center(60) + "|")
    lines.append("+" + "=" * 60 + "+")

    # 入口
    inlet = out.get("inlet_total", {})
    lines.append("|  [Inlet]" + " " * 51 + "|")
    lines.append(f"|    Total flow: {inlet.get('flow_rate', 0):.2f} mol/s" + " " * 30 + "|")

    inlet_comp = inlet.get("composition", {})
    if inlet_comp:
        lines.append("|    Composition:" + " " * 44 + "|")
        for comp, frac in inlet_comp.items():
            pct = frac * 100
            bar_filled = int(pct / 5)
            bar = "#" * bar_filled + "." * (20 - bar_filled)
            lines.append(f"|      {comp:<10} [{bar}] {pct:5.1f}%" + " " * 6 + "|")

    lines.append("+" + "-" * 60 + "+")

    # 出口ストリーム
    outlet_streams = out.get("outlet_streams", [])
    lines.append("|  [Outlet]" + " " * 50 + "|")

    for stream in outlet_streams:
        name = stream.get("name", "Stream")
        flow = stream.get("flow_rate", 0)
        comp = stream.get("composition", {})

        lines.append(f"|    {name}:" + " " * (55 - len(name)) + "|")
        lines.append(f"|      Flow: {flow:.2f} mol/s" + " " * 36 + "|")

        if comp:
            for c, frac in comp.items():
                pct = frac * 100
                bar_filled = int(pct / 5)
                bar = "#" * bar_filled + "." * (20 - bar_filled)
                lines.append(f"|      {c:<10} [{bar}] {pct:5.1f}%" + " " * 6 + "|")
        lines.append("|" + " " * 60 + "|")

    # 収支チェック
    closure = out.get("closure", 100)
    lines.append("+" + "-" * 60 + "+")
    status = "[OK]" if closure >= 99.9 else "[!]"
    lines.append(f"|  Mass closure: {closure:.2f}% {status}" + " " * 35 + "|")

    lines.append("+" + "=" * 60 + "+")

    return "\n".join(lines)


def format_distillation_result(result: CalculationResult) -> str:
    """蒸留塔設計結果をフォーマット"""
    if not result.success:
        return _format_error(result)

    out = result.outputs

    lines = []
    lines.append("")
    lines.append("+" + "=" * 60 + "+")
    lines.append("|" + "  Distillation Column Design".center(60) + "|")
    lines.append("+" + "=" * 60 + "+")

    # 設計パラメータ
    lines.append("|  [Design Parameters]" + " " * 39 + "|")

    alpha = out.get("relative_volatility", 0)
    lines.append(f"|    Relative volatility a : {alpha:.2f}" + " " * 27 + "|")

    R_min = out.get("minimum_reflux_ratio", 0)
    R = out.get("actual_reflux_ratio", 0)
    lines.append(f"|    Min reflux ratio Rmin : {R_min:.3f}" + " " * 26 + "|")
    r_ratio = R / R_min if R_min > 0 else 0
    lines.append(f"|    Actual reflux ratio R : {R:.3f} (= {r_ratio:.2f} x Rmin)" + " " * 10 + "|")

    N_min = out.get("minimum_stages", 0)
    N = out.get("actual_stages", 0)
    feed = out.get("feed_stage", 0)
    lines.append(f"|    Min stages Nmin      : {N_min}" + " " * 30 + "|")
    lines.append(f"|    Theoretical stages N : {N} (incl. reboiler)" + " " * 16 + "|")
    lines.append(f"|    Feed stage           : {feed} (from bottom)" + " " * 16 + "|")

    lines.append("+" + "-" * 60 + "+")

    # 物質収支
    lines.append("|  [Material Balance]" + " " * 40 + "|")
    D = out.get("distillate_flow_rate", 0)
    B = out.get("bottoms_flow_rate", 0)
    F = D + B

    lines.append(f"|    Feed (F)       : {F:.1f} kmol/h" + " " * 26 + "|")
    d_pct = D / F * 100 if F > 0 else 0
    b_pct = B / F * 100 if F > 0 else 0
    lines.append(f"|    Distillate (D) : {D:.1f} kmol/h ({d_pct:.1f}%)" + " " * 15 + "|")
    lines.append(f"|    Bottoms (B)    : {B:.1f} kmol/h ({b_pct:.1f}%)" + " " * 15 + "|")

    lines.append("+" + "-" * 60 + "+")

    # 熱負荷
    lines.append("|  [Heat Duties]" + " " * 45 + "|")
    Qc = out.get("condenser_duty", 0)
    Qr = out.get("reboiler_duty", 0)

    if Qc > 1000:
        lines.append(f"|    Condenser Qc : {Qc/1000:.1f} MW" + " " * 32 + "|")
    else:
        lines.append(f"|    Condenser Qc : {Qc:.1f} kW" + " " * 32 + "|")

    if Qr > 1000:
        lines.append(f"|    Reboiler Qr  : {Qr/1000:.1f} MW" + " " * 32 + "|")
    else:
        lines.append(f"|    Reboiler Qr  : {Qr:.1f} kW" + " " * 32 + "|")

    # 塔径
    diameter = out.get("column_diameter", 0)
    if diameter:
        lines.append("+" + "-" * 60 + "+")
        lines.append("|  [Column Dimensions (estimate)]" + " " * 27 + "|")
        lines.append(f"|    Diameter : {diameter:.2f} m" + " " * 37 + "|")

    lines.append("+" + "=" * 60 + "+")

    # 警告
    if result.warnings:
        lines.append("")
        lines.append("[!] Warnings:")
        for w in result.warnings:
            lines.append(f"  * {w}")

    return "\n".join(lines)


def format_result(result: CalculationResult) -> str:
    """結果を自動判定してフォーマット"""
    skill_id = result.skill_id

    if skill_id == "property_estimation":
        return format_property_result(result)
    elif skill_id == "mass_balance":
        return format_mass_balance_result(result)
    elif skill_id == "distillation":
        return format_distillation_result(result)
    else:
        return _format_generic(result)


def _format_error(result: CalculationResult) -> str:
    """エラー結果をフォーマット"""
    lines = []
    lines.append("")
    lines.append("+" + "-" * 50 + "+")
    lines.append("|  [ERROR] Calculation Failed" + " " * 22 + "|")
    lines.append("+" + "-" * 50 + "+")
    for err in result.errors:
        # 長いエラーメッセージは折り返す
        if len(err) > 46:
            lines.append(f"|  {err[:46]}|")
            lines.append(f"|  {err[46:]:<48}|")
        else:
            lines.append(f"|  {err:<48}|")
    lines.append("+" + "-" * 50 + "+")
    return "\n".join(lines)


def _format_generic(result: CalculationResult) -> str:
    """汎用フォーマット"""
    if not result.success:
        return _format_error(result)

    lines = []
    lines.append("")
    lines.append(f"=== {result.skill_id} 計算結果 ===")
    lines.append("")

    for key, value in result.outputs.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for k, v in value.items():
                lines.append(f"  {k}: {v}")
        elif isinstance(value, float):
            lines.append(f"{key}: {value:.4g}")
        else:
            lines.append(f"{key}: {value}")

    if result.warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in result.warnings:
            lines.append(f"  * {w}")

    return "\n".join(lines)


# 便利関数
def print_result(result: CalculationResult):
    """結果を表示（エンコーディング対応）"""
    import sys
    text = format_result(result)
    try:
        print(text)
    except UnicodeEncodeError:
        # Windows cp932 等で文字化けする場合、ASCII互換で出力
        print(text.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
