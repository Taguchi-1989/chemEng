"""
物性推算テンプレート

純物質の熱力学物性値を計算する。
"""

from __future__ import annotations

from typing import Any

# 物性の単位マッピング
PROPERTY_UNITS = {
    "vapor_pressure": "Pa",
    "liquid_density": "kg/m³",
    "gas_density": "kg/m³",
    "liquid_viscosity": "Pa·s",
    "gas_viscosity": "Pa·s",
    "heat_capacity_liquid": "J/(mol·K)",
    "heat_capacity_gas": "J/(mol·K)",
    "thermal_conductivity_liquid": "W/(m·K)",
    "thermal_conductivity_gas": "W/(m·K)",
    "surface_tension": "N/m",
    "heat_of_vaporization": "J/mol",
    "critical_temperature": "K",
    "critical_pressure": "Pa",
    "acentric_factor": "-",
    "molecular_weight": "g/mol",
}


def execute(params: dict[str, Any], engine=None) -> dict[str, Any]:
    """
    物性推算を実行

    Args:
        params: 入力パラメータ
            - substance: 物質名
            - property: 物性名
            - temperature: 温度 (K)
            - pressure: 圧力 (Pa)
        engine: 計算エンジン

    Returns:
        計算結果
    """
    substance = params["substance"]
    property_name = params["property"]
    temperature = params.get("temperature", 298.15)
    pressure = params.get("pressure", 101325.0)

    warnings = []
    calculation_steps = []  # 計算過程を記録

    # Step 1: 入力条件
    calculation_steps.append({
        "step": 1,
        "title": "入力条件 / Input Conditions",
        "description": f"物質: {substance}",
        "formulas": [
            f"物質名: {substance}",
            f"推算物性: {property_name}",
            f"温度 T = {temperature} K ({temperature - 273.15:.1f} °C)",
            f"圧力 P = {pressure} Pa = {pressure/1000:.1f} kPa",
        ],
        "values": {"substance": substance, "property": property_name, "T": temperature, "P": pressure},
    })

    # エンジンがない場合はインポート
    if engine is None:
        try:
            from core.compat import get_thermo_engine
            engine = get_thermo_engine()
        except ImportError as e:
            return {
                "success": False,
                "errors": [f"Engine not available: {e}"],
            }

    # エンジンが利用可能か確認
    if not engine.is_available():
        return {
            "success": False,
            "errors": ["thermo/chemicals library not installed"],
        }

    # 条件
    conditions = {
        "temperature": temperature,
        "pressure": pressure,
    }

    try:
        # Step 2: 物質情報取得
        try:
            info = engine.get_substance_info(substance)
            substance_name = info.get("name", substance)
            cas = info.get("cas_number", info.get("CAS", "N/A"))
            mw = info.get("molecular_weight", info.get("MW", None))
            Tc = info.get("critical_temperature", info.get("Tc", None))
            Pc = info.get("critical_pressure", info.get("Pc", None))

            info_formulas = [
                f"物質名: {substance_name}",
                f"CAS番号: {cas}",
            ]
            if mw:
                info_formulas.append(f"分子量 MW = {mw:.2f} g/mol")
            if Tc:
                info_formulas.append(f"臨界温度 Tc = {Tc:.1f} K")
            if Pc:
                info_formulas.append(f"臨界圧力 Pc = {Pc/1e6:.2f} MPa")

            calculation_steps.append({
                "step": 2,
                "title": "物質情報 / Substance Information",
                "description": "データベースから物質情報を取得",
                "formulas": info_formulas,
                "values": {"name": substance_name, "CAS": cas, "MW": mw, "Tc": Tc, "Pc": Pc},
            })
        except Exception:
            substance_name = substance
            calculation_steps.append({
                "step": 2,
                "title": "物質情報 / Substance Information",
                "description": "物質情報取得",
                "formulas": [f"物質名: {substance}"],
                "values": {},
            })

        # 物性値を計算
        value = engine.get_property(substance, property_name, conditions)

        # 単位を取得
        unit = PROPERTY_UNITS.get(property_name, "")

        # 値の妥当性チェック
        if value is None:
            return {
                "success": False,
                "errors": [f"Could not calculate {property_name} for {substance}"],
            }

        # Step 3: 計算方法と結果
        method_info = _get_method_info(property_name, temperature, pressure)
        calculation_steps.append({
            "step": 3,
            "title": "物性計算 / Property Calculation",
            "description": method_info["description"],
            "formulas": method_info["formulas"] + [
                "",
                f"計算結果: {property_name} = {value:.4g} {unit}",
            ],
            "values": {"value": value, "unit": unit},
        })

        if value < 0 and property_name not in ["acentric_factor"]:
            warnings.append(f"Negative value calculated: {value}")

        return {
            "success": True,
            "outputs": {
                "value": value,
                "unit": unit,
                "substance": substance_name,
                "property": property_name,
                "conditions": conditions,
                "calculation_steps": calculation_steps,
            },
            "warnings": warnings,
        }

    except Exception:
        # Registry層の safe_error_message で安全に変換されるため、再raise
        raise


def _get_method_info(property_name: str, T: float, P: float) -> dict:
    """物性計算方法の情報を取得"""
    methods = {
        "vapor_pressure": {
            "description": "Antoine式 または Wagner式による蒸気圧推算",
            "formulas": [
                "Antoine式: log₁₀(P) = A - B/(C + T)",
                "Wagner式: ln(Pr) = (aτ + bτ^1.5 + cτ³ + dτ⁶) / Tr",
                "  τ = 1 - Tr, Tr = T/Tc, Pr = P/Pc",
            ],
        },
        "liquid_density": {
            "description": "Rackett式による液密度推算",
            "formulas": [
                "Rackett式: ρ = ρc × Zra^((1-Tr)^(2/7))",
                "  Tr = T/Tc（換算温度）",
                "  Zra: Rackett圧縮係数",
            ],
        },
        "liquid_viscosity": {
            "description": "Andrade式による液粘度推算",
            "formulas": [
                "Andrade式: ln(μ) = A + B/T + C×ln(T)",
                "または Letsou-Stiel相関式",
            ],
        },
        "heat_of_vaporization": {
            "description": "Watson式による蒸発熱推算",
            "formulas": [
                "Watson式: ΔHvap(T₂) = ΔHvap(T₁) × ((1-Tr₂)/(1-Tr₁))^n",
                "  n ≈ 0.38（一般値）",
                "  Tr = T/Tc",
            ],
        },
        "heat_capacity_liquid": {
            "description": "多項式近似による液体熱容量",
            "formulas": [
                "Cp = A + B×T + C×T² + D×T³",
                "データベース値 または グループ寄与法",
            ],
        },
        "heat_capacity_gas": {
            "description": "多項式近似による気体熱容量",
            "formulas": [
                "Cp = A + B×T + C×T² + D×T³",
                "理想気体熱容量（圧力依存なし）",
            ],
        },
        "surface_tension": {
            "description": "Macleod-Sugden式による表面張力推算",
            "formulas": [
                "σ^(1/4) = [P] × (ρL - ρV)",
                "  [P]: パラコール",
                "または Brock-Bird相関式",
            ],
        },
        "boiling_point": {
            "description": "沸点（データベース値）",
            "formulas": [
                "常圧(101.325 kPa)での沸騰温度",
                "蒸気圧 = 大気圧 となる温度",
            ],
        },
    }

    default = {
        "description": "thermoライブラリによる物性計算",
        "formulas": [
            f"物性: {property_name}",
            f"計算条件: T = {T:.1f} K, P = {P:.0f} Pa",
        ],
    }

    return methods.get(property_name, default)
