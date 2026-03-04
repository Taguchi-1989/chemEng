"""
ガス吸収塔設計テンプレート

向流ガス吸収塔の設計計算。
- Kremser式による段数・除去率計算
- NTU/HTU法
- 最小液ガス比の計算
"""

from __future__ import annotations

import math
from typing import Any


def execute(params: dict[str, Any], engine=None) -> dict[str, Any]:
    """
    ガス吸収塔設計計算を実行

    Args:
        params: 入力パラメータ
        engine: 計算エンジン（thermo）

    Returns:
        計算結果
    """
    # パラメータ取得
    gas_component = params["gas_component"]
    carrier_gas = params["carrier_gas"]
    solvent = params["solvent"]
    G = params["gas_flow_rate"]  # kmol/h (キャリアガス基準)
    y_in = params["inlet_gas_composition"]  # 入口ガス組成
    y_out = params.get("outlet_gas_composition")  # 出口ガス組成（指定時）
    L = params.get("liquid_flow_rate")  # kmol/h (溶媒基準)
    x_in = params.get("inlet_liquid_composition", 0.0)  # 入口液組成
    T = params.get("temperature", 298.15)  # K
    P = params.get("pressure", 101325.0)  # Pa
    N_specified = params.get("stages")  # 指定段数
    removal_target = params.get("removal_efficiency", 0.9)  # 目標除去率

    warnings = []
    calculation_steps = []

    # Step 1: 入力条件
    calculation_steps.append({
        "step": 1,
        "title": "入力条件 / Input Conditions",
        "description": f"{gas_component} absorption into {solvent}",
        "formulas": [
            f"吸収成分: {gas_component}",
            f"キャリアガス: {carrier_gas}",
            f"吸収液: {solvent}",
            f"ガス流量 G = {G} kmol/h",
            f"入口ガス組成 y_in = {y_in} (モル分率)",
            f"入口液組成 x_in = {x_in}",
            f"温度 T = {T} K = {T - 273.15:.1f} °C",
            f"圧力 P = {P/1000:.1f} kPa",
        ],
        "values": {"G": G, "y_in": y_in, "x_in": x_in, "T": T, "P": P},
    })

    # 入口での溶質流量（キャリアガスフリー基準）
    if y_in >= 1.0:
        return {
            "success": False,
            "errors": ["入口ガス組成 y_in は 1.0 未満である必要があります"],
        }
    solute_in = G * y_in / (1 - y_in)  # kmol/h
    calculation_steps[-1]["formulas"].append(f"入口溶質流量 = G × y_in / (1 - y_in) = {solute_in:.3f} kmol/h")

    # Step 2: ヘンリー定数の推定
    H, m = _estimate_henry_constant(
        engine, gas_component, solvent, T, P, warnings
    )

    calculation_steps.append({
        "step": 2,
        "title": "平衡関係 / Equilibrium Relationship",
        "description": "ヘンリー則: y* = m × x (希薄溶液)",
        "formulas": [
            f"ヘンリー定数 H = {H/1e6:.2f} MPa",
            f"平衡定数 m = H/P = {m:.4f}",
            "",
            "y* = m × x （気液平衡関係）",
            "(m < 1: ガスは液に溶けやすい)",
            "(m > 1: ガスは液に溶けにくい)",
        ],
        "values": {"H": H, "m": m},
    })

    if m <= 0:
        return {
            "success": False,
            "errors": ["Henry constant must be positive"],
        }

    # Step 3: 除去率と出口組成
    if y_out is not None:
        # 出口組成指定
        removal = (y_in - y_out) / y_in
    else:
        # 除去率から出口組成を計算
        removal = removal_target
        y_out = y_in * (1 - removal)

    solute_absorbed = G * (y_in - y_out)  # 吸収される溶質量

    calculation_steps.append({
        "step": 3,
        "title": "除去率と吸収量 / Removal Efficiency",
        "description": "目標除去率から出口条件を計算",
        "formulas": [
            f"除去率 η = (y_in - y_out) / y_in = {removal*100:.1f}%",
            f"入口ガス組成 y_in = {y_in}",
            f"出口ガス組成 y_out = {y_out:.6f}",
            f"吸収量 = G × (y_in - y_out) = {solute_absorbed:.3f} kmol/h",
        ],
        "values": {"removal": removal, "y_out": y_out, "absorbed": solute_absorbed},
    })

    # Step 4: 最小液ガス比
    # 平衡線の傾き m で、入口ガス組成 y_in と平衡な液組成 x_in* を求める
    x_eq_with_y_in = y_in / m  # y_in と平衡な液組成

    # 物質収支: G(y_in - y_out) = L(x_out - x_in)
    # 最小液流量は x_out = x_eq_with_y_in のとき
    if x_eq_with_y_in > x_in:
        L_min = G * (y_in - y_out) / (x_eq_with_y_in - x_in)
        LG_min = L_min / G
    else:
        L_min = float('inf')
        LG_min = float('inf')
        warnings.append("Equilibrium composition is less than inlet liquid composition")

    calculation_steps.append({
        "step": 4,
        "title": "最小液ガス比 / Minimum L/G Ratio",
        "description": "無限段での理論最小液流量",
        "formulas": [
            "最小液ガス比 (L/G)_min = G × (y_in - y_out) / (x* - x_in)",
            f"y_in と平衡な液組成 x* = y_in / m = {x_eq_with_y_in:.4f}",
            f"(L/G)_min = {LG_min:.3f}" if LG_min != float('inf') else "(L/G)_min = ∞",
            "",
            "実際の液ガス比は最小値の 1.2〜2.0 倍を使用",
        ],
        "values": {"L_min": L_min, "LG_min": LG_min},
    })

    # Step 5: 液流量の決定
    if L is None:
        # 液流量未指定時は最小の1.5倍を使用
        if LG_min != float('inf'):
            L = 1.5 * L_min
            warnings.append(f"Liquid flow rate not specified, using 1.5 × L_min = {L:.1f} kmol/h")
        else:
            return {
                "success": False,
                "errors": ["Cannot determine liquid flow rate"],
            }

    LG_ratio = L / G

    # 出口液組成
    x_out = x_in + solute_absorbed / L

    calculation_steps.append({
        "step": 5,
        "title": "操作条件 / Operating Conditions",
        "description": "液流量と物質収支",
        "formulas": [
            f"液流量 L = {L:.1f} kmol/h",
            f"液ガス比 L/G = {LG_ratio:.3f}",
            f"(L/G) / (L/G)_min = {LG_ratio/LG_min:.2f}" if LG_min != float('inf') else "",
            "",
            "物質収支: G(y_in - y_out) = L(x_out - x_in)",
            f"出口液組成 x_out = x_in + 吸収量/L = {x_out:.6f}",
        ],
        "values": {"L": L, "LG_ratio": LG_ratio, "x_out": x_out},
    })

    if LG_min != float('inf') and LG_ratio < LG_min:
        warnings.append(f"L/G ratio ({LG_ratio:.3f}) is less than minimum ({LG_min:.3f})")

    # Step 6: 吸収係数と段数計算（Kremser式）
    A = L / (m * G)  # 吸収係数

    calculation_steps.append({
        "step": 6,
        "title": "吸収係数 / Absorption Factor",
        "description": "Kremser式による計算",
        "formulas": [
            "吸収係数 A = L / (m × G)",
            f"A = {L:.1f} / ({m:.4f} × {G:.1f})",
            f"A = {A:.4f}",
            "",
            "A > 1: 効率的な吸収が可能",
            "A < 1: 吸収効率が低い",
        ],
        "values": {"A": A},
    })

    if A < 1.0:
        warnings.append(f"Absorption factor A={A:.3f} < 1: Consider increasing liquid flow rate")

    # 段数計算
    if N_specified is not None:
        # 段数指定 → 除去率を計算
        N = N_specified
        if abs(A - 1.0) < 1e-6:
            actual_removal = N / (N + 1)
        else:
            actual_removal = (A**(N+1) - A) / (A**(N+1) - 1)
        y_out_actual = y_in * (1 - actual_removal)
    else:
        # 除去率指定 → 段数を計算
        actual_removal = removal
        if abs(A - 1.0) < 1e-6:
            N = actual_removal / (1 - actual_removal)
        elif A <= 1.0:
            if actual_removal > A / (A + 1) * 1.5:
                warnings.append(f"Target removal {actual_removal:.1%} may be difficult with A={A:.3f}")
            try:
                N = math.log((1 - actual_removal) / (1 - actual_removal * A)) / math.log(A)
            except (ValueError, ZeroDivisionError):
                N = 50
        else:
            try:
                numerator = (actual_removal * (A - 1) + 1) / A
                denominator = actual_removal * (A - 1) + 1 - A * actual_removal
                if denominator > 0 and numerator > 0:
                    N = math.log(numerator / denominator) / math.log(A)
                else:
                    N = 10
            except (ValueError, ZeroDivisionError):
                N = 10

        N = max(1, min(100, N))
        y_out_actual = y_out

    N = int(round(N))

    # 再計算（整数段数での実際の除去率）
    if abs(A - 1.0) < 1e-6:
        actual_removal = N / (N + 1)
    else:
        actual_removal = (A**(N+1) - A) / (A**(N+1) - 1)

    # NTU計算（連続接触の場合）
    if abs(A - 1.0) < 1e-6:
        avg_driving_force = (y_in - m*x_out + y_out - m*x_in) / 2
        NTU = (y_in - y_out) / avg_driving_force if abs(avg_driving_force) > 1e-12 else N
    else:
        # 対数平均推進力
        delta_y1 = y_in - m * x_out  # 塔底
        delta_y2 = y_out - m * x_in  # 塔頂
        if delta_y1 > 0 and delta_y2 > 0:
            ratio = delta_y1 / delta_y2
            if abs(ratio - 1.0) < 1e-10:
                # delta_y1 ≈ delta_y2 の場合、対数平均 = 算術平均
                delta_y_lm = (delta_y1 + delta_y2) / 2
            else:
                delta_y_lm = (delta_y1 - delta_y2) / math.log(ratio)
            NTU = (y_in - y_out) / delta_y_lm * (A - 1) / A if abs(delta_y_lm) > 1e-12 else N
        else:
            NTU = N  # フォールバック

    calculation_steps.append({
        "step": 7,
        "title": "Kremser式による段数計算 / Stage Calculation",
        "description": "理論段数と移動単位数",
        "formulas": [
            "Kremser式: η = (A^(N+1) - A) / (A^(N+1) - 1)",
            f"理論段数 N = {N} 段",
            f"吸収係数 A = {A:.4f}",
            f"実際の除去率 η = {actual_removal:.4f} = {actual_removal*100:.1f}%",
            "",
            f"移動単位数 NTU ≈ {NTU:.2f}",
        ],
        "values": {"N": N, "removal": actual_removal, "NTU": NTU},
    })

    # Step 8: 物質収支まとめ
    solute_absorbed_actual = G * y_in * actual_removal
    x_out_actual = x_in + solute_absorbed_actual / L
    y_out_actual = y_in * (1 - actual_removal)

    # 出口流量
    G_out = G * (1 - y_in) / (1 - y_out_actual) if y_out_actual < 1 else G
    L_out = L + solute_absorbed_actual

    calculation_steps.append({
        "step": 8,
        "title": "物質収支 / Material Balance",
        "description": "入出力の物質収支",
        "formulas": [
            "入力:",
            f"  ガス流量 G_in = {G:.1f} kmol/h",
            f"  ガス中溶質 = {G*y_in:.3f} kmol/h",
            f"  液流量 L_in = {L:.1f} kmol/h",
            f"  液中溶質 = {L*x_in:.3f} kmol/h",
            "",
            "出力:",
            f"  出口ガス流量 = {G_out:.2f} kmol/h",
            f"  出口ガス組成 y_out = {y_out_actual:.6f}",
            f"  出口液流量 = {L_out:.2f} kmol/h",
            f"  出口液組成 x_out = {x_out_actual:.6f}",
            "",
            f"  吸収された溶質 = {solute_absorbed_actual:.3f} kmol/h",
        ],
        "values": {
            "G_out": G_out, "y_out": y_out_actual,
            "L_out": L_out, "x_out": x_out_actual,
            "absorbed": solute_absorbed_actual,
        },
    })

    return {
        "success": True,
        "outputs": {
            "absorption_factor": round(A, 4),
            "henry_constant": round(H, 0),
            "actual_stages": N,
            "ntu": round(NTU, 2),
            "removal_efficiency": round(actual_removal, 4),
            "liquid_gas_ratio": round(LG_ratio, 4),
            "min_liquid_gas_ratio": round(LG_min, 4) if LG_min != float('inf') else None,
            "outlet_gas_flow": round(G_out, 3),
            "outlet_gas_composition": round(y_out_actual, 8),
            "outlet_liquid_flow": round(L_out, 3),
            "outlet_liquid_composition": round(x_out_actual, 8),
            "absorbed_amount": round(solute_absorbed_actual, 4),
            "calculation_steps": calculation_steps,
        },
        "warnings": warnings,
    }


