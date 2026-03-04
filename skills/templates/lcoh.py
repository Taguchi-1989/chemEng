"""
LCOH (Levelized Cost of Hydrogen) 計算テンプレート

水素製造原価の計算を行う。
対応製造方法:
- PEM電解 (pem_electrolysis)
- アルカリ電解 (alkaline_electrolysis)
- 固体酸化物電解 (soec_electrolysis)
- 天然ガス改質 (smr)
- 天然ガス改質+CCS (smr_ccs)
- 自己熱改質+CCS (atr_ccs)

参考:
- European Hydrogen Observatory LCOH Calculator
- NREL H2A Model
- DOE Hydrogen Program
"""

from __future__ import annotations

from typing import Any

# 製造方法別デフォルトパラメータ
METHOD_DEFAULTS = {
    "pem_electrolysis": {
        "capex_per_kw": 1000,  # EUR/kW (2024年)
        "electricity_consumption": 50,  # kWh/kg H2
        "stack_lifetime": 11,  # years (80,000時間想定)
        "stack_cost_percent": 60,  # % of CAPEX
        "carbon_intensity": 0,  # kg CO2/kg H2 (電力由来除く)
        "water_consumption": 9,  # L/kg H2
        "oxygen_production": 8,  # kg O2/kg H2
    },
    "alkaline_electrolysis": {
        "capex_per_kw": 700,  # EUR/kW
        "electricity_consumption": 55,  # kWh/kg H2
        "stack_lifetime": 9,  # years
        "stack_cost_percent": 50,
        "carbon_intensity": 0,
        "water_consumption": 9,
        "oxygen_production": 8,
    },
    "soec_electrolysis": {
        "capex_per_kw": 1500,  # EUR/kW (高温電解)
        "electricity_consumption": 40,  # kWh/kg H2 (高効率)
        "stack_lifetime": 7,  # years
        "stack_cost_percent": 60,
        "carbon_intensity": 0,
        "water_consumption": 9,
        "oxygen_production": 8,
    },
    "smr": {
        "capex_per_kw": 400,  # EUR/kW (改質装置)
        "natural_gas_consumption": 0.165,  # MWh/kg H2
        "stack_lifetime": 25,  # years (触媒寿命)
        "stack_cost_percent": 10,
        "carbon_intensity": 9.5,  # kg CO2/kg H2
        "water_consumption": 4.5,  # L/kg H2
        "oxygen_production": 0,
    },
    "smr_ccs": {
        "capex_per_kw": 600,  # EUR/kW (CCS込み)
        "natural_gas_consumption": 0.18,  # MWh/kg H2 (CCS電力含む)
        "stack_lifetime": 25,
        "stack_cost_percent": 10,
        "carbon_intensity": 9.5,  # 回収前
        "ccs_capture_rate": 90,  # %
        "water_consumption": 5,
        "oxygen_production": 0,
        "ccs_cost": 0.3,  # EUR/kg H2 追加コスト
    },
    "atr_ccs": {
        "capex_per_kw": 650,  # EUR/kW
        "natural_gas_consumption": 0.17,  # MWh/kg H2
        "stack_lifetime": 25,
        "stack_cost_percent": 10,
        "carbon_intensity": 8.5,
        "ccs_capture_rate": 95,  # ATRはCCS効率が高い
        "water_consumption": 4,
        "oxygen_production": 0,
        "ccs_cost": 0.25,
    },
}


def calculate_crf(discount_rate: float, lifetime: int) -> float:
    """
    Capital Recovery Factor (資本回収係数) を計算

    CRF = r * (1+r)^n / ((1+r)^n - 1)

    Args:
        discount_rate: 割引率 (小数, e.g., 0.06 for 6%)
        lifetime: プロジェクト寿命 (年)

    Returns:
        CRF値
    """
    r = discount_rate
    n = lifetime
    if r == 0:
        return 1 / n
    return r * (1 + r)**n / ((1 + r)**n - 1)


