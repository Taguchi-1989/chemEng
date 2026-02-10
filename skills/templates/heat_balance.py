"""
熱収支テンプレート

定常状態のプロセスにおける熱収支（エネルギーバランス）を計算する。
Q = m * Cp * dT + m * Hvap (相変化時)
"""

from __future__ import annotations

from typing import Any


def execute(params: dict[str, Any], engine=None) -> dict[str, Any]:
    """
    熱収支を実行

    Args:
        params: 入力パラメータ
            - substance: 物質名
            - flow_rate: 流量 (mol/s)
            - inlet_temperature: 入口温度 (K)
            - outlet_temperature: 出口温度 (K)
            - pressure: 圧力 (Pa)
            - phase_change: 相変化考慮
            - heat_of_reaction: 反応熱 (J/mol)
            - efficiency: 熱効率
        engine: 計算エンジン

    Returns:
        計算結果
    """
    substance = params["substance"]
    flow_rate = params["flow_rate"]  # mol/s
    T_in = params["inlet_temperature"]  # K
    T_out = params["outlet_temperature"]  # K
    P = params.get("pressure", 101325)  # Pa
    phase_change = params.get("phase_change", True)
    heat_of_reaction = params.get("heat_of_reaction", 0.0)  # J/mol
    efficiency = params.get("efficiency", 1.0)

    warnings = []
    calculation_steps = []  # 計算過程を記録

    if engine is None:
        return {
            "success": False,
            "outputs": {},
            "errors": ["No calculation engine available"],
            "warnings": [],
        }

    # Step 1: 物性値を取得
    calculation_steps.append({
        "step": 1,
        "title": "物性値取得 / Property Lookup",
        "description": f"物質: {substance}",
        "formulas": [],
        "values": {},
    })

    try:
        T_boil = engine.get_property(substance, "boiling_point", {"pressure": P})
        calculation_steps[-1]["values"]["T_boil"] = T_boil
        calculation_steps[-1]["formulas"].append(f"沸点 Tb = {T_boil:.2f} K ({T_boil - 273.15:.1f} °C)")
    except Exception:
        T_boil = None
        warnings.append("Could not get boiling point, assuming no phase change")
        phase_change = False

    # 相の判定
    def get_phase(T: float) -> str:
        if T_boil is None:
            return "unknown"
        return "vapor" if T > T_boil else "liquid"

    inlet_phase = get_phase(T_in)
    outlet_phase = get_phase(T_out)

    calculation_steps[-1]["values"]["inlet_phase"] = inlet_phase
    calculation_steps[-1]["values"]["outlet_phase"] = outlet_phase
    calculation_steps[-1]["formulas"].append(f"入口相: {inlet_phase} (T_in = {T_in} K)")
    calculation_steps[-1]["formulas"].append(f"出口相: {outlet_phase} (T_out = {T_out} K)")

    # 変数初期化
    sensible_heat = 0.0
    latent_heat = 0.0
    inlet_enthalpy = 0.0
    outlet_enthalpy = 0.0
    Cp_liq = None
    Cp_gas = None
    H_vap = None

    if phase_change and T_boil is not None:
        # Step 2: 熱容量・蒸発熱の取得
        try:
            H_vap = engine.get_property(substance, "heat_of_vaporization", {"temperature": T_boil})
        except Exception:
            H_vap = 0.0
            warnings.append("Could not get heat of vaporization")

        if inlet_phase == "liquid" and outlet_phase == "vapor":
            # 液体 → 沸点 → 蒸発 → 蒸気
            calculation_steps.append({
                "step": 2,
                "title": "物性値取得 / Heat Capacity & Hvap",
                "description": "液体→気体の相変化あり",
                "formulas": [],
                "values": {},
            })

            try:
                Cp_liq = engine.get_property(substance, "heat_capacity_liquid", {"temperature": (T_in + T_boil) / 2})
            except Exception:
                Cp_liq = 75.0
                warnings.append(f"Using default liquid Cp = {Cp_liq} J/(mol·K)")

            try:
                Cp_gas = engine.get_property(substance, "heat_capacity_gas", {"temperature": (T_boil + T_out) / 2})
            except Exception:
                Cp_gas = 35.0
                warnings.append(f"Using default gas Cp = {Cp_gas} J/(mol·K)")

            calculation_steps[-1]["values"] = {"Cp_liq": Cp_liq, "Cp_gas": Cp_gas, "H_vap": H_vap}
            calculation_steps[-1]["formulas"] = [
                f"Cp,液 = {Cp_liq:.2f} J/(mol·K)",
                f"Cp,気 = {Cp_gas:.2f} J/(mol·K)",
                f"ΔHvap = {H_vap:.0f} J/mol = {H_vap/1000:.2f} kJ/mol",
            ]

            # Step 3: 顕熱計算（液体加熱）
            Q_liquid = flow_rate * Cp_liq * (T_boil - T_in)
            calculation_steps.append({
                "step": 3,
                "title": "顕熱計算（液体加熱）/ Sensible Heat (Liquid)",
                "description": f"T_in → T_boil: {T_in:.1f} K → {T_boil:.1f} K",
                "formulas": [
                    "Q₁ = ṁ × Cp,液 × (Tb - T_in)",
                    f"Q₁ = {flow_rate} × {Cp_liq:.2f} × ({T_boil:.1f} - {T_in:.1f})",
                    f"Q₁ = {flow_rate} × {Cp_liq:.2f} × {T_boil - T_in:.1f}",
                    f"Q₁ = {Q_liquid:.1f} W = {Q_liquid/1000:.2f} kW",
                ],
                "values": {"Q_liquid": Q_liquid},
            })

            # Step 4: 潜熱計算（蒸発）
            Q_vap = flow_rate * H_vap
            calculation_steps.append({
                "step": 4,
                "title": "潜熱計算（蒸発）/ Latent Heat (Vaporization)",
                "description": f"沸点での相変化: {T_boil:.1f} K",
                "formulas": [
                    "Q₂ = ṁ × ΔHvap",
                    f"Q₂ = {flow_rate} × {H_vap:.0f}",
                    f"Q₂ = {Q_vap:.1f} W = {Q_vap/1000:.2f} kW",
                ],
                "values": {"Q_vap": Q_vap},
            })

            # Step 5: 顕熱計算（蒸気加熱）
            Q_gas = flow_rate * Cp_gas * (T_out - T_boil)
            calculation_steps.append({
                "step": 5,
                "title": "顕熱計算（蒸気加熱）/ Sensible Heat (Vapor)",
                "description": f"T_boil → T_out: {T_boil:.1f} K → {T_out:.1f} K",
                "formulas": [
                    "Q₃ = ṁ × Cp,気 × (T_out - Tb)",
                    f"Q₃ = {flow_rate} × {Cp_gas:.2f} × ({T_out:.1f} - {T_boil:.1f})",
                    f"Q₃ = {flow_rate} × {Cp_gas:.2f} × {T_out - T_boil:.1f}",
                    f"Q₃ = {Q_gas:.1f} W = {Q_gas/1000:.2f} kW",
                ],
                "values": {"Q_gas": Q_gas},
            })

            sensible_heat = Q_liquid + Q_gas
            latent_heat = Q_vap
            outlet_enthalpy = Cp_liq * (T_boil - T_in) + H_vap + Cp_gas * (T_out - T_boil)

        elif inlet_phase == "vapor" and outlet_phase == "liquid":
            # 蒸気 → 沸点 → 凝縮 → 液体（冷却）
            calculation_steps.append({
                "step": 2,
                "title": "物性値取得 / Heat Capacity & Hvap",
                "description": "気体→液体の相変化あり（凝縮）",
                "formulas": [],
                "values": {},
            })

            try:
                Cp_gas = engine.get_property(substance, "heat_capacity_gas", {"temperature": (T_in + T_boil) / 2})
            except Exception:
                Cp_gas = 35.0
                warnings.append(f"Using default gas Cp = {Cp_gas} J/(mol·K)")

            try:
                Cp_liq = engine.get_property(substance, "heat_capacity_liquid", {"temperature": (T_boil + T_out) / 2})
            except Exception:
                Cp_liq = 75.0
                warnings.append(f"Using default liquid Cp = {Cp_liq} J/(mol·K)")

            calculation_steps[-1]["values"] = {"Cp_liq": Cp_liq, "Cp_gas": Cp_gas, "H_vap": H_vap}
            calculation_steps[-1]["formulas"] = [
                f"Cp,気 = {Cp_gas:.2f} J/(mol·K)",
                f"Cp,液 = {Cp_liq:.2f} J/(mol·K)",
                f"ΔHvap = {H_vap:.0f} J/mol",
            ]

            Q_gas = flow_rate * Cp_gas * (T_boil - T_in)
            Q_cond = -flow_rate * H_vap
            Q_liquid = flow_rate * Cp_liq * (T_out - T_boil)

            sensible_heat = Q_gas + Q_liquid
            latent_heat = Q_cond
            outlet_enthalpy = Cp_gas * (T_boil - T_in) - H_vap + Cp_liq * (T_out - T_boil)

            calculation_steps.append({
                "step": 3,
                "title": "顕熱計算（蒸気冷却）",
                "formulas": [f"Q₁ = {Q_gas:.1f} W = {Q_gas/1000:.2f} kW"],
                "values": {"Q_gas": Q_gas},
            })
            calculation_steps.append({
                "step": 4,
                "title": "潜熱計算（凝縮）",
                "formulas": [f"Q₂ = -{H_vap:.0f} × {flow_rate} = {Q_cond:.1f} W = {Q_cond/1000:.2f} kW"],
                "values": {"Q_cond": Q_cond},
            })
            calculation_steps.append({
                "step": 5,
                "title": "顕熱計算（液体冷却）",
                "formulas": [f"Q₃ = {Q_liquid:.1f} W = {Q_liquid/1000:.2f} kW"],
                "values": {"Q_liquid": Q_liquid},
            })

        else:
            # 相変化なし
            if inlet_phase == "liquid":
                try:
                    Cp = engine.get_property(substance, "heat_capacity_liquid", {"temperature": (T_in + T_out) / 2})
                except Exception:
                    Cp = 75.0
                    warnings.append(f"Using default liquid Cp = {Cp} J/(mol·K)")
            else:
                try:
                    Cp = engine.get_property(substance, "heat_capacity_gas", {"temperature": (T_in + T_out) / 2})
                except Exception:
                    Cp = 35.0
                    warnings.append(f"Using default gas Cp = {Cp} J/(mol·K)")

            calculation_steps.append({
                "step": 2,
                "title": "物性値取得 / Heat Capacity",
                "description": "相変化なし",
                "formulas": [f"Cp = {Cp:.2f} J/(mol·K)"],
                "values": {"Cp": Cp},
            })

            sensible_heat = flow_rate * Cp * (T_out - T_in)
            calculation_steps.append({
                "step": 3,
                "title": "顕熱計算 / Sensible Heat",
                "description": f"ΔT = {T_out - T_in:.1f} K",
                "formulas": [
                    "Q = ṁ × Cp × ΔT",
                    f"Q = {flow_rate} × {Cp:.2f} × {T_out - T_in:.1f}",
                    f"Q = {sensible_heat:.1f} W = {sensible_heat/1000:.2f} kW",
                ],
                "values": {"Q_sensible": sensible_heat},
            })

            outlet_enthalpy = Cp * (T_out - T_in)

    else:
        # 相変化を考慮しない
        try:
            Cp = engine.get_property(substance, "heat_capacity_liquid", {"temperature": (T_in + T_out) / 2})
        except Exception:
            try:
                Cp = engine.get_property(substance, "heat_capacity_gas", {"temperature": (T_in + T_out) / 2})
            except Exception:
                Cp = 75.0
                warnings.append(f"Using default Cp = {Cp} J/(mol·K)")

        calculation_steps.append({
            "step": 2,
            "title": "物性値取得 / Heat Capacity",
            "formulas": [f"Cp = {Cp:.2f} J/(mol·K)"],
            "values": {"Cp": Cp},
        })

        sensible_heat = flow_rate * Cp * (T_out - T_in)
        calculation_steps.append({
            "step": 3,
            "title": "顕熱計算 / Sensible Heat",
            "formulas": [
                "Q = ṁ × Cp × ΔT",
                f"Q = {flow_rate} × {Cp:.2f} × {T_out - T_in:.1f}",
                f"Q = {sensible_heat:.1f} W = {sensible_heat/1000:.2f} kW",
            ],
            "values": {"Q_sensible": sensible_heat},
        })

        outlet_enthalpy = Cp * (T_out - T_in)

    # 反応熱
    reaction_heat = flow_rate * heat_of_reaction

    # 合計熱負荷
    total_heat_duty = sensible_heat + latent_heat + reaction_heat

    # Step: 合計
    calculation_steps.append({
        "step": len(calculation_steps) + 1,
        "title": "合計熱負荷 / Total Heat Duty",
        "description": "",
        "formulas": [
            "Q_total = Q_sensible + Q_latent + Q_reaction",
            f"Q_total = {sensible_heat/1000:.2f} + {latent_heat/1000:.2f} + {reaction_heat/1000:.2f}",
            f"Q_total = {total_heat_duty/1000:.2f} kW",
        ],
        "values": {"Q_total": total_heat_duty},
    })

    # 効率を考慮
    if efficiency > 0 and efficiency < 1:
        actual_heat_duty = total_heat_duty / efficiency
        calculation_steps.append({
            "step": len(calculation_steps) + 1,
            "title": "実熱負荷（効率考慮）/ Actual Duty",
            "description": f"熱効率 η = {efficiency*100:.0f}%",
            "formulas": [
                "Q_actual = Q_total / η",
                f"Q_actual = {total_heat_duty/1000:.2f} / {efficiency}",
                f"Q_actual = {actual_heat_duty/1000:.2f} kW",
            ],
            "values": {"Q_actual": actual_heat_duty},
        })
    else:
        actual_heat_duty = total_heat_duty
        if efficiency <= 0:
            warnings.append("Efficiency is zero or negative, using ideal duty")

    return {
        "success": True,
        "outputs": {
            "sensible_heat": sensible_heat / 1000,
            "latent_heat": latent_heat / 1000,
            "reaction_heat": reaction_heat / 1000,
            "total_heat_duty": total_heat_duty / 1000,
            "actual_heat_duty": actual_heat_duty / 1000,
            "inlet_enthalpy": inlet_enthalpy,
            "outlet_enthalpy": outlet_enthalpy,
            "phase_info": {
                "inlet_phase": inlet_phase,
                "outlet_phase": outlet_phase,
                "boiling_point": T_boil,
                "has_phase_change": inlet_phase != outlet_phase,
            },
            "conditions": {
                "substance": substance,
                "flow_rate": flow_rate,
                "inlet_temperature": T_in,
                "outlet_temperature": T_out,
                "pressure": P,
                "efficiency": efficiency,
            },
            "calculation_steps": calculation_steps,
        },
        "warnings": warnings,
    }
