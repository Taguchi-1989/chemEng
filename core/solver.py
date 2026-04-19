"""
フローシートソルバー

逐次モジュラー法によるフローシート計算、ゴールシーク、収束トラッカー。
"""
from __future__ import annotations

import copy
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("chemeng")


@dataclass
class ConvergenceRecord:
    """1反復の収束記録"""
    iteration: int
    variables: dict[str, float]
    residuals: dict[str, float]
    max_residual: float


@dataclass
class ConvergenceTracker:
    """収束履歴トラッカー"""
    history: list[ConvergenceRecord] = field(default_factory=list)
    converged: bool = False
    iterations_used: int = 0

    def record(self, iteration: int, variables: dict[str, float], residuals: dict[str, float]):
        max_res = max(abs(v) for v in residuals.values()) if residuals else 0.0
        self.history.append(ConvergenceRecord(
            iteration=iteration, variables=dict(variables),
            residuals=dict(residuals), max_residual=max_res,
        ))

    def to_dict(self) -> dict[str, Any]:
        return {
            "converged": self.converged,
            "iterations_used": self.iterations_used,
            "history": [
                {
                    "iteration": r.iteration,
                    "variables": r.variables,
                    "residuals": r.residuals,
                    "max_residual": r.max_residual,
                }
                for r in self.history
            ],
        }


# ==================== Block Calculators ====================

def calculate_mixer(block_params: dict, inlet_streams: list[dict], components: list[str]) -> dict:
    """ミキサー: 複数入口ストリームを合流"""
    total_flow = sum(s.get("total_flow", 0) or 0 for s in inlet_streams)
    if total_flow <= 0:
        return {"error": "No inlet flow"}

    # Mass-weighted temperature
    total_enthalpy_flow = sum(
        (s.get("total_flow", 0) or 0) * (s.get("temperature", 298.15) or 298.15)
        for s in inlet_streams
    )
    outlet_temp = total_enthalpy_flow / total_flow if total_flow > 0 else 298.15

    # Composition mixing
    comp_flows = {}
    for comp in components:
        comp_flows[comp] = sum(
            (s.get("total_flow", 0) or 0) * (s.get("composition", {}).get(comp, 0) or 0)
            for s in inlet_streams
        )
    composition = {comp: flow / total_flow for comp, flow in comp_flows.items()} if total_flow > 0 else {}

    # Pressure = min of inlets
    pressures = [s.get("pressure") for s in inlet_streams if s.get("pressure") is not None]
    pressure = min(pressures) if pressures else 101325.0

    return {
        "outlet": {
            "total_flow": total_flow,
            "temperature": outlet_temp,
            "pressure": pressure,
            "composition": composition,
            "phase": "liquid",
        }
    }


def calculate_splitter(block_params: dict, inlet_streams: list[dict], components: list[str]) -> dict:
    """スプリッター: ストリームを分割比で分岐"""
    if not inlet_streams:
        return {"error": "No inlet stream"}

    inlet = inlet_streams[0]
    split_ratio = block_params.get("split_ratio", 0.5)

    base_flow = inlet.get("total_flow", 0) or 0
    outlet1 = {
        "total_flow": base_flow * split_ratio,
        "temperature": inlet.get("temperature", 298.15),
        "pressure": inlet.get("pressure", 101325.0),
        "composition": dict(inlet.get("composition", {})),
        "phase": inlet.get("phase", "liquid"),
    }
    outlet2 = {
        "total_flow": base_flow * (1 - split_ratio),
        "temperature": inlet.get("temperature", 298.15),
        "pressure": inlet.get("pressure", 101325.0),
        "composition": dict(inlet.get("composition", {})),
        "phase": inlet.get("phase", "liquid"),
    }

    return {"outlet_1": outlet1, "outlet_2": outlet2}


def calculate_heat_exchanger(block_params: dict, inlet_streams: list[dict], components: list[str]) -> dict:
    """熱交換器: 出口温度指定またはデューティ指定"""
    if not inlet_streams:
        return {"error": "No inlet stream"}

    inlet = inlet_streams[0]
    inlet_temp = inlet.get("temperature", 298.15) or 298.15
    total_flow = inlet.get("total_flow", 0) or 0

    outlet_temp = block_params.get("outlet_temperature")
    duty = block_params.get("duty")  # kW
    cp = block_params.get("cp", 75.0)  # J/(mol*K) default water

    if outlet_temp is not None:
        # Calculate duty from temperature spec
        duty_calc = total_flow * cp * (outlet_temp - inlet_temp) / 1000  # kW
    elif duty is not None:
        # Calculate outlet temp from duty spec
        outlet_temp = inlet_temp + (duty * 1000) / (total_flow * cp) if total_flow * cp > 0 else inlet_temp
        duty_calc = duty
    else:
        outlet_temp = inlet_temp
        duty_calc = 0.0

    return {
        "outlet": {
            "total_flow": total_flow,
            "temperature": outlet_temp,
            "pressure": inlet.get("pressure", 101325.0),
            "composition": dict(inlet.get("composition", {})),
            "phase": inlet.get("phase", "liquid"),
        },
        "duty_kW": duty_calc,
    }


