"""
要件定義データクラス

ユーザーからの計算要件を構造化して保持する。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class CalculationType(Enum):
    """計算種別"""

    MASS_BALANCE = "mass_balance"
    ENERGY_BALANCE = "energy_balance"
    PROPERTY_ESTIMATION = "property_estimation"
    DISTILLATION = "distillation"
    HEAT_EXCHANGER = "heat_exchanger"
    REACTOR = "reactor"
    REACTION_KINETICS = "reaction_kinetics"
    FLASH = "flash"
    BUBBLE_POINT = "bubble_point"
    DEW_POINT = "dew_point"


@dataclass
class Substance:
    """物質定義"""

    name: str
    cas_number: str | None = None
    formula: str | None = None
    synonyms: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.name:
            raise ValueError("Substance name is required")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Substance":
        """辞書から生成"""
        return cls(
            name=data["name"],
            cas_number=data.get("cas_number"),
            formula=data.get("formula"),
            synonyms=data.get("synonyms", []),
        )

    def to_dict(self) -> dict[str, Any]:
        """辞書に変換"""
        return {
            "name": self.name,
            "cas_number": self.cas_number,
            "formula": self.formula,
            "synonyms": self.synonyms,
        }


@dataclass
class Condition:
    """運転条件"""

    temperature: float | None = None  # K
    pressure: float | None = None  # Pa
    flow_rate: float | None = None  # mol/s or kg/s
    flow_rate_unit: str = "mol/s"
    composition: dict[str, float] = field(default_factory=dict)  # mol fraction
    phase: str | None = None  # "liquid", "vapor", "two-phase"
    quality: float | None = None  # vapor quality (0-1)

    def __post_init__(self):
        if self.composition:
            total = sum(self.composition.values())
            if abs(total - 1.0) > 0.01:
                raise ValueError(f"Composition must sum to 1.0, got {total}")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Condition":
        """辞書から生成"""
        return cls(
            temperature=data.get("temperature"),
            pressure=data.get("pressure"),
            flow_rate=data.get("flow_rate"),
            flow_rate_unit=data.get("flow_rate_unit", "mol/s"),
            composition=data.get("composition", {}),
            phase=data.get("phase"),
            quality=data.get("quality"),
        )

    def to_dict(self) -> dict[str, Any]:
        """辞書に変換"""
        return {
            "temperature": self.temperature,
            "pressure": self.pressure,
            "flow_rate": self.flow_rate,
            "flow_rate_unit": self.flow_rate_unit,
            "composition": self.composition,
            "phase": self.phase,
            "quality": self.quality,
        }


@dataclass
class RequirementSpec:
    """要件仕様"""

    id: str = field(default_factory=lambda: str(uuid4())[:8])
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # 基本情報
    description: str = ""
    calculation_type: CalculationType = CalculationType.PROPERTY_ESTIMATION

    # 対象物質
    substances: list[Substance] = field(default_factory=list)

    # 条件
    inlet_conditions: list[Condition] = field(default_factory=list)
    outlet_conditions: list[Condition] = field(default_factory=list)
    operating_conditions: dict[str, Any] = field(default_factory=dict)

    # 目標・制約
    targets: dict[str, float] = field(default_factory=dict)  # e.g., {"purity": 0.95}
    constraints: dict[str, Any] = field(default_factory=dict)

    # メタデータ
    source: str = "user_input"  # user_input, ai_extracted, imported
    confidence: float = 1.0
    raw_input: str | None = None
    tags: list[str] = field(default_factory=list)

    def update(self):
        """更新時刻を更新"""
        self.updated_at = datetime.now()

    def add_substance(self, substance: Substance):
        """物質を追加"""
        self.substances.append(substance)
        self.update()

    def add_inlet_condition(self, condition: Condition):
        """入口条件を追加"""
        self.inlet_conditions.append(condition)
        self.update()

    def set_target(self, name: str, value: float):
        """目標値を設定"""
        self.targets[name] = value
        self.update()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RequirementSpec":
        """辞書から生成"""
        substances = [Substance.from_dict(s) for s in data.get("substances", [])]
        inlet_conditions = [Condition.from_dict(c) for c in data.get("inlet_conditions", [])]
        outlet_conditions = [Condition.from_dict(c) for c in data.get("outlet_conditions", [])]

        calc_type = data.get("calculation_type", "property_estimation")
        if isinstance(calc_type, str):
            calc_type = CalculationType(calc_type)

        return cls(
            id=data.get("id", str(uuid4())[:8]),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"])
            if "updated_at" in data
            else datetime.now(),
            description=data.get("description", ""),
            calculation_type=calc_type,
            substances=substances,
            inlet_conditions=inlet_conditions,
            outlet_conditions=outlet_conditions,
            operating_conditions=data.get("operating_conditions", {}),
            targets=data.get("targets", {}),
            constraints=data.get("constraints", {}),
            source=data.get("source", "user_input"),
            confidence=data.get("confidence", 1.0),
            raw_input=data.get("raw_input"),
            tags=data.get("tags", []),
        )

    def to_dict(self) -> dict[str, Any]:
        """辞書に変換"""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "description": self.description,
            "calculation_type": self.calculation_type.value,
            "substances": [s.to_dict() for s in self.substances],
            "inlet_conditions": [c.to_dict() for c in self.inlet_conditions],
            "outlet_conditions": [c.to_dict() for c in self.outlet_conditions],
            "operating_conditions": self.operating_conditions,
            "targets": self.targets,
            "constraints": self.constraints,
            "source": self.source,
            "confidence": self.confidence,
            "raw_input": self.raw_input,
            "tags": self.tags,
        }