def calculate_annualized_stack_cost(
    capex: float,
    stack_cost_percent: float,
    stack_lifetime: float,
    project_lifetime: int,
    discount_rate: float
) -> float:
    """
    スタック交換の年間平均費用を計算

    Args:
        capex: 総CAPEX (EUR)
        stack_cost_percent: スタック費用のCAPEX比率 (%)
        stack_lifetime: スタック寿命 (年)
        project_lifetime: プロジェクト寿命 (年)
        discount_rate: 割引率

    Returns:
        年間スタック交換費用 (EUR/year)
    """
    stack_cost = capex * (stack_cost_percent / 100)

    # プロジェクト期間中の交換回数
    num_replacements = int(project_lifetime / stack_lifetime)
    if project_lifetime % stack_lifetime == 0:
        num_replacements -= 1  # 最終年の交換は不要

    if num_replacements <= 0:
        return 0

    # 各交換時点での現在価値を計算し、年間化
    total_npv = 0
    for i in range(1, num_replacements + 1):
        replacement_year = i * stack_lifetime
        if replacement_year < project_lifetime:
            npv = stack_cost / ((1 + discount_rate) ** replacement_year)
            total_npv += npv

    # 年間化
    crf = calculate_crf(discount_rate, project_lifetime)
    return total_npv * crf


