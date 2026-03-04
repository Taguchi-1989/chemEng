"""
蒸留塔設計テンプレート

二成分系蒸留塔の設計計算。
- McCabe-Thiele法（段数計算）
- Fenske-Underwood-Gilliland法（簡易法）
"""

from __future__ import annotations

import math
from typing import Any


def execute(params: dict[str, Any], engine=None) -> dict[str, Any]:
    """
    蒸留塔設計計算を実行

    Args:
        params: 入力パラメータ
        engine: 計算エンジン（thermo）

    Returns:
        計算結果
    """
    # パラメータ取得
    light_comp = params["light_component"]
    heavy_comp = params["heavy_component"]
    F = params["feed_flow_rate"]  # kmol/h
    zF = params["feed_composition"]
    T_feed = params.get("feed_temperature", 350.0)
    q = params.get("feed_condition", 1.0)
    P = params.get("column_pressure", 101325.0)
    xD = params["distillate_purity"]
    xB_heavy = params["bottoms_purity"]
    R_factor = params.get("reflux_ratio_factor", 1.3)

    # xB は軽沸成分のモル分率
    xB = 1.0 - xB_heavy

    warnings = []
    calculation_steps = []  # 計算過程を記録

    # Step 1: 入力条件
    calculation_steps.append({
        "step": 1,
        "title": "入力条件 / Input Conditions",
        "description": f"{light_comp}/{heavy_comp} 系",
        "formulas": [
            f"原料流量 F = {F} kmol/h",
            f"原料組成 zF = {zF} (軽沸成分モル分率)",
            f"留出液純度 xD = {xD}",
            f"缶出液純度 xB_heavy = {xB_heavy} → xB = {xB:.4f} (軽沸)",
            f"原料温度 T = {T_feed} K",
            f"原料状態 q = {q} (1=飽和液, 0=飽和蒸気)",
            f"操作圧力 P = {P} Pa = {P/1000:.1f} kPa",
        ],
        "values": {"F": F, "zF": zF, "xD": xD, "xB": xB, "T_feed": T_feed, "q": q, "P": P},
    })

    # 入力検証
    if zF >= xD:
        return {
            "success": False,
            "errors": [f"Feed composition ({zF}) must be less than distillate purity ({xD})"],
        }
    if zF <= xB:
        return {
            "success": False,
            "errors": [f"Feed composition ({zF}) must be greater than bottoms light component ({xB})"],
        }

    # エンジン取得
    if engine is None:
        try:
            from core.compat import get_thermo_engine
            engine = get_thermo_engine()
        except ImportError:
            # エンジンなしでも相対揮発度を仮定して計算可能
            warnings.append("Engine not available, using assumed relative volatility")
            engine = None

    # Step 2: 相対揮発度の計算
    alpha = _calculate_relative_volatility(
        engine, light_comp, heavy_comp, T_feed, P, zF, warnings
    )

    calculation_steps.append({
        "step": 2,
        "title": "相対揮発度 / Relative Volatility",
        "description": "VLE計算から相対揮発度を算出",
        "formulas": [
            "α = K_light / K_heavy",
            f"α = {alpha:.3f}",
            "（α > 1 で蒸留分離が可能）",
        ],
        "values": {"alpha": alpha},
    })

    if alpha <= 1.0:
        return {
            "success": False,
            "errors": [f"Relative volatility ({alpha:.3f}) must be > 1 for separation"],
        }

    if alpha < 1.1:
        warnings.append(f"Low relative volatility ({alpha:.3f}) - separation will be difficult")

    # Step 3: 物質収支
    D = F * (zF - xB) / (xD - xB)  # 留出液流量
    B = F - D  # 缶出液流量

    calculation_steps.append({
        "step": 3,
        "title": "物質収支 / Material Balance",
        "description": "全物質収支 + 成分収支",
        "formulas": [
            "全物質収支: F = D + B",
            "成分収支: F·zF = D·xD + B·xB",
            "",
            "D = F × (zF - xB) / (xD - xB)",
            f"D = {F} × ({zF} - {xB:.4f}) / ({xD} - {xB:.4f})",
            f"D = {F} × {zF - xB:.4f} / {xD - xB:.4f}",
            f"D = {D:.3f} kmol/h",
            "",
            "B = F - D",
            f"B = {F} - {D:.3f}",
            f"B = {B:.3f} kmol/h",
        ],
        "values": {"D": D, "B": B},
    })

    if D <= 0 or B <= 0:
        return {
            "success": False,
            "errors": ["Invalid material balance - check specifications"],
        }

    # Step 4: 最小理論段数（Fenske式）
    N_min = math.log((xD / (1 - xD)) * ((1 - xB) / xB)) / math.log(alpha)

    calculation_steps.append({
        "step": 4,
        "title": "最小理論段数（Fenske式）/ Minimum Stages",
        "description": "全還流条件での最小段数",
        "formulas": [
            "Nmin = ln[(xD/(1-xD)) × ((1-xB)/xB)] / ln(α)",
            f"Nmin = ln[({xD}/{1-xD:.4f}) × ({1-xB:.4f}/{xB:.4f})] / ln({alpha:.3f})",
            f"Nmin = ln[{xD/(1-xD):.3f} × {(1-xB)/xB:.3f}] / {math.log(alpha):.4f}",
            f"Nmin = ln[{(xD/(1-xD))*((1-xB)/xB):.3f}] / {math.log(alpha):.4f}",
            f"Nmin = {math.log((xD/(1-xD))*((1-xB)/xB)):.4f} / {math.log(alpha):.4f}",
            f"Nmin = {N_min:.2f} 段",
        ],
        "values": {"N_min": N_min},
    })

    # Step 5: 最小還流比（Underwood法）
    R_min = _calculate_minimum_reflux(alpha, xD, xF=zF, q=q)

    y_eq = alpha * zF / (1 + (alpha - 1) * zF)  # 計算式表示用
    calculation_steps.append({
        "step": 5,
        "title": "最小還流比（Underwood法）/ Minimum Reflux",
        "description": "操作線とq線の交点から算出",
        "formulas": [
            "平衡蒸気組成: y* = α·xF / (1 + (α-1)·xF)",
            f"y* = {alpha:.3f}×{zF} / (1 + ({alpha:.3f}-1)×{zF})",
            f"y* = {alpha*zF:.4f} / {1+(alpha-1)*zF:.4f}",
            f"y* = {y_eq:.4f}",
            "",
            "Rmin = (xD - y*) / (y* - xF)",
            f"Rmin = ({xD} - {y_eq:.4f}) / ({y_eq:.4f} - {zF})",
            f"Rmin = {xD - y_eq:.4f} / {y_eq - zF:.4f}",
            f"Rmin = {R_min:.4f}",
        ],
        "values": {"R_min": R_min, "y_eq": y_eq},
    })

    if R_min < 0:
        warnings.append(f"Calculated negative Rmin ({R_min:.3f}) - separation is very easy, using Rmin=0.01")
        R_min = 0.01

    # Step 6: 実還流比
    R = R_min * R_factor

    calculation_steps.append({
        "step": 6,
        "title": "実還流比 / Actual Reflux Ratio",
        "description": f"還流比係数 = {R_factor}",
        "formulas": [
            "R = Rmin × 係数",
            f"R = {R_min:.4f} × {R_factor}",
            f"R = {R:.4f}",
        ],
        "values": {"R": R, "R_factor": R_factor},
    })

    # Step 7: 実理論段数（Gilliland相関）
    N = _gilliland_correlation(N_min, R_min, R)

    X = (R - R_min) / (R + 1)
    Y = (N - N_min) / (N + 1) if N > 0 else 0
    calculation_steps.append({
        "step": 7,
        "title": "実理論段数（Gilliland相関）/ Actual Stages",
        "description": "Gilliland相関図の代数近似",
        "formulas": [
            "X = (R - Rmin) / (R + 1)",
            f"X = ({R:.4f} - {R_min:.4f}) / ({R:.4f} + 1)",
            f"X = {R - R_min:.4f} / {R + 1:.4f}",
            f"X = {X:.4f}",
            "",
            "Y = 1 - exp[(1+54.4X)/(11+117.2X) × (X-1)/√X]",
            f"Y = {Y:.4f}",
            "",
            "N = (Nmin + Y) / (1 - Y)",
            f"N = ({N_min:.2f} + {Y:.4f}) / (1 - {Y:.4f})",
            f"N = {N:.2f} 段",
            f"理論段数（リボイラー込み）= {int(round(N)) + 1} 段",
        ],
        "values": {"X": X, "Y": Y, "N": N},
    })

    # Step 8: 原料供給段（Kirkbride式）
    feed_stage = _kirkbride_feed_stage(N, zF, xD, xB, D, B)

    calculation_steps.append({
        "step": 8,
        "title": "原料供給段（Kirkbride式）/ Feed Stage",
        "description": "精留部と回収部の段数比",
        "formulas": [
            "log(Nr/Ns) = 0.206 × log[(B/D)×((zF-xB)/(xD-zF))²×(xB/(1-xD))]",
            f"Nr + Ns = N = {N:.1f}",
            f"原料供給段 = {feed_stage} 段目（塔頂から数えて）",
        ],
        "values": {"feed_stage": feed_stage},
    })

    # Step 9: 熱負荷計算
    Qc, Qr = _calculate_heat_duties(
        engine, light_comp, heavy_comp, D, R, F, q, T_feed, P, warnings
    )

    # 塔頂蒸気流量
    V = D * (R + 1)  # kmol/h
    L = D * R  # 精留部液流量

    calculation_steps.append({
        "step": 9,
        "title": "熱負荷計算 / Heat Duties",
        "description": "凝縮器・再沸器の熱負荷",
        "formulas": [
            "塔頂蒸気流量: V = D × (R + 1)",
            f"V = {D:.3f} × ({R:.4f} + 1)",
            f"V = {V:.3f} kmol/h",
            "",
            "精留部液流量: L = D × R",
            f"L = {D:.3f} × {R:.4f}",
            f"L = {L:.3f} kmol/h",
            "",
            "凝縮器熱負荷: Qc = V × ΔHvap",
            f"Qc = {Qc:.1f} kW",
            "",
            "再沸器熱負荷: Qr ≈ Qc + F×(1-q)×ΔHvap",
            f"Qr = {Qr:.1f} kW",
        ],
        "values": {"V": V, "L": L, "Qc": Qc, "Qr": Qr},
    })

    # Step 10: 塔径の概算
    diameter = _estimate_column_diameter(
        V, P, T_feed, warnings, engine=engine,
        light_comp=light_comp, heavy_comp=heavy_comp, zF=zF,
    )

    calculation_steps.append({
        "step": 10,
        "title": "塔径概算 / Column Diameter",
        "description": "蒸気流量ベースの概算",
        "formulas": [
            "蒸気体積流量から許容速度で塔断面積を計算",
            f"塔径 D = {diameter:.2f} m",
        ],
        "values": {"diameter": diameter},
    })

    return {
        "success": True,
        "outputs": {
            "minimum_reflux_ratio": round(R_min, 4),
            "actual_reflux_ratio": round(R, 4),
            "minimum_stages": int(round(N_min)),
            "actual_stages": int(round(N)) + 1,  # +1 for reboiler
            "feed_stage": feed_stage,
            "distillate_flow_rate": round(D, 3),
            "bottoms_flow_rate": round(B, 3),
            "condenser_duty": round(Qc, 1),
            "reboiler_duty": round(Qr, 1),
            "relative_volatility": round(alpha, 3),
            "column_diameter": round(diameter, 2),
            "vapor_flow_rate": round(V, 3),
            "liquid_flow_rate_rectifying": round(D * R, 3),
            "calculation_steps": calculation_steps,
        },
        "warnings": warnings,
    }