def _estimate_henry_constant(
    engine, gas: str, solvent: str, T: float, P: float, warnings: list[str]
) -> tuple[float, float]:
    """
    ヘンリー定数を推定

    Returns:
        (H, m): ヘンリー定数[Pa], 平衡定数 m = H/P
    """
    # 典型的なガス-水系のヘンリー定数（298K）（文献値の概算）
    # H = y*P / x [Pa] （低圧ではヘンリー則）
    HENRY_CONSTANTS_WATER = {
        # ガス: H [Pa] at 298K
        "ammonia": 5.8e5,      # よく溶ける
        "hydrogen_sulfide": 1.0e6,
        "sulfur_dioxide": 4.0e6,
        "carbon_dioxide": 1.6e8,
        "chlorine": 1.0e6,
        "hydrogen_chloride": 2.0e5,  # よく溶ける
        "oxygen": 4.3e9,
        "nitrogen": 8.5e9,
        "hydrogen": 7.1e9,
        "methane": 4.0e9,
        "ethane": 3.0e9,
        "propane": 4.0e9,
        "acetone": 3.5e6,
        "ethanol": 5.0e5,
        "methanol": 4.5e5,
    }

    # 正規化したキーで検索
    gas_key = gas.lower().replace(" ", "_")
    solvent_key = solvent.lower().replace(" ", "_")

    if solvent_key == "water" and gas_key in HENRY_CONSTANTS_WATER:
        H = HENRY_CONSTANTS_WATER[gas_key]
        # 温度補正（簡易）
        # van't Hoff式の近似（多くのガスでは温度上昇でHは増加）
        H = H * math.exp(1500 * (1/298.15 - 1/T))
    else:
        # 未知の系：デフォルト値を使用
        warnings.append(f"Using default Henry constant for {gas}/{solvent} system")
        H = 1.0e7  # 中程度の溶解性

    m = H / P  # 平衡定数
    return H, m