def calculate_lcoh(params: dict[str, Any], include_sensitivity: bool = True) -> dict[str, Any]:
    """
    LCOH (Levelized Cost of Hydrogen) を計算

    Args:
        params: 入力パラメータ
        include_sensitivity: 感度分析データを含めるか（再帰防止用）
            - production_method: 製造方法
            - capacity: 設備容量 (MW)
            - capex_per_kw: CAPEX単価 (EUR/kW)
            - electricity_price: 電力価格 (EUR/MWh)
            - natural_gas_price: 天然ガス価格 (EUR/MWh)
            - operating_hours: 年間稼働時間 (h/year)
            - opex_percent: OPEX率 (%)
            - stack_lifetime: スタック寿命 (年)
            - stack_cost_percent: スタック費用率 (%)
            - project_lifetime: プロジェクト寿命 (年)
            - discount_rate: 割引率 (%)
            - carbon_price: 炭素価格 (EUR/ton CO2)
            - oxygen_revenue: 酸素販売収入 (EUR/kg O2)
            - subsidies: 補助金 (EUR/kg H2)
            - water_price: 水価格 (EUR/m3)

    Returns:
        計算結果の辞書
    """
    steps = []

    # 製造方法の取得とデフォルト値の設定
    method = params.get("production_method", "pem_electrolysis")
    defaults = METHOD_DEFAULTS.get(method, METHOD_DEFAULTS["pem_electrolysis"])

    steps.append({
        "step": "製造方法の選択",
        "method": method,
        "description": get_method_description(method)
    })

    # パラメータの取得（デフォルト値で補完）
    capacity_mw = params.get("capacity", 10)  # MW
    capacity_kw = capacity_mw * 1000  # kW

    capex_per_kw = params.get("capex_per_kw", defaults["capex_per_kw"])
    operating_hours = params.get("operating_hours", 4000)
    maintenance_days = params.get("maintenance_days", 0) or 0
    labor_cost = params.get("labor_cost", 0) or 0
    maintenance_cost = params.get("maintenance_cost", 0) or 0
    capex_subsidy_percent = params.get("capex_subsidy_percent", 0) or 0
    capex_subsidy_amount = params.get("capex_subsidy_amount", 0) or 0

    # 設備利用率が指定された場合
    if "capacity_factor" in params and params["capacity_factor"]:
        operating_hours = params["capacity_factor"] * 8760
    if maintenance_days:
        operating_hours = max(0, operating_hours - (maintenance_days * 24))
    if operating_hours <= 0:
        raise ValueError("Operating hours must be > 0 after maintenance downtime")

    opex_percent = params.get("opex_percent", 3.0)
    stack_lifetime = params.get("stack_lifetime", defaults["stack_lifetime"])
    stack_cost_percent = params.get("stack_cost_percent", defaults["stack_cost_percent"])
    project_lifetime = params.get("project_lifetime", 20)
    discount_rate = params.get("discount_rate", 6.0) / 100  # 小数に変換
    carbon_price = params.get("carbon_price", 0)
    water_price = params.get("water_price", 2.0)
    subsidies = params.get("subsidies", 0)
    oxygen_revenue_per_kg = params.get("oxygen_revenue", 0)

    # 電解 or 改質かで分岐
    is_electrolysis = "electrolysis" in method

    if is_electrolysis:
        electricity_price = params.get("electricity_price", 50)  # EUR/MWh
        electricity_consumption = params.get(
            "electricity_consumption",
            defaults["electricity_consumption"]
        )  # kWh/kg H2
    else:
        natural_gas_price = params.get("natural_gas_price", 30)  # EUR/MWh
        natural_gas_consumption = defaults.get("natural_gas_consumption", 0.165)  # MWh/kg H2

    # ----- 計算開始 -----

    # 1. 総CAPEX
    if maintenance_days:
        steps.append({
            "step": "Operating Hours Adjustment",
            "formula": "effective_hours = operating_hours - maintenance_days * 24",
            "values": {
                "operating_hours_input": params.get("operating_hours", 4000),
                "maintenance_days": maintenance_days,
            },
            "result": f"{operating_hours:.1f} hours/year"
        })

    total_capex = capacity_kw * capex_per_kw
    capex_subsidy = (total_capex * (capex_subsidy_percent / 100)) + capex_subsidy_amount
    net_capex = max(0, total_capex - capex_subsidy)
    steps.append({
        "step": "総CAPEX計算",
        "formula": "CAPEX = 容量 × 単価",
        "values": {
            "capacity_kw": capacity_kw,
            "capex_per_kw": capex_per_kw,
            "capex_subsidy_percent": capex_subsidy_percent,
            "capex_subsidy_amount": capex_subsidy_amount,
        },
        "result": f"{net_capex:,.0f} EUR (gross {total_capex:,.0f} - subsidy {capex_subsidy:,.0f})"
    })

    # 2. 年間水素生産量
    if is_electrolysis:
        # 電解: 電力容量から生産量を計算
        annual_electricity = capacity_kw * operating_hours  # kWh/year
        annual_h2_production = annual_electricity / electricity_consumption  # kg/year

        steps.append({
            "step": "年間水素生産量計算",
            "formula": "H2生産量 = 電力使用量 / 電力消費量",
            "values": {
                "annual_electricity_kwh": annual_electricity,
                "electricity_consumption_kwh_per_kg": electricity_consumption,
            },
            "result": f"{annual_h2_production:,.0f} kg/year"
        })
    else:
        # SMR/ATR: 改質能力から生産量を計算
        # 改質器の容量は熱入力ベース
        annual_heat_input = capacity_mw * operating_hours  # MWh/year
        annual_h2_production = annual_heat_input / natural_gas_consumption  # kg/year

        steps.append({
            "step": "年間水素生産量計算",
            "formula": "H2生産量 = 熱入力 / ガス消費量",
            "values": {
                "annual_heat_input_mwh": annual_heat_input,
                "natural_gas_consumption_mwh_per_kg": natural_gas_consumption,
            },
            "result": f"{annual_h2_production:,.0f} kg/year"
        })

    # 3. CRF（資本回収係数）
    crf = calculate_crf(discount_rate, project_lifetime)
    steps.append({
        "step": "資本回収係数 (CRF) 計算",
        "formula": "CRF = r(1+r)^n / ((1+r)^n - 1)",
        "values": {
            "discount_rate": f"{discount_rate*100:.1f}%",
            "project_lifetime": f"{project_lifetime} years",
        },
        "result": f"{crf:.4f}"
    })

    # 4. 年間CAPEX償却
    annual_capex_cost = net_capex * crf
    capex_per_kg = annual_capex_cost / annual_h2_production

    steps.append({
        "step": "年間CAPEX償却",
        "formula": "年間CAPEX = 総CAPEX × CRF",
        "values": {
            "total_capex": f"{net_capex:,.0f} EUR",
            "crf": crf,
        },
        "result": f"{annual_capex_cost:,.0f} EUR/year ({capex_per_kg:.2f} EUR/kg H2)"
    })

    # 5. エネルギーコスト
    if is_electrolysis:
        annual_electricity_mwh = capacity_kw * operating_hours / 1000
        annual_energy_cost = annual_electricity_mwh * electricity_price
        energy_per_kg = annual_energy_cost / annual_h2_production

        steps.append({
            "step": "電力コスト計算",
            "formula": "電力コスト = 電力使用量 × 電力単価",
            "values": {
                "annual_electricity_mwh": annual_electricity_mwh,
                "electricity_price_eur_mwh": electricity_price,
            },
            "result": f"{annual_energy_cost:,.0f} EUR/year ({energy_per_kg:.2f} EUR/kg H2)"
        })
    else:
        annual_gas_mwh = annual_h2_production * natural_gas_consumption
        annual_energy_cost = annual_gas_mwh * natural_gas_price
        energy_per_kg = annual_energy_cost / annual_h2_production

        steps.append({
            "step": "天然ガスコスト計算",
            "formula": "ガスコスト = ガス使用量 × ガス単価",
            "values": {
                "annual_gas_mwh": annual_gas_mwh,
                "natural_gas_price_eur_mwh": natural_gas_price,
            },
            "result": f"{annual_energy_cost:,.0f} EUR/year ({energy_per_kg:.2f} EUR/kg H2)"
        })

    # 6. 固定OPEX
    annual_base_opex = net_capex * (opex_percent / 100)
    annual_fixed_opex = annual_base_opex + labor_cost + maintenance_cost
    opex_base_per_kg = annual_base_opex / annual_h2_production
    labor_per_kg = labor_cost / annual_h2_production if labor_cost else 0
    maintenance_per_kg = maintenance_cost / annual_h2_production if maintenance_cost else 0
    opex_per_kg = opex_base_per_kg + labor_per_kg + maintenance_per_kg

    steps.append({
        "step": "固定OPEX計算",
        "formula": "固定OPEX = CAPEX × OPEX率",
        "values": {
            "total_capex": f"{net_capex:,.0f} EUR",
            "opex_percent": f"{opex_percent}%",
            "labor_cost": f"{labor_cost:,.0f} EUR/year",
            "maintenance_cost": f"{maintenance_cost:,.0f} EUR/year",
        },
        "result": f"{annual_fixed_opex:,.0f} EUR/year ({opex_per_kg:.2f} EUR/kg H2)"
    })

    # 7. スタック交換費用
    annual_stack_cost = calculate_annualized_stack_cost(
        total_capex, stack_cost_percent, stack_lifetime,
        project_lifetime, discount_rate
    )
    stack_per_kg = annual_stack_cost / annual_h2_production

    steps.append({
        "step": "スタック交換費用計算",
        "formula": "NPV(交換費用) × CRF",
        "values": {
            "stack_cost_percent": f"{stack_cost_percent}%",
            "stack_lifetime": f"{stack_lifetime} years",
            "replacements": int(project_lifetime / stack_lifetime) - (1 if project_lifetime % stack_lifetime == 0 else 0),
        },
        "result": f"{annual_stack_cost:,.0f} EUR/year ({stack_per_kg:.2f} EUR/kg H2)"
    })

    # 8. 水コスト
    water_consumption = defaults.get("water_consumption", 9)  # L/kg H2
    annual_water_m3 = (annual_h2_production * water_consumption) / 1000
    annual_water_cost = annual_water_m3 * water_price
    water_per_kg = annual_water_cost / annual_h2_production

    steps.append({
        "step": "水コスト計算",
        "formula": "水コスト = 水使用量 × 水単価",
        "values": {
            "water_consumption_l_per_kg": water_consumption,
            "water_price_eur_m3": water_price,
        },
        "result": f"{annual_water_cost:,.0f} EUR/year ({water_per_kg:.4f} EUR/kg H2)"
    })

    # 9. 炭素コスト
    base_carbon_intensity = defaults.get("carbon_intensity", 0)

    if "ccs" in method:
        ccs_capture_rate = params.get("ccs_capture_rate", defaults.get("ccs_capture_rate", 90)) / 100
        actual_carbon_intensity = base_carbon_intensity * (1 - ccs_capture_rate)
        ccs_additional_cost = defaults.get("ccs_cost", 0.3) * annual_h2_production
    else:
        actual_carbon_intensity = base_carbon_intensity
        ccs_additional_cost = 0

    annual_co2_emissions = annual_h2_production * actual_carbon_intensity / 1000  # ton CO2
    annual_carbon_cost = annual_co2_emissions * carbon_price + ccs_additional_cost
    carbon_per_kg = annual_carbon_cost / annual_h2_production

    steps.append({
        "step": "炭素コスト計算",
        "formula": "炭素コスト = CO2排出量 × 炭素価格 (+ CCSコスト)",
        "values": {
            "carbon_intensity_kg_co2_per_kg_h2": actual_carbon_intensity,
            "annual_co2_emissions_ton": annual_co2_emissions,
            "carbon_price_eur_ton": carbon_price,
        },
        "result": f"{annual_carbon_cost:,.0f} EUR/year ({carbon_per_kg:.2f} EUR/kg H2)"
    })

    # 10. 収入（酸素販売、補助金）
    oxygen_production = defaults.get("oxygen_production", 0)
    annual_oxygen_revenue = annual_h2_production * oxygen_production * oxygen_revenue_per_kg
    annual_subsidies = annual_h2_production * subsidies
    total_revenue = annual_oxygen_revenue + annual_subsidies
    revenue_per_kg = total_revenue / annual_h2_production

    steps.append({
        "step": "収入計算",
        "values": {
            "oxygen_production_kg_per_kg_h2": oxygen_production,
            "oxygen_revenue_eur_per_kg_o2": oxygen_revenue_per_kg,
            "subsidies_eur_per_kg_h2": subsidies,
        },
        "result": f"{total_revenue:,.0f} EUR/year ({revenue_per_kg:.2f} EUR/kg H2)"
    })

    # 11. LCOH計算
    total_annual_cost = (
        annual_capex_cost +
        annual_energy_cost +
        annual_fixed_opex +
        annual_stack_cost +
        annual_water_cost +
        annual_carbon_cost -
        total_revenue
    )

    lcoh = total_annual_cost / annual_h2_production

    steps.append({
        "step": "LCOH計算",
        "formula": "LCOH = 年間総コスト / 年間H2生産量",
        "values": {
            "total_annual_cost_eur": total_annual_cost,
            "annual_h2_production_kg": annual_h2_production,
        },
        "result": f"{lcoh:.2f} EUR/kg H2"
    })

    # LCOH内訳
    lcoh_breakdown = {
        "capex": round(capex_per_kg, 3),
        "energy": round(energy_per_kg, 3),
        "opex": round(opex_base_per_kg, 3),
        "labor": round(labor_per_kg, 3),
        "maintenance": round(maintenance_per_kg, 3),
        "stack_replacement": round(stack_per_kg, 3),
        "water": round(water_per_kg, 4),
        "carbon": round(carbon_per_kg, 3),
        "revenue_offset": round(-revenue_per_kg, 3),
        "total": round(lcoh, 3),
    }

    # 年間コスト
    annual_costs = {
        "capex_annualized": round(annual_capex_cost, 0),
        "energy": round(annual_energy_cost, 0),
        "fixed_opex": round(annual_base_opex, 0),
        "labor": round(labor_cost, 0),
        "maintenance": round(maintenance_cost, 0),
        "stack_replacement": round(annual_stack_cost, 0),
        "water": round(annual_water_cost, 0),
        "carbon": round(annual_carbon_cost, 0),
        "revenue": round(-total_revenue, 0),
        "total": round(total_annual_cost, 0),
    }

    # エネルギー効率
    if is_electrolysis:
        # H2 HHV = 39.4 kWh/kg
        energy_efficiency = (39.4 / electricity_consumption) * 100
    else:
        # SMR効率
        h2_energy_content = 39.4  # kWh/kg (HHV)
        gas_energy_input = natural_gas_consumption * 1000  # kWh/kg H2
        energy_efficiency = (h2_energy_content / gas_energy_input) * 100

    # 感度分析データ
    if include_sensitivity:
        sensitivity_data = generate_sensitivity_data(params, lcoh, is_electrolysis)
    else:
        sensitivity_data = {}

    return {
        "lcoh": round(lcoh, 3),
        "lcoh_breakdown": lcoh_breakdown,
        "annual_h2_production": round(annual_h2_production, 0),
        "total_capex": round(net_capex, 0),
        "annual_costs": annual_costs,
        "carbon_intensity": round(actual_carbon_intensity, 2),
        "energy_efficiency": round(energy_efficiency, 1),
        "production_method": method,
        "capacity_mw": capacity_mw,
        "operating_hours": operating_hours,
        "calculation_steps": steps,
        "sensitivity_data": sensitivity_data,
    }


