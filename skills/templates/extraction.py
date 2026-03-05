"""
液液抽出設計テンプレート

向流多段抽出の設計計算。
- Kremser式による段数・抽出率計算
"""

from __future__ import annotations

import math
from typing import Any


def execute(params: dict[str, Any], engine=None) -> dict[str, Any]:
    """
    液液抽出設計計算を実行

    Args:
        params: 入力パラメータ
        engine: 計算エンジン（thermo）

    Returns:
        計算結果
    """
    # パラメータ取得
    solute = params["solute"]
    carrier = params["carrier"]
    solvent = params["solvent"]
    F = params["feed_flow_rate"]  # kmol/h (キャリア+溶質)
    xF = params["feed_composition"]  # 原料中の溶質モル分率
    S = params["solvent_flow_rate"]  # kmol/h (抽剤)
    yS = params.get("solvent_purity", 0.0)  # 抽剤中の溶質モル分率
    T = params.get("temperature", 298.15)  # K
    P = params.get("pressure", 101325.0)  # Pa
    N_specified = params.get("stages")  # 指定段数
    recovery_target = params.get("recovery", 0.9)  # 目標抽出率
    # 極端な抽出率をclamp
    if recovery_target > 0.9999:
        recovery_target = 0.9999

    warnings = []
    calculation_steps = []

    # Step 1: 入力条件
    calculation_steps.append({
        "step": 1,
        "title": "入力条件 / Input Conditions",
        "description": f"{solute} extraction from {carrier} using {solvent}",
        "formulas": [
            f"溶質: {solute}",
            f"キャリア: {carrier}",
            f"抽剤: {solvent}",
            f"原料流量 F = {F} kmol/h",
            f"原料組成 xF = {xF} (溶質モル分率)",
            f"抽剤流量 S = {S} kmol/h",
            f"抽剤組成 yS = {yS}",
            f"温度 T = {T} K = {T - 273.15:.1f} °C",
        ],
        "values": {"F": F, "xF": xF, "S": S, "yS": yS, "T": T},
    })

    # 溶質流量
    F_solute = F * xF  # kmol/h
    F_carrier = F * (1 - xF)  # kmol/h

    # Step 2: 分配係数の推定
    m = _estimate_distribution_coefficient(
        engine, solute, carrier, solvent, T, P, warnings
    )

    calculation_steps.append({
        "step": 2,
        "title": "分配係数 / Distribution Coefficient",
        "description": "平衡関係 y* = m × x",
        "formulas": [
            "分配係数 m = (エキストラクト相中の溶質濃度) / (ラフィネート相中の溶質濃度)",
            f"m = {m:.3f}",
            "(m > 1: 抽剤への溶質の親和性が高い)",
        ],
        "values": {"m": m},
    })

    if m <= 0:
        return {
            "success": False,
            "errors": ["Distribution coefficient must be positive"],
        }

    # Step 3: 抽出係数の計算
    E = m * S / F  # 抽出係数

    calculation_steps.append({
        "step": 3,
        "title": "抽出係数 / Extraction Factor",
        "description": "操作条件から抽出係数を計算",
        "formulas": [
            "E = m × S / F",
            f"E = {m:.3f} × {S} / {F}",
            f"E = {E:.4f}",
            "",
            "E > 1: 効率的な抽出が可能",
            "E < 1: 抽出効率が低い",
        ],
        "values": {"E": E},
    })

    if E < 1.0:
        warnings.append(f"Extraction factor E={E:.3f} < 1: Consider increasing solvent flow rate")

    # Step 4: 段数と抽出率の計算（Kremser式）
    if N_specified is not None:
        # 段数指定 → 抽出率を計算
        N = N_specified
        if abs(E - 1.0) < 1e-6:
            # E ≈ 1 の特殊ケース
            recovery = N / (N + 1)
        else:
            # Kremser式
            recovery = (E**(N+1) - E) / (E**(N+1) - 1)
    else:
        # 抽出率指定 → 段数を計算
        recovery = recovery_target
        if abs(E - 1.0) < 1e-6:
            # E ≈ 1 の特殊ケース
            N = recovery / (1 - recovery)
        elif E <= 1.0:
            # E < 1 では目標抽出率に到達困難
            if recovery > E / (E + 1) * 1.5:
                warnings.append(f"Target recovery {recovery:.1%} may be difficult with E={E:.3f}")
            try:
                log_arg = (1 - recovery) / (1 - recovery * E)
                if log_arg <= 0 or recovery >= 1:
                    N = 50
                else:
                    N = math.log(log_arg) / math.log(E)
            except (ValueError, ZeroDivisionError):
                N = 50
        else:
            # Kremser式の逆算
            # recovery = (E^(N+1) - E) / (E^(N+1) - 1)
            # 解くと: N = log[(recovery - 1/E) / (recovery - 1)] / log(E) - 1
            try:
                numerator = (recovery * (E - 1) + 1) / E
                denominator = recovery * (E - 1) + 1 - E * recovery
                if denominator > 0 and numerator > 0:
                    N = math.log(numerator / denominator) / math.log(E)
                else:
                    N = 10  # フォールバック
            except (ValueError, ZeroDivisionError):
                N = 10

        N = max(1, min(50, N))

    N = int(round(N))

    # 再計算（整数段数での実際の抽出率）
    if abs(E - 1.0) < 1e-6:
        actual_recovery = N / (N + 1)
    else:
        actual_recovery = (E**(N+1) - E) / (E**(N+1) - 1)

    calculation_steps.append({
        "step": 4,
        "title": "Kremser式による計算 / Kremser Equation",
        "description": "段数と抽出率の関係",
        "formulas": [
            "抽出率 φ = (E^(N+1) - E) / (E^(N+1) - 1)",
            f"N = {N} 段",
            f"E = {E:.4f}",
            f"φ = {actual_recovery:.4f} = {actual_recovery*100:.1f}%",
        ],
        "values": {"N": N, "recovery": actual_recovery},
    })

    # Step 5: 物質収支
    solute_extracted = F_solute * actual_recovery  # 抽出される溶質
    solute_remaining = F_solute * (1 - actual_recovery)  # 残留する溶質

    # ラフィネート（抽出後の原料側）
    R_flow = F_carrier + solute_remaining  # キャリア + 残留溶質
    xR = solute_remaining / R_flow if R_flow > 0 else 0  # ラフィネート中の溶質モル分率

    # エキストラクト（溶質を含む抽剤側）
    E_flow = S + solute_extracted  # 抽剤 + 抽出溶質
    yE = solute_extracted / E_flow if E_flow > 0 else 0  # エキストラクト中の溶質モル分率

    calculation_steps.append({
        "step": 5,
        "title": "物質収支 / Material Balance",
        "description": "入出力の物質収支",
        "formulas": [
            "入力:",
            f"  原料中の溶質 = {F_solute:.3f} kmol/h",
            f"  抽剤中の溶質 = {S * yS:.3f} kmol/h",
            "",
            "出力:",
            f"  ラフィネート流量 R = {R_flow:.3f} kmol/h",
            f"  ラフィネート組成 xR = {xR:.4f}",
            f"  エキストラクト流量 E = {E_flow:.3f} kmol/h",
            f"  エキストラクト組成 yE = {yE:.4f}",
            "",
            f"  抽出された溶質 = {solute_extracted:.3f} kmol/h",
            f"  残留した溶質 = {solute_remaining:.3f} kmol/h",
        ],
        "values": {
            "R_flow": R_flow, "xR": xR,
            "E_flow": E_flow, "yE": yE,
        },
    })

    return {
        "success": True,
        "outputs": {
            "extraction_factor": round(E, 4),
            "distribution_coefficient": round(m, 4),
            "actual_stages": N,
            "recovery": round(actual_recovery, 4),
            "raffinate_flow_rate": round(R_flow, 3),
            "raffinate_composition": round(xR, 6),
            "extract_flow_rate": round(E_flow, 3),
            "extract_composition": round(yE, 6),
            "solute_in_raffinate": round(solute_remaining, 4),
            "solute_in_extract": round(solute_extracted, 4),
            "calculation_steps": calculation_steps,
        },
        "warnings": warnings,
    }


