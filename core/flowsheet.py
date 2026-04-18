"""
プロセスフローシート データモデル

プロセスシミュレーションのブロック、ストリーム、フローシートを定義する。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StreamData:
    """プロセスストリーム"""
    id: str
    name: str
    source_block: str | None = None  # block_id or None (external feed)
    target_block: str | None = None  # block_id or None (product)
    temperature: float | None = None  # K
    pressure: float | None = None     # Pa
    total_flow: float | None = None   # mol/s
    composition: dict[str, float] = field(default_factory=dict)  # component -> mole fraction
    phase: str = "liquid"  # liquid/vapor/mixed
    enthalpy: float | None = None  # J/mol
    properties: dict[str, Any] = field(default_factory=dict)  # additional properties

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name,
            "source_block": self.source_block, "target_block": self.target_block,
            "temperature": self.temperature, "pressure": self.pressure,
            "total_flow": self.total_flow, "composition": self.composition,
            "phase": self.phase, "enthalpy": self.enthalpy,
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StreamData:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class BlockData:
    """プロセスブロック（ユニットオペレーション）"""
    id: str
    block_type: str  # mixer, splitter, heat_exchanger, reactor, flash
    name: str
    parameters: dict[str, Any] = field(default_factory=dict)
    inlet_streams: list[str] = field(default_factory=list)   # stream_id list
    outlet_streams: list[str] = field(default_factory=list)  # stream_id list
    calculation_result: dict[str, Any] | None = None
    position: dict[str, float] = field(default_factory=dict)  # x, y for UI layout

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "block_type": self.block_type, "name": self.name,
            "parameters": self.parameters,
            "inlet_streams": self.inlet_streams, "outlet_streams": self.outlet_streams,
            "calculation_result": self.calculation_result,
            "position": self.position,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlockData:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class FlowsheetData:
    """プロセスフローシート"""
    id: str
    name: str
    components: list[str] = field(default_factory=list)  # global component list
    blocks: dict[str, BlockData] = field(default_factory=dict)
    streams: dict[str, StreamData] = field(default_factory=dict)
    tear_streams: list[str] = field(default_factory=list)  # for convergence
    convergence_config: dict[str, Any] = field(default_factory=lambda: {
        "method": "successive_substitution",  # or "wegstein"
        "max_iterations": 50,
        "tolerance": 1e-6,
    })

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name,
            "components": self.components,
            "blocks": {k: v.to_dict() for k, v in self.blocks.items()},
            "streams": {k: v.to_dict() for k, v in self.streams.items()},
            "tear_streams": self.tear_streams,
            "convergence_config": self.convergence_config,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FlowsheetData:
        blocks = {k: BlockData.from_dict(v) for k, v in data.get("blocks", {}).items()}
        streams = {k: StreamData.from_dict(v) for k, v in data.get("streams", {}).items()}
        return cls(
            id=data["id"], name=data["name"],
            components=data.get("components", []),
            blocks=blocks, streams=streams,
            tear_streams=data.get("tear_streams", []),
            convergence_config=data.get("convergence_config", {}),
        )

    def get_calculation_order(self) -> list[str]:
        """トポロジカルソートで計算順序を決定"""
        # Build adjacency from streams
        in_degree: dict[str, int] = {bid: 0 for bid in self.blocks}
        adj: dict[str, list[str]] = {bid: [] for bid in self.blocks}

        tear_set = set(self.tear_streams)
        for stream in self.streams.values():
            if stream.id in tear_set:
                continue  # skip tear streams
            src = stream.source_block
            tgt = stream.target_block
            if src and tgt and src in self.blocks and tgt in self.blocks:
                adj[src].append(tgt)
                in_degree[tgt] += 1

        # Kahn's algorithm
        queue = [bid for bid, deg in in_degree.items() if deg == 0]
        order = []
        while queue:
            node = queue.pop(0)
            order.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Add any remaining blocks (cycles)
        for bid in self.blocks:
            if bid not in order:
                order.append(bid)

        return order


def generate_mermaid(flowsheet: FlowsheetData) -> str:
    """フローシートからMermaidダイアグラムテキストを生成"""
    lines = ["graph LR"]

    # Block shapes
    shape_map = {
        "mixer": ("{", "}"),        # rhombus
        "splitter": ("{", "}"),
        "heat_exchanger": ("[[", "]]"),  # subroutine
        "reactor": ("((", "))"),      # circle
        "flash": ("[(", ")]"),        # cylinder
    }

    for block in flowsheet.blocks.values():
        left, right = shape_map.get(block.block_type, ("[", "]"))
        lines.append(f"    {block.id}{left}{block.name}{right}")

    for stream in flowsheet.streams.values():
        src = stream.source_block or "FEED"
        tgt = stream.target_block or "PRODUCT"
        # Build label
        parts = []
        if stream.total_flow is not None:
            parts.append(f"{stream.total_flow:.1f} mol/s")
        if stream.temperature is not None:
            parts.append(f"{stream.temperature:.0f} K")
        label = ", ".join(parts)
        if label:
            lines.append(f"    {src} -->|{label}| {tgt}")
        else:
            lines.append(f"    {src} --> {tgt}")

    return "\n".join(lines)