def generate_sensitivity_data(
    params: dict[str, Any],
    base_lcoh: float,
    is_electrolysis: bool
) -> dict[str, list[dict[str, float]]]:
    """
    感度分析用データを生成
    主要パラメータを±20%変動させた場合のLCOHを計算
    """
    sensitivity = {}

    if is_electrolysis:
        # 電力価格感度
        base_price = params.get("electricity_price", 50)
        electricity_sensitivity = []
        for factor in [0.6, 0.8, 1.0, 1.2, 1.4]:
            test_params = params.copy()
            test_params["electricity_price"] = base_price * factor
            result = calculate_lcoh_simple(test_params)
            electricity_sensitivity.append({
                "price": round(base_price * factor, 1),
                "lcoh": round(result, 2)
            })
        sensitivity["electricity_price"] = electricity_sensitivity
    else:
        # 天然ガス価格感度
        base_price = params.get("natural_gas_price", 30)
        gas_sensitivity = []
        for factor in [0.6, 0.8, 1.0, 1.2, 1.4]:
            test_params = params.copy()
            test_params["natural_gas_price"] = base_price * factor
            result = calculate_lcoh_simple(test_params)
            gas_sensitivity.append({
                "price": round(base_price * factor, 1),
                "lcoh": round(result, 2)
            })
        sensitivity["natural_gas_price"] = gas_sensitivity

    # CAPEX感度
    base_capex = params.get("capex_per_kw",
                           METHOD_DEFAULTS.get(params.get("production_method", "pem_electrolysis"), {}).get("capex_per_kw", 1000))
    capex_sensitivity = []
    for factor in [0.6, 0.8, 1.0, 1.2, 1.4]:
        test_params = params.copy()
        test_params["capex_per_kw"] = base_capex * factor
        result = calculate_lcoh_simple(test_params)
        capex_sensitivity.append({
            "capex": round(base_capex * factor, 0),
            "lcoh": round(result, 2)
        })
    sensitivity["capex"] = capex_sensitivity

    # 稼働時間感度
    hours_sensitivity = []
    for hours in [2000, 4000, 6000, 8000]:
        test_params = params.copy()
        test_params["operating_hours"] = hours
        result = calculate_lcoh_simple(test_params)
        hours_sensitivity.append({
            "hours": hours,
            "lcoh": round(result, 2)
        })
    sensitivity["operating_hours"] = hours_sensitivity

    return sensitivity


