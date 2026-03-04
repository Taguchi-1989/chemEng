"""
T-x-y 相図生成テンプレート

二成分系のT-x-y線図（泡点曲線・露点曲線）データを生成する。
"""

from __future__ import annotations

from typing import Any


def execute(params: dict[str, Any], engine=None) -> dict[str, Any]:
    """
    T-x-y相図データを生成

    Args:
        params: 入力パラメータ
            - light_component: 軽沸成分名
            - heavy_component: 重沸成分名
            - pressure: 操作圧力 (Pa), default 101325
            - points: データ点数, default 21
        engine: 計算エンジン（thermo）

    Returns:
        x, y, T_bubble, T_dew, bp_light, bp_heavy
    """
    light_comp = params["light_component"]
    heavy_comp = params["heavy_component"]
    pressure = params.get("pressure", 101325.0)
    points = params.get("points", 21)

    if points < 2:
        points = 2
    if points > 200:
        points = 200

    if engine is None or not engine.is_available():
        return {
            "success": False,
            "errors": ["Thermo engine is not available"],
        }

    substances = [light_comp, heavy_comp]
    x_values = []
    y_values = []
    T_bubble = []
    T_dew = []
    warnings = []

    try:
        # 泡点曲線：液相組成を0→1でスキャン
        for i in range(points):
            x_light = i / (points - 1)
            composition = {light_comp: x_light, heavy_comp: 1 - x_light}

            bubble = engine.calculate_bubble_point(substances, composition, pressure)

            x_values.append(x_light)
            T_bubble.append(bubble["bubble_point_temperature"])
            y_values.append(bubble["vapor_composition"].get(light_comp, x_light))

            if not bubble.get("converged", True):
                warnings.append(f"Bubble point did not converge at x={x_light:.3f}")

        # 露点曲線：気相組成を0→1でスキャン
        for i in range(points):
            y_light = i / (points - 1)
            composition = {light_comp: y_light, heavy_comp: 1 - y_light}

            dew = engine.calculate_dew_point(substances, composition, pressure)
            T_dew.append(dew["dew_point_temperature"])

            if not dew.get("converged", True):
                warnings.append(f"Dew point did not converge at y={y_light:.3f}")

        # 純成分の沸点
        bp_light = engine.get_property(light_comp, "boiling_point", {"pressure": pressure})
        bp_heavy = engine.get_property(heavy_comp, "boiling_point", {"pressure": pressure})

        result = {
            "success": True,
            "light_component": light_comp,
            "heavy_component": heavy_comp,
            "pressure": pressure,
            "x": x_values,
            "y": y_values,
            "T_bubble": T_bubble,
            "T_dew": T_dew,
            "bp_light": bp_light,
            "bp_heavy": bp_heavy,
        }

        if warnings:
            result["warnings"] = warnings

        return result

    except Exception:
        # Registry層の safe_error_message で安全に変換されるため、再raise
        raise