def _calculate_relative_volatility(
    engine, light_comp: str, heavy_comp: str,
    T: float, P: float, z: float, warnings: list[str]
) -> float:
    """相対揮発度を計算"""
    if engine is None or not engine.is_available():
        # デフォルト値（エタノール-水系の典型値）
        warnings.append("Using default relative volatility (2.5)")
        return 2.5

    try:
        result = engine.calculate_equilibrium(
            substances=[light_comp, heavy_comp],
            composition={light_comp: z, heavy_comp: 1 - z},
            conditions={"temperature": T, "pressure": P},
        )
        K_values = result.get("K_values", {})
        K_light = K_values.get(light_comp, 2.0)
        K_heavy = K_values.get(heavy_comp, 1.0)
        alpha = K_light / K_heavy if K_heavy > 0 else 2.5
        return alpha
    except Exception as e:
        warnings.append("VLE calculation failed, using default α=2.5")
        return 2.5


def _calculate_minimum_reflux(alpha: float, xD: float, xF: float, q: float) -> float:
    """
    最小還流比を計算（二成分系簡易法）

    飽和液原料(q=1)の場合の近似式を使用:
    Rmin = (1/(α-1)) * [xD/xF - α*(1-xD)/(1-xF)]

    より一般的な式:
    Rmin = (xD - y_eq) / (y_eq - xF)
    where y_eq = α*xF / (1 + (α-1)*xF)
    """
    if alpha <= 1.0:
        return float('inf')

    # 原料組成での平衡蒸気組成
    y_eq = alpha * xF / (1 + (alpha - 1) * xF)

    # 原料熱状態による補正
    # q = 1 (飽和液): 操作線と平衡線の交点がq線上
    # 簡易的には、q線の傾きを考慮
    if q >= 0.999:  # 飽和液
        # Rmin = (xD - y_eq) / (y_eq - xF) が基本
        if abs(y_eq - xF) < 1e-10:
            return 0.5
        R_min = (xD - y_eq) / (y_eq - xF)
    else:
        # q < 1 の場合、より複雑な計算が必要
        # 簡易的に補正係数を適用
        if abs(y_eq - xF) < 1e-10:
            return 0.5
        R_min = (xD - y_eq) / (y_eq - xF) * (1 + 0.1 * (1 - q))

    # 負の値は分離が容易（平衡線がxDに近い）なことを示す
    if R_min < 0:
        R_min = 0.01

    return R_min