def calculate_lcoh_simple(params: dict[str, Any]) -> float:
    """簡易LCOH計算（感度分析用）"""
    result = calculate_lcoh(params, include_sensitivity=False)
    return result["lcoh"]


def get_method_description(method: str) -> str:
    """製造方法の説明を取得"""
    descriptions = {
        "pem_electrolysis": "PEM(固体高分子膜)電解: 高純度、急速応答、再エネ連携に適する",
        "alkaline_electrolysis": "アルカリ電解: 成熟技術、低コスト、大規模向け",
        "soec_electrolysis": "SOEC(固体酸化物)電解: 高温高効率、廃熱利用可能",
        "smr": "SMR(水蒸気メタン改質): 最も普及、グレー水素",
        "smr_ccs": "SMR + CCS: CO2回収付き、ブルー水素",
        "atr_ccs": "ATR + CCS: 高CO2回収率、ブルー水素",
    }
    return descriptions.get(method, "不明な製造方法")


# API呼び出し用エントリポイント
def execute(params: dict[str, Any], engine=None) -> dict[str, Any]:
    """
    スキル実行のエントリポイント（registry互換）

    Args:
        params: 入力パラメータ
        engine: 計算エンジン（LCOHでは未使用）

    Returns:
        計算結果
    """
    result = calculate_lcoh(params)
    return {
        "success": True,
        "outputs": result,
        "warnings": [],
    }


def run(params: dict[str, Any]) -> dict[str, Any]:
    """
    スキル実行のエントリポイント（後方互換）
    """
    return calculate_lcoh(params)


if __name__ == "__main__":
    # テスト実行
    test_params = {
        "production_method": "pem_electrolysis",
        "capacity": 10,  # MW
        "electricity_price": 50,  # EUR/MWh
        "operating_hours": 4000,
        "project_lifetime": 20,
        "discount_rate": 6,
    }

    result = calculate_lcoh(test_params)

    print("\n=== LCOH計算結果 ===")
    print(f"LCOH: {result['lcoh']:.2f} EUR/kg H2")
    print("\n内訳:")
    for key, value in result['lcoh_breakdown'].items():
        print(f"  {key}: {value:.3f} EUR/kg H2")
    print(f"\n年間生産量: {result['annual_h2_production']:,.0f} kg/year")
    print(f"エネルギー効率: {result['energy_efficiency']:.1f}%")
    print(f"CO2排出原単位: {result['carbon_intensity']:.2f} kg CO2/kg H2")