def calculate_reactor(block_params: dict, inlet_streams: list[dict], components: list[str]) -> dict:
    """転化率反応器: 指定転化率で反応"""
    if not inlet_streams:
        return {"error": "No inlet stream"}

    inlet = inlet_streams[0]
    total_flow = inlet.get("total_flow", 0) or 0
    composition = dict(inlet.get("composition", {}))

    key_component = block_params.get("key_component", "")
    conversion = block_params.get("conversion", 0.0)
    stoichiometry = block_params.get("stoichiometry", {})  # {comp: coeff} relative to key
    outlet_temperature = block_params.get("outlet_temperature", inlet.get("temperature", 298.15))

    if key_component and key_component in composition:
        key_flow = total_flow * composition.get(key_component, 0)
        reacted = key_flow * conversion

        # Update component flows
        comp_flows = {comp: total_flow * frac for comp, frac in composition.items()}
        comp_flows[key_component] -= reacted

        for comp, coeff in stoichiometry.items():
            if comp != key_component and comp in comp_flows:
                comp_flows[comp] += reacted * coeff

        new_total = sum(max(0, f) for f in comp_flows.values())
        new_composition = {comp: max(0, f) / new_total for comp, f in comp_flows.items()} if new_total > 0 else composition
    else:
        new_total = total_flow
        new_composition = composition

    return {
        "outlet": {
            "total_flow": new_total,
            "temperature": outlet_temperature,
            "pressure": inlet.get("pressure", 101325.0),
            "composition": new_composition,
            "phase": inlet.get("phase", "liquid"),
        },
    }


def calculate_flash(block_params: dict, inlet_streams: list[dict], components: list[str]) -> dict:
    """フラッシュドラム: 簡易気液分離（Rachford-Rice省略、固定分配）"""
    if not inlet_streams:
        return {"error": "No inlet stream"}

    inlet = inlet_streams[0]
    total_flow = inlet.get("total_flow", 0) or 0
    vapor_fraction = block_params.get("vapor_fraction", 0.5)
    temperature = block_params.get("temperature", inlet.get("temperature", 298.15))
    pressure = block_params.get("pressure", inlet.get("pressure", 101325.0))

    # K-values (simplified - in production, use thermo engine)
    k_values = block_params.get("k_values", {})
    composition = inlet.get("composition", {})

    vapor_flow = total_flow * vapor_fraction
    liquid_flow = total_flow * (1 - vapor_fraction)

    vapor_comp = {}
    liquid_comp = {}
    for comp in components:
        z = composition.get(comp, 0)
        k = k_values.get(comp, 1.0)
        # Simplified flash: y = K*x, z = V*y + L*x
        if vapor_fraction * k + (1 - vapor_fraction) > 0:
            x = z / (vapor_fraction * k + (1 - vapor_fraction))
            y = k * x
        else:
            x = z
            y = z
        liquid_comp[comp] = x
        vapor_comp[comp] = y

    return {
        "vapor_outlet": {
            "total_flow": vapor_flow,
            "temperature": temperature,
            "pressure": pressure,
            "composition": vapor_comp,
            "phase": "vapor",
        },
        "liquid_outlet": {
            "total_flow": liquid_flow,
            "temperature": temperature,
            "pressure": pressure,
            "composition": liquid_comp,
            "phase": "liquid",
        },
    }


# Block calculator registry
BLOCK_CALCULATORS: dict[str, Callable] = {
    "mixer": calculate_mixer,
    "splitter": calculate_splitter,
    "heat_exchanger": calculate_heat_exchanger,
    "reactor": calculate_reactor,
    "flash": calculate_flash,
}


# ==================== Sequential Modular Solver ====================