def _gilliland_correlation(N_min: float, R_min: float, R: float) -> float:
    """
    Gilliland相関で実段数を計算

    X = (R - R_min) / (R + 1)
    Y = (N - N_min) / (N + 1)
    Y = 1 - exp[(1 + 54.4*X)/(11 + 117.2*X) * (X-1)/sqrt(X)]
    """
    if R <= R_min:
        return float('inf')

    X = (R - R_min) / (R + 1)

    if X <= 0:
        # X <= 0 means R <= R_min, should not reach here (caught above)
        return float('inf')
    if X >= 1:
        # X >= 1 means very high reflux, approaching total reflux → N ≈ N_min
        return N_min * 1.05

    try:
        exponent = (1 + 54.4 * X) / (11 + 117.2 * X) * (X - 1) / math.sqrt(X)
        Y = 1 - math.exp(exponent)
    except (ValueError, OverflowError):
        Y = 0.5  # フォールバック

    # N = (N_min + Y) / (1 - Y)
    if Y >= 1:
        return N_min * 3

    N = (N_min + Y) / (1 - Y)
    return N


def _kirkbride_feed_stage(
    N: float, zF: float, xD: float, xB: float, D: float, B: float
) -> int:
    """
    Kirkbride式で原料供給段を計算

    log(Nr/Ns) = 0.206 * log[(B/D) * ((xF-xB)/(xD-xF))^2 * (xB/(1-xD))]
    """
    try:
        ratio = (B / D) * ((zF - xB) / (xD - zF)) ** 2 * (xB / (1 - xD))
        log_ratio = 0.206 * math.log10(ratio) if ratio > 0 else 0
        Nr_Ns = 10 ** log_ratio

        # Ns = N / (1 + Nr/Ns) = N / (1 + Nr_Ns)
        Ns = N / (1 + Nr_Ns)
        feed_stage = int(round(Ns))

        # 妥当な範囲に制限
        feed_stage = max(1, min(int(N) - 1, feed_stage))
        return feed_stage

    except (ValueError, ZeroDivisionError):
        return int(N / 2)


