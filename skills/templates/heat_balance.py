"""
Heat balance calculation template.

The calculation uses a simple process-energy balance:
Q = n * Cp * dT + n * Hvap + n * dHrxn
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_CP_LIQ = 75.0
DEFAULT_CP_GAS = 35.0
DEFAULT_CP_GENERIC = 75.0


@dataclass
class HeatBalanceContext:
    substance: str
    flow_rate: float
    inlet_temperature: float
    outlet_temperature: float
    pressure: float
    phase_change: bool
    heat_of_reaction: float
    efficiency: float


@dataclass
class HeatBalanceState:
    inlet_phase: str
    outlet_phase: str
    boiling_point: float | None
    sensible_heat: float = 0.0
    latent_heat: float = 0.0
    inlet_enthalpy: float = 0.0
    outlet_enthalpy: float = 0.0


def _add_step(
    calculation_steps: list[dict[str, Any]],
    title: str,
    formulas: list[str],
    values: dict[str, Any],
    description: str = "",
) -> None:
    calculation_steps.append(
        {
            "step": len(calculation_steps) + 1,
            "title": title,
            "description": description,
            "formulas": formulas,
            "values": values,
        }
    )


def _get_phase(temperature: float, boiling_point: float | None) -> str:
    if boiling_point is None:
        return "unknown"
    return "vapor" if temperature > boiling_point else "liquid"


def _get_property_with_fallback(
    engine,
    substance: str,
    property_name: str,
    temperature: float | None,
    fallback: float,
    warning_message: str,
    warnings: list[str],
) -> float:
    conditions = {}
    if temperature is not None:
        conditions["temperature"] = temperature
    try:
        return engine.get_property(substance, property_name, conditions)
    except Exception:
        warnings.append(warning_message)
        return fallback


def _lookup_boiling_point(
    engine,
    substance: str,
    pressure: float,
    phase_change: bool,
    warnings: list[str],
) -> tuple[float | None, bool]:
    try:
        return engine.get_property(substance, "boiling_point", {"pressure": pressure}), phase_change
    except Exception:
        warnings.append("Could not get boiling point, assuming no phase change")
        return None, False


def _lookup_cp_liquid(
    engine,
    substance: str,
    temperature: float,
    warnings: list[str],
) -> float:
    return _get_property_with_fallback(
        engine,
        substance,
        "heat_capacity_liquid",
        temperature,
        DEFAULT_CP_LIQ,
        f"Using default liquid Cp = {DEFAULT_CP_LIQ} J/(mol*K)",
        warnings,
    )


def _lookup_cp_gas(
    engine,
    substance: str,
    temperature: float,
    warnings: list[str],
) -> float:
    return _get_property_with_fallback(
        engine,
        substance,
        "heat_capacity_gas",
        temperature,
        DEFAULT_CP_GAS,
        f"Using default gas Cp = {DEFAULT_CP_GAS} J/(mol*K)",
        warnings,
    )


def _lookup_heat_of_vaporization(
    engine,
    substance: str,
    boiling_point: float,
    warnings: list[str],
) -> float:
    return _get_property_with_fallback(
        engine,
        substance,
        "heat_of_vaporization",
        boiling_point,
        0.0,
        "Could not get heat of vaporization",
        warnings,
    )


def _lookup_generic_cp(
    engine,
    substance: str,
    temperature: float,
    warnings: list[str],
) -> float:
    try:
        return engine.get_property(substance, "heat_capacity_liquid", {"temperature": temperature})
    except Exception:
        try:
            return engine.get_property(substance, "heat_capacity_gas", {"temperature": temperature})
        except Exception:
            warnings.append(f"Using default Cp = {DEFAULT_CP_GENERIC} J/(mol*K)")
            return DEFAULT_CP_GENERIC


def _integrate_cp(
    engine,
    substance: str,
    T_start: float,
    T_end: float,
    phase: str,
    warnings: list[str],
    n_points: int = 5,
) -> tuple[float, list[tuple[float, float]]]:
    """
    Cp(T)を台形則で積分し ∫Cp dT を返す。

    大きな温度差（>50K）では定数Cpの誤差が大きいため、
    複数点でCpを取得して台形積分する。

    Returns:
        (integral, points): 積分値 [J/mol], (T, Cp)のリスト
    """
    lookup_fn = _lookup_cp_liquid if phase == "liquid" else (
        _lookup_cp_gas if phase == "vapor" else _lookup_generic_cp
    )

    dT = abs(T_end - T_start)

    # 温度差が小さい場合は平均温度の1点で十分
    if dT < 50:
        n_points = 1

    if n_points <= 1:
        T_avg = (T_start + T_end) / 2
        cp = lookup_fn(engine, substance, T_avg, warnings)
        return cp * (T_end - T_start), [(T_avg, cp)]

    # 台形則: 複数点でCpを取得
    temperatures = [T_start + i * (T_end - T_start) / n_points for i in range(n_points + 1)]
    cp_values = [lookup_fn(engine, substance, T, warnings) for T in temperatures]
    points = list(zip(temperatures, cp_values))

    # 台形積分
    integral = 0.0
    for i in range(len(temperatures) - 1):
        dt = temperatures[i + 1] - temperatures[i]
        integral += 0.5 * (cp_values[i] + cp_values[i + 1]) * dt

    return integral, points


def _calculate_single_phase_case(
    ctx: HeatBalanceContext,
    engine,
    phase: str,
    calculation_steps: list[dict[str, Any]],
    warnings: list[str],
) -> tuple[float, float]:
    dT = abs(ctx.outlet_temperature - ctx.inlet_temperature)
    use_integration = dT > 50

    integral, cp_points = _integrate_cp(
        engine, ctx.substance,
        ctx.inlet_temperature, ctx.outlet_temperature,
        phase, warnings,
        n_points=5 if use_integration else 1,
    )

    cp_avg = abs(integral / (ctx.outlet_temperature - ctx.inlet_temperature)) if dT > 0 else cp_points[0][1]

    if use_integration:
        cp_detail = [f"Cp integrated over {len(cp_points)} points (trapezoid rule):"]
        for T, cp in cp_points:
            cp_detail.append(f"  T={T:.1f}K: Cp={cp:.2f} J/(mol*K)")
        cp_detail.append(f"∫Cp dT = {integral:.1f} J/mol (effective Cp_avg = {cp_avg:.2f})")
    else:
        cp_detail = [f"Cp = {cp_avg:.2f} J/(mol*K) at T_avg = {cp_points[0][0]:.1f} K"]

    _add_step(
        calculation_steps,
        "Heat Capacity",
        cp_detail,
        {"Cp_avg": cp_avg, "phase": phase, "integrated": use_integration},
        f"{'Multi-point integration (dT={dT:.0f}K > 50K)' if use_integration else 'Single-phase heat capacity'}",
    )

    sensible_heat = ctx.flow_rate * integral
    _add_step(
        calculation_steps,
        "Sensible Heat",
        [
            "Q = n × ∫Cp dT" if use_integration else "Q = n × Cp × dT",
            f"Q = {ctx.flow_rate} × {integral:.2f}",
            f"Q = {sensible_heat:.1f} W = {sensible_heat/1000:.2f} kW",
        ],
        {"Q_sensible": sensible_heat},
        f"dT = {ctx.outlet_temperature - ctx.inlet_temperature:.1f} K",
    )
    return sensible_heat, integral


def _calculate_liquid_to_vapor_case(
    ctx: HeatBalanceContext,
    engine,
    boiling_point: float,
    hvap: float,
    calculation_steps: list[dict[str, Any]],
    warnings: list[str],
) -> tuple[float, float, float]:
    cp_liq = _lookup_cp_liquid(
        engine, ctx.substance, (ctx.inlet_temperature + boiling_point) / 2, warnings
    )
    cp_gas = _lookup_cp_gas(
        engine, ctx.substance, (boiling_point + ctx.outlet_temperature) / 2, warnings
    )

    _add_step(
        calculation_steps,
        "Heat Capacity & Hvap",
        [
            f"Cp_liq = {cp_liq:.2f} J/(mol*K)",
            f"Cp_gas = {cp_gas:.2f} J/(mol*K)",
            f"Hvap = {hvap:.0f} J/mol = {hvap/1000:.2f} kJ/mol",
        ],
        {"Cp_liq": cp_liq, "Cp_gas": cp_gas, "H_vap": hvap},
        "Liquid heating, vaporization, and vapor superheating",
    )

    q_liquid = ctx.flow_rate * cp_liq * (boiling_point - ctx.inlet_temperature)
    q_vaporization = ctx.flow_rate * hvap
    q_gas = ctx.flow_rate * cp_gas * (ctx.outlet_temperature - boiling_point)

    _add_step(
        calculation_steps,
        "Sensible Heat (Liquid)",
        [f"Q = {q_liquid:.1f} W = {q_liquid/1000:.2f} kW"],
        {"Q_liquid": q_liquid},
    )
    _add_step(
        calculation_steps,
        "Latent Heat (Vaporization)",
        [f"Q = {q_vaporization:.1f} W = {q_vaporization/1000:.2f} kW"],
        {"Q_vap": q_vaporization},
    )
    _add_step(
        calculation_steps,
        "Sensible Heat (Vapor)",
        [f"Q = {q_gas:.1f} W = {q_gas/1000:.2f} kW"],
        {"Q_gas": q_gas},
    )

    sensible_heat = q_liquid + q_gas
    outlet_enthalpy = (
        cp_liq * (boiling_point - ctx.inlet_temperature)
        + hvap
        + cp_gas * (ctx.outlet_temperature - boiling_point)
    )
    return sensible_heat, q_vaporization, outlet_enthalpy


def _calculate_vapor_to_liquid_case(
    ctx: HeatBalanceContext,
    engine,
    boiling_point: float,
    hvap: float,
    calculation_steps: list[dict[str, Any]],
    warnings: list[str],
) -> tuple[float, float, float]:
    cp_gas = _lookup_cp_gas(
        engine, ctx.substance, (ctx.inlet_temperature + boiling_point) / 2, warnings
    )
    cp_liq = _lookup_cp_liquid(
        engine, ctx.substance, (boiling_point + ctx.outlet_temperature) / 2, warnings
    )

    _add_step(
        calculation_steps,
        "Heat Capacity & Hvap",
        [
            f"Cp_gas = {cp_gas:.2f} J/(mol*K)",
            f"Cp_liq = {cp_liq:.2f} J/(mol*K)",
            f"Hvap = {hvap:.0f} J/mol",
        ],
        {"Cp_liq": cp_liq, "Cp_gas": cp_gas, "H_vap": hvap},
        "Vapor cooling, condensation, and liquid subcooling",
    )

    q_gas = ctx.flow_rate * cp_gas * (boiling_point - ctx.inlet_temperature)
    q_cond = -ctx.flow_rate * hvap
    q_liquid = ctx.flow_rate * cp_liq * (ctx.outlet_temperature - boiling_point)

    _add_step(
        calculation_steps,
        "Sensible Heat (Vapor Cooling)",
        [f"Q = {q_gas:.1f} W = {q_gas/1000:.2f} kW"],
        {"Q_gas": q_gas},
    )
    _add_step(
        calculation_steps,
        "Latent Heat (Condensation)",
        [f"Q = {q_cond:.1f} W = {q_cond/1000:.2f} kW"],
        {"Q_cond": q_cond},
    )
    _add_step(
        calculation_steps,
        "Sensible Heat (Liquid Cooling)",
        [f"Q = {q_liquid:.1f} W = {q_liquid/1000:.2f} kW"],
        {"Q_liquid": q_liquid},
    )

    sensible_heat = q_gas + q_liquid
    outlet_enthalpy = (
        cp_gas * (boiling_point - ctx.inlet_temperature)
        - hvap
        + cp_liq * (ctx.outlet_temperature - boiling_point)
    )
    return sensible_heat, q_cond, outlet_enthalpy


def _calculate_thermal_load(
    ctx: HeatBalanceContext,
    state: HeatBalanceState,
    engine,
    calculation_steps: list[dict[str, Any]],
    warnings: list[str],
) -> None:
    if not ctx.phase_change or state.boiling_point is None:
        state.sensible_heat, state.outlet_enthalpy = _calculate_single_phase_case(
            ctx, engine, state.inlet_phase, calculation_steps, warnings
        )
        return

    hvap = _lookup_heat_of_vaporization(engine, ctx.substance, state.boiling_point, warnings)

    if state.inlet_phase == "liquid" and state.outlet_phase == "vapor":
        state.sensible_heat, state.latent_heat, state.outlet_enthalpy = _calculate_liquid_to_vapor_case(
            ctx, engine, state.boiling_point, hvap, calculation_steps, warnings
        )
        return

    if state.inlet_phase == "vapor" and state.outlet_phase == "liquid":
        state.sensible_heat, state.latent_heat, state.outlet_enthalpy = _calculate_vapor_to_liquid_case(
            ctx, engine, state.boiling_point, hvap, calculation_steps, warnings
        )
        return

    state.sensible_heat, state.outlet_enthalpy = _calculate_single_phase_case(
        ctx, engine, state.inlet_phase, calculation_steps, warnings
    )


def execute(params: dict[str, Any], engine=None) -> dict[str, Any]:
    """
    Calculate process heat duty.

    Args:
        params: Input parameters.
        engine: Calculation engine.

    Returns:
        Calculation result.
    """
    if engine is None:
        return {
            "success": False,
            "outputs": {},
            "errors": ["No calculation engine available"],
            "warnings": [],
        }

    ctx = HeatBalanceContext(
        substance=params["substance"],
        flow_rate=params["flow_rate"],
        inlet_temperature=params["inlet_temperature"],
        outlet_temperature=params["outlet_temperature"],
        pressure=params.get("pressure") or 101325.0,
        phase_change=params.get("phase_change", True),
        heat_of_reaction=params.get("heat_of_reaction") or 0.0,
        efficiency=params.get("efficiency") or 1.0,
    )

    warnings: list[str] = []
    calculation_steps: list[dict[str, Any]] = []

    # 混合物判定
    is_mixture = any(sep in ctx.substance for sep in (",", "+", "/"))

    if is_mixture:
        # 混合物の場合: 沸点ベースの相判定はできない → 全量を顕熱計算として処理
        warnings.append(
            "Mixture detected: phase determination via boiling point is not valid for mixtures. "
            "Mixtures have a bubble-dew point range, not a single boiling point. "
            "Falling back to sensible-heat-only calculation (no phase change). "
            "For accurate mixture heat duty with phase change, use flash (VLE) calculation. / "
            "混合物が検出されました: 混合物には単一沸点が存在しません（泡点〜露点の温度幅）。"
            "顕熱のみの計算にフォールバックします。相変化を含む場合はフラッシュ計算をご利用ください。"
        )
        ctx.phase_change = False
        state = HeatBalanceState(
            inlet_phase="unknown",
            outlet_phase="unknown",
            boiling_point=None,
        )
        _add_step(
            calculation_steps,
            "Mixture Mode",
            [
                f"Substance: {ctx.substance} (mixture)",
                "Phase determination skipped (no single boiling point for mixtures)",
                "Calculating sensible heat only (Q = n × ∫Cp dT)",
            ],
            {"is_mixture": True},
            "Mixture bypass: no phase change calculation",
        )
        _calculate_thermal_load(ctx, state, engine, calculation_steps, warnings)
    else:
        # 純物質の場合: 通常の沸点ベースの相判定
        boiling_point, phase_change = _lookup_boiling_point(
            engine, ctx.substance, ctx.pressure, ctx.phase_change, warnings
        )
        ctx.phase_change = phase_change

        state = HeatBalanceState(
            inlet_phase=_get_phase(ctx.inlet_temperature, boiling_point),
            outlet_phase=_get_phase(ctx.outlet_temperature, boiling_point),
            boiling_point=boiling_point,
        )

        lookup_formulas: list[str] = []
        lookup_values: dict[str, Any] = {
            "T_boil": boiling_point,
            "inlet_phase": state.inlet_phase,
            "outlet_phase": state.outlet_phase,
        }
        if boiling_point is not None:
            lookup_formulas.append(
                f"Tb = {boiling_point:.2f} K ({boiling_point - 273.15:.1f} C)"
            )
        lookup_formulas.append(f"Inlet phase = {state.inlet_phase} (T_in = {ctx.inlet_temperature} K)")
        lookup_formulas.append(f"Outlet phase = {state.outlet_phase} (T_out = {ctx.outlet_temperature} K)")
        _add_step(
            calculation_steps,
            "Property Lookup",
            lookup_formulas,
            lookup_values,
            f"Substance: {ctx.substance}",
        )
        _calculate_thermal_load(ctx, state, engine, calculation_steps, warnings)

    reaction_heat = ctx.flow_rate * ctx.heat_of_reaction
    total_heat_duty = state.sensible_heat + state.latent_heat + reaction_heat

    _add_step(
        calculation_steps,
        "Total Heat Duty",
        [
            "Q_total = Q_sensible + Q_latent + Q_reaction",
            f"Q_total = {state.sensible_heat/1000:.2f} + {state.latent_heat/1000:.2f} + {reaction_heat/1000:.2f}",
            f"Q_total = {total_heat_duty/1000:.2f} kW",
        ],
        {"Q_total": total_heat_duty},
    )

    if 0 < ctx.efficiency < 1:
        actual_heat_duty = total_heat_duty / ctx.efficiency
        _add_step(
            calculation_steps,
            "Actual Duty",
            [
                "Q_actual = Q_total / eta",
                f"Q_actual = {total_heat_duty/1000:.2f} / {ctx.efficiency}",
                f"Q_actual = {actual_heat_duty/1000:.2f} kW",
            ],
            {"Q_actual": actual_heat_duty},
            f"Efficiency = {ctx.efficiency*100:.0f}%",
        )
    else:
        actual_heat_duty = total_heat_duty
        if ctx.efficiency <= 0:
            warnings.append("Efficiency is zero or negative, using ideal duty")

    return {
        "success": True,
        "outputs": {
            "sensible_heat": state.sensible_heat / 1000,
            "latent_heat": state.latent_heat / 1000,
            "reaction_heat": reaction_heat / 1000,
            "total_heat_duty": total_heat_duty / 1000,
            "actual_heat_duty": actual_heat_duty / 1000,
            "inlet_enthalpy": state.inlet_enthalpy,
            "outlet_enthalpy": state.outlet_enthalpy,
            "phase_info": {
                "inlet_phase": state.inlet_phase,
                "outlet_phase": state.outlet_phase,
                "boiling_point": state.boiling_point,
                "has_phase_change": state.inlet_phase != state.outlet_phase,
            },
            "conditions": {
                "substance": ctx.substance,
                "flow_rate": ctx.flow_rate,
                "inlet_temperature": ctx.inlet_temperature,
                "outlet_temperature": ctx.outlet_temperature,
                "pressure": ctx.pressure,
                "efficiency": ctx.efficiency,
            },
            "calculation_steps": calculation_steps,
        },
        "warnings": warnings,
    }