class SequentialModularSolver:
    """逐次モジュラー法フローシートソルバー"""

    def __init__(self, flowsheet_data: dict):
        from .flowsheet import FlowsheetData
        self.flowsheet = FlowsheetData.from_dict(flowsheet_data)
        self.tracker = ConvergenceTracker()

    def solve(self) -> dict[str, Any]:
        """フローシート全体を計算"""
        start = time.perf_counter()
        config = self.flowsheet.convergence_config or {}
        max_iter = config.get("max_iterations", 50)
        tol = config.get("tolerance", 1e-6)
        method = config.get("method", "successive_substitution")

        order = self.flowsheet.get_calculation_order()
        tear_set = set(self.flowsheet.tear_streams)
        has_tears = bool(tear_set)

        # Initialize tear stream values (use current values as initial guess)
        prev_tear_values: dict[str, dict[str, float]] = {}
        for sid in tear_set:
            s = self.flowsheet.streams.get(sid)
            if s:
                prev_tear_values[sid] = {
                    "total_flow": s.total_flow or 0,
                    "temperature": s.temperature or 298.15,
                }

        converged = False
        wegstein_prev: dict[str, dict[str, float]] = {}

        for iteration in range(max_iter):
            # Calculate each block in order
            for block_id in order:
                self._calculate_block(block_id)

            if not has_tears:
                converged = True
                self.tracker.iterations_used = 1
                break

            # Check tear stream convergence
            residuals = {}
            new_tear_values: dict[str, dict[str, float]] = {}
            for sid in tear_set:
                s = self.flowsheet.streams.get(sid)
                if not s:
                    continue
                new_vals = {
                    "total_flow": s.total_flow or 0,
                    "temperature": s.temperature or 298.15,
                }
                new_tear_values[sid] = new_vals
                prev = prev_tear_values.get(sid, {})
                for key in new_vals:
                    prev_val = prev.get(key, 0)
                    new_val = new_vals[key]
                    denom = max(abs(prev_val), 1e-10)
                    residuals[f"{sid}.{key}"] = abs(new_val - prev_val) / denom

            variables = {}
            for sid, vals in new_tear_values.items():
                for key, val in vals.items():
                    variables[f"{sid}.{key}"] = val

            self.tracker.record(iteration, variables, residuals)

            max_res = max(residuals.values()) if residuals else 0.0
            if max_res < tol:
                converged = True
                self.tracker.converged = True
                self.tracker.iterations_used = iteration + 1
                break

            # Update tear streams for next iteration
            if method == "wegstein" and iteration > 0:
                # Wegstein acceleration
                for sid in tear_set:
                    new_v = new_tear_values.get(sid, {})
                    prev_v = prev_tear_values.get(sid, {})
                    wprev = wegstein_prev.get(sid, {})
                    s = self.flowsheet.streams.get(sid)
                    if not s:
                        continue
                    for key in ["total_flow", "temperature"]:
                        x_new = new_v.get(key, 0)
                        x_old = prev_v.get(key, 0)
                        g_old = wprev.get(key, x_old)
                        dx = x_new - x_old
                        dg = x_new - g_old
                        if abs(dx) > 1e-12 and abs(dg - dx) > 1e-12:
                            slope = dg / dx
                            q = slope / (slope - 1)
                            q = max(-5.0, min(q, 0.0))  # bound
                            accelerated = q * x_old + (1 - q) * x_new
                        else:
                            accelerated = x_new
                        if key == "total_flow":
                            s.total_flow = accelerated
                        elif key == "temperature":
                            s.temperature = accelerated
                    wegstein_prev[sid] = dict(new_v)

            prev_tear_values = new_tear_values

        if not converged and has_tears:
            self.tracker.converged = False
            self.tracker.iterations_used = max_iter

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return {
            "success": converged or not has_tears,
            "flowsheet": self.flowsheet.to_dict(),
            "convergence": self.tracker.to_dict(),
            "execution_time_ms": elapsed_ms,
            "warnings": [] if converged else ["Convergence not achieved / 収束しませんでした"],
        }

    def _calculate_block(self, block_id: str):
        """単一ブロックを計算"""
        block = self.flowsheet.blocks.get(block_id)
        if not block:
            return

        calculator = BLOCK_CALCULATORS.get(block.block_type)
        if not calculator:
            block.calculation_result = {"error": f"Unknown block type: {block.block_type}"}
            return

        # Gather inlet stream data
        inlet_data = []
        for sid in block.inlet_streams:
            s = self.flowsheet.streams.get(sid)
            if s:
                inlet_data.append(s.to_dict())

        result = calculator(block.parameters, inlet_data, self.flowsheet.components)
        block.calculation_result = result

        # Propagate results to outlet streams
        self._propagate_outputs(block, result)

    def _propagate_outputs(self, block, result: dict):
        """計算結果を出口ストリームに反映"""
        if not block.outlet_streams:
            return

        if len(block.outlet_streams) == 1 and "outlet" in result:
            self._update_stream(block.outlet_streams[0], result["outlet"])
        elif len(block.outlet_streams) == 2:
            # splitter or flash with two outlets
            if "outlet_1" in result:
                self._update_stream(block.outlet_streams[0], result["outlet_1"])
            if "outlet_2" in result:
                self._update_stream(block.outlet_streams[1], result["outlet_2"])
            if "vapor_outlet" in result:
                self._update_stream(block.outlet_streams[0], result["vapor_outlet"])
            if "liquid_outlet" in result:
                self._update_stream(block.outlet_streams[1], result["liquid_outlet"])
        else:
            # Try matching by index
            for i, sid in enumerate(block.outlet_streams):
                key = f"outlet_{i+1}"
                if key in result:
                    self._update_stream(sid, result[key])

    def _update_stream(self, stream_id: str, data: dict):
        """ストリームデータを更新"""
        stream = self.flowsheet.streams.get(stream_id)
        if not stream:
            return
        if "total_flow" in data:
            stream.total_flow = data["total_flow"]
        if "temperature" in data:
            stream.temperature = data["temperature"]
        if "pressure" in data:
            stream.pressure = data["pressure"]
        if "composition" in data:
            stream.composition = data["composition"]
        if "phase" in data:
            stream.phase = data["phase"]


