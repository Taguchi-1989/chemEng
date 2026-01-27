"""
物質収支テンプレート

定常状態のプロセスにおける物質収支（マスバランス）を計算する。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Stream:
    """ストリーム"""
    name: str
    flow_rate: float | None = None  # mol/s or kg/s
    composition: dict[str, float] = field(default_factory=dict)  # mol or mass fraction
    component_flows: dict[str, float] = field(default_factory=dict)  # mol/s or kg/s per component

    def calculate_component_flows(self, components: list[str]):
        """成分流量を計算"""
        if self.flow_rate is not None and self.composition:
            self.component_flows = {
                comp: self.flow_rate * self.composition.get(comp, 0.0)
                for comp in components
            }

    def calculate_from_component_flows(self, components: list[str]):
        """成分流量から全流量と組成を計算"""
        total = sum(self.component_flows.get(comp, 0.0) for comp in components)
        if total > 0:
            self.flow_rate = total
            self.composition = {
                comp: self.component_flows.get(comp, 0.0) / total
                for comp in components
            }

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "flow_rate": self.flow_rate,
            "composition": self.composition,
            "component_flows": self.component_flows,
        }


def execute(params: dict[str, Any], engine=None) -> dict[str, Any]:
    """
    物質収支を実行

    Args:
        params: 入力パラメータ
            - components: 成分リスト
            - inlet_streams: 入口ストリーム
            - outlet_streams: 出口ストリーム（部分情報）
            - basis: 計算基準（molar/mass）
            - split_fractions: 分配係数
        engine: 計算エンジン（物性取得用）

    Returns:
        計算結果
    """
    components = params["components"]
    inlet_data = params["inlet_streams"]
    outlet_data = params.get("outlet_streams", [])
    basis = params.get("basis", "molar")
    split_fractions = params.get("split_fractions", {})

    warnings = []
    calculation_steps = []  # 計算過程を記録

    # Step 1: 入力条件
    calculation_steps.append({
        "step": 1,
        "title": "入力条件 / Input Conditions",
        "description": f"成分: {', '.join(components)}",
        "formulas": [
            f"成分数: {len(components)}",
            f"入口ストリーム数: {len(inlet_data)}",
            f"出口ストリーム数: {len(outlet_data)}",
            f"計算基準: {basis}",
        ],
        "values": {"components": components, "basis": basis},
    })

    # Step 2: 入口ストリームを解析
    inlet_streams = []
    inlet_formulas = []
    for data in inlet_data:
        stream = Stream(
            name=data["name"],
            flow_rate=data.get("flow_rate"),
            composition=data.get("composition", {}),
        )
        stream.calculate_component_flows(components)
        inlet_streams.append(stream)

        # 計算式を記録
        inlet_formulas.append(f"【{stream.name}】")
        inlet_formulas.append(f"  全流量: {stream.flow_rate}")
        for comp in components:
            comp_flow = stream.component_flows.get(comp, 0.0)
            comp_frac = stream.composition.get(comp, 0.0)
            inlet_formulas.append(f"  {comp}: {stream.flow_rate} × {comp_frac:.4f} = {comp_flow:.4f}")

    calculation_steps.append({
        "step": 2,
        "title": "入口ストリーム / Inlet Streams",
        "description": "各入口の成分流量を計算",
        "formulas": inlet_formulas,
        "values": {"inlet_streams": [s.to_dict() for s in inlet_streams]},
    })

    # Step 3: 入口合計を計算
    inlet_total_flows = {comp: 0.0 for comp in components}
    for stream in inlet_streams:
        for comp in components:
            inlet_total_flows[comp] += stream.component_flows.get(comp, 0.0)

    total_inlet = sum(inlet_total_flows.values())
    inlet_total_composition = {
        comp: inlet_total_flows[comp] / total_inlet if total_inlet > 0 else 0.0
        for comp in components
    }

    total_formulas = ["入口合計成分流量:"]
    for comp in components:
        total_formulas.append(f"  {comp}: {inlet_total_flows[comp]:.4f}")
    total_formulas.append(f"")
    total_formulas.append(f"全入口流量: {total_inlet:.4f}")
    total_formulas.append(f"")
    total_formulas.append("入口合計組成:")
    for comp in components:
        total_formulas.append(f"  {comp}: {inlet_total_composition[comp]:.4f}")

    calculation_steps.append({
        "step": 3,
        "title": "入口合計 / Inlet Total",
        "description": "全入口ストリームの合計",
        "formulas": total_formulas,
        "values": {"total_inlet": total_inlet, "inlet_total_flows": inlet_total_flows},
    })

    # 出口ストリームを解析・計算
    outlet_streams = []
    remaining_flows = dict(inlet_total_flows)  # 残り成分流量

    for data in outlet_data:
        stream = Stream(
            name=data["name"],
            flow_rate=data.get("flow_rate"),
            composition=data.get("composition", {}),
        )

        # 流量と組成が両方わかっている場合
        if stream.flow_rate is not None and stream.composition:
            stream.calculate_component_flows(components)
            for comp in components:
                remaining_flows[comp] -= stream.component_flows.get(comp, 0.0)

        # 組成だけわかっている場合（後で計算）
        elif stream.composition:
            pass  # 後で残りから計算

        outlet_streams.append(stream)

    # 組成だけわかっている出口ストリームの流量を計算
    # （単純な場合：2出口で1つの組成がわかっている）
    for stream in outlet_streams:
        if stream.flow_rate is None and stream.composition:
            # 分配係数が指定されている場合
            if split_fractions:
                stream.component_flows = {}
                for comp in components:
                    if comp in split_fractions:
                        frac = split_fractions[comp].get(stream.name, 0.0)
                        stream.component_flows[comp] = inlet_total_flows[comp] * frac
                    else:
                        # 組成から逆算
                        pass
                stream.calculate_from_component_flows(components)
            else:
                # 連立方程式を解く（簡易実装：2成分2出口の場合）
                if len(components) == 2 and len(outlet_streams) == 2:
                    _solve_two_component_balance(
                        components, inlet_total_flows, outlet_streams, warnings
                    )
                    break

    # 残りの出口ストリームを計算
    for stream in outlet_streams:
        if stream.flow_rate is None and not stream.composition:
            # 残り全部
            stream.component_flows = dict(remaining_flows)
            stream.calculate_from_component_flows(components)

    # Step 4: 出口合計を計算
    outlet_total_flows = {comp: 0.0 for comp in components}
    for stream in outlet_streams:
        for comp in components:
            outlet_total_flows[comp] += stream.component_flows.get(comp, 0.0)

    total_outlet = sum(outlet_total_flows.values())
    outlet_total_composition = {
        comp: outlet_total_flows[comp] / total_outlet if total_outlet > 0 else 0.0
        for comp in components
    }

    outlet_formulas = ["出口ストリーム成分流量:"]
    for stream in outlet_streams:
        outlet_formulas.append(f"【{stream.name}】")
        outlet_formulas.append(f"  全流量: {stream.flow_rate:.4f}" if stream.flow_rate else "  全流量: 未定")
        for comp in components:
            comp_flow = stream.component_flows.get(comp, 0.0)
            outlet_formulas.append(f"  {comp}: {comp_flow:.4f}")
    outlet_formulas.append("")
    outlet_formulas.append("出口合計成分流量:")
    for comp in components:
        outlet_formulas.append(f"  {comp}: {outlet_total_flows[comp]:.4f}")
    outlet_formulas.append(f"")
    outlet_formulas.append(f"全出口流量: {total_outlet:.4f}")

    calculation_steps.append({
        "step": 4,
        "title": "出口ストリーム / Outlet Streams",
        "description": "各出口の成分流量",
        "formulas": outlet_formulas,
        "values": {"total_outlet": total_outlet, "outlet_total_flows": outlet_total_flows},
    })

    # Step 5: 収支チェック
    balance_check = {}
    balance_formulas = ["成分収支チェック:", "入口 = 出口 + 蓄積（定常状態では蓄積=0）", ""]
    for comp in components:
        diff = inlet_total_flows[comp] - outlet_total_flows[comp]
        rel_err = abs(diff) / inlet_total_flows[comp] if inlet_total_flows[comp] > 0 else 0.0
        balance_check[comp] = {
            "inlet": inlet_total_flows[comp],
            "outlet": outlet_total_flows[comp],
            "difference": diff,
            "relative_error": rel_err,
        }
        balance_formulas.append(f"【{comp}】")
        balance_formulas.append(f"  入口: {inlet_total_flows[comp]:.4f}")
        balance_formulas.append(f"  出口: {outlet_total_flows[comp]:.4f}")
        balance_formulas.append(f"  差分: {diff:.4f}")
        balance_formulas.append(f"  相対誤差: {rel_err*100:.2f}%")

    # 閉合率
    total_diff = sum(abs(b["difference"]) for b in balance_check.values())
    closure = (1 - total_diff / total_inlet) * 100 if total_inlet > 0 else 100.0

    balance_formulas.append("")
    balance_formulas.append(f"閉合率 / Closure = {closure:.2f}%")
    if closure >= 99.0:
        balance_formulas.append("✓ 収支が閉じています")
    else:
        balance_formulas.append("⚠ 収支が閉じていません")

    calculation_steps.append({
        "step": 5,
        "title": "収支チェック / Balance Check",
        "description": "物質収支の検証",
        "formulas": balance_formulas,
        "values": {"closure": closure, "balance_check": balance_check},
    })

    if closure < 99.0:
        warnings.append(f"Mass balance closure is {closure:.2f}%")

    return {
        "success": True,
        "outputs": {
            "inlet_total": {
                "flow_rate": total_inlet,
                "composition": inlet_total_composition,
                "component_flows": inlet_total_flows,
            },
            "outlet_total": {
                "flow_rate": total_outlet,
                "composition": outlet_total_composition,
                "component_flows": outlet_total_flows,
            },
            "inlet_streams": [s.to_dict() for s in inlet_streams],
            "outlet_streams": [s.to_dict() for s in outlet_streams],
            "balance_check": balance_check,
            "closure": closure,
            "basis": basis,
            "calculation_steps": calculation_steps,
        },
        "warnings": warnings,
    }


def _solve_two_component_balance(
    components: list[str],
    inlet_flows: dict[str, float],
    outlet_streams: list[Stream],
    warnings: list[str],
):
    """
    2成分2出口の物質収支を解く

    入口: F, zF
    出口1: D, xD（組成既知）
    出口2: B, xB（組成既知）

    F = D + B
    F * zF[i] = D * xD[i] + B * xB[i]
    """
    comp1, comp2 = components[0], components[1]

    F1 = inlet_flows[comp1]
    F2 = inlet_flows[comp2]
    F = F1 + F2
    zF1 = F1 / F if F > 0 else 0

    stream1, stream2 = outlet_streams[0], outlet_streams[1]

    xD1 = stream1.composition.get(comp1, 0.0)
    xB1 = stream2.composition.get(comp1, 0.0)

    # D = F * (zF1 - xB1) / (xD1 - xB1)
    denom = xD1 - xB1
    if abs(denom) < 1e-10:
        warnings.append("Cannot solve: outlet compositions are too similar")
        return

    D = F * (zF1 - xB1) / denom
    B = F - D

    if D < 0 or B < 0:
        warnings.append(f"Negative flow calculated: D={D:.2f}, B={B:.2f}")
        D = max(0, D)
        B = max(0, B)

    # 成分流量を設定
    stream1.flow_rate = D
    stream1.component_flows = {
        comp1: D * xD1,
        comp2: D * (1 - xD1),
    }

    stream2.flow_rate = B
    stream2.component_flows = {
        comp1: B * xB1,
        comp2: B * (1 - xB1),
    }