def _estimate_distribution_coefficient(
    engine, solute: str, carrier: str, solvent: str,
    T: float, P: float, warnings: list[str]
) -> float:
    """
    分配係数を推定

    簡易的に典型的な系の値を使用。
    将来的にはthermoライブラリのLLE計算を統合。
    """
    # 典型的な系の分配係数（文献値の概算）
    KNOWN_SYSTEMS = {
        # (溶質, キャリア, 抽剤): m
        ("acetic_acid", "water", "ethyl_acetate"): 0.5,
        ("acetic_acid", "water", "diethyl_ether"): 0.4,
        ("acetic_acid", "water", "isopropanol"): 1.2,
        ("acetone", "water", "toluene"): 1.5,
        ("acetone", "water", "chloroform"): 2.0,
        ("ethanol", "water", "hexane"): 0.3,
        ("phenol", "water", "benzene"): 2.3,
        ("phenol", "water", "toluene"): 2.0,
        ("aniline", "water", "toluene"): 15.0,
        ("aniline", "water", "benzene"): 20.0,
    }

    # 正規化したキーで検索
    key = (solute.lower(), carrier.lower(), solvent.lower())

    if key in KNOWN_SYSTEMS:
        m = KNOWN_SYSTEMS[key]
        return m

    # 未知の系：デフォルト値を使用
    warnings.append(f"Using default distribution coefficient for {solute}/{carrier}/{solvent} system")

    # 極性に基づく簡易推定
    # 有機溶媒への抽出を想定してデフォルトm=1.0
    return 1.0