# ==================== Goal Seek Solver ====================

class GoalSeekSolver:
    """ゴールシークソルバー"""

    def __init__(self, flowsheet_data: dict):
        self.flowsheet_data = flowsheet_data

    def solve(
        self,
        target_variable: str,     # e.g. "stream.S1.temperature"
        target_value: float,
        manipulated_variable: str, # e.g. "block.HX1.parameters.outlet_temperature"
        lower_bound: float,
        upper_bound: float,
        tolerance: float = 1e-6,
        max_iterations: int = 50,
    ) -> dict[str, Any]:
        """ゴールシーク実行"""
        tracker = ConvergenceTracker()

        def objective(x: float) -> float:
            # Set manipulated variable
            data = copy.deepcopy(self.flowsheet_data)
            _set_nested_value(data, manipulated_variable, x)

            # Solve flowsheet
            solver = SequentialModularSolver(data)
            result = solver.solve()

            # Get target variable value
            actual = _get_nested_value(result["flowsheet"], target_variable)
            if actual is None:
                return float('inf')
            return actual - target_value

        # Brent's method (bisection with interpolation)
        try:
            a, b = lower_bound, upper_bound
            fa, fb = objective(a), objective(b)

            if fa * fb > 0:
                return {
                    "success": False,
                    "error": "Target value not bracketed by bounds / 上下限で目標値を挟めません",
                    "convergence": tracker.to_dict(),
                }

            for i in range(max_iterations):
                c = (a + b) / 2
                fc = objective(c)

                tracker.record(i, {"manipulated": c}, {"residual": fc})

                if abs(fc) < tolerance:
                    tracker.converged = True
                    tracker.iterations_used = i + 1

                    # Final solve with converged value
                    final_data = copy.deepcopy(self.flowsheet_data)
                    _set_nested_value(final_data, manipulated_variable, c)
                    final_solver = SequentialModularSolver(final_data)
                    final_result = final_solver.solve()

                    return {
                        "success": True,
                        "manipulated_value": c,
                        "target_achieved": target_value + fc,
                        "flowsheet": final_result["flowsheet"],
                        "convergence": tracker.to_dict(),
                    }

                if fa * fc < 0:
                    b = c
                    fb = fc
                else:
                    a = c
                    fa = fc

            tracker.converged = False
            tracker.iterations_used = max_iterations
            return {
                "success": False,
                "error": "Goal seek did not converge / ゴールシークが収束しませんでした",
                "last_value": (a + b) / 2,
                "convergence": tracker.to_dict(),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "convergence": tracker.to_dict(),
            }


def _set_nested_value(data: dict, path: str, value: Any):
    """ドット区切りパスで値を設定 (e.g. 'blocks.HX1.parameters.outlet_temperature')"""
    keys = path.split(".")
    obj = data
    for key in keys[:-1]:
        if isinstance(obj, dict):
            obj = obj.setdefault(key, {})
        else:
            return
    if isinstance(obj, dict):
        obj[keys[-1]] = value


def _get_nested_value(data: dict, path: str) -> Any:
    """ドット区切りパスで値を取得"""
    keys = path.split(".")
    obj = data
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key)
        else:
            return None
        if obj is None:
            return None
    return obj