def _calculate_heat_duties(
    engine, light_comp: str, heavy_comp: str,
    D: float, R: float, F: float, q: float, T: float, P: float,
    warnings: list[str]
) -> tuple[float, float]:
    """凝縮器・再沸器の熱負荷を計算"""
    # 蒸発熱を取得
    Hvap = 40000.0  # J/mol（デフォルト、エタノール程度）

    if engine is not None and engine.is_available():
        try:
            # 軽沸成分の蒸発熱
            Hvap_light = engine.get_property(
                light_comp, "heat_of_vaporization", {"temperature": T}
            )
            Hvap_heavy = engine.get_property(
                heavy_comp, "heat_of_vaporization", {"temperature": T}
            )
            Hvap = (Hvap_light + Hvap_heavy) / 2
        except Exception:
            warnings.append("Could not get heat of vaporization, using default")

    # 塔頂蒸気流量
    V = D * (R + 1)  # kmol/h

    # 凝縮器熱負荷 (kW)
    # Qc = V * Hvap / 3600 (kmol/h → kmol/s, J/mol → J/s = W)
    Qc = V * 1000 * Hvap / 3600 / 1000  # kW

    # 再沸器熱負荷（概算）
    # Qr ≈ Qc + F * (1-q) * Hvap（原料の蒸発熱を考慮）
    Qr = Qc + F * 1000 * (1 - q) * Hvap / 3600 / 1000

    return Qc, Qr


def _estimate_column_diameter(
    V: float, P: float, T: float, warnings: list[str],
    engine=None, light_comp: str = "", heavy_comp: str = "", zF: float = 0.5,
) -> float:
    """
    塔径の概算（Fair法の簡易版）

    V: 蒸気流量 (kmol/h)
    """
    # 蒸気密度の概算（理想気体）
    R_gas = 8.314  # J/(mol·K)

    # 平均分子量をエンジンから取得（可能な場合）
    MW_avg = 50.0  # g/mol（デフォルト）
    if engine is not None and engine.is_available() and light_comp and heavy_comp:
        try:
            MW_light = engine.get_property(light_comp, "molecular_weight", {})
            MW_heavy = engine.get_property(heavy_comp, "molecular_weight", {})
            MW_avg = zF * MW_light + (1 - zF) * MW_heavy
        except Exception:
            warnings.append("Could not get molecular weights, using default MW=50 g/mol")

    rho_v = P * MW_avg / 1000 / (R_gas * T)  # kg/m³

    # 蒸気質量流量
    m_v = V * MW_avg / 3600  # kg/s

    # 蒸気体積流量
    Q_v = m_v / rho_v  # m³/s

    # 許容蒸気速度（簡易推定）
    u_flood = 1.0  # m/s（概算、実際はトレイ設計に依存）
    u_allow = 0.8 * u_flood

    # 塔断面積
    A = Q_v / u_allow

    # 塔径
    D_col = math.sqrt(4 * A / math.pi)

    return D_col
