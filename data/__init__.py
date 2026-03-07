"""
物性値データベース - データモデル

ローカルに保存するカスタム物性データの構造を定義。
複数ソースからのデータを出典付きで管理する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PropertyValue:
    """単一物性値（出典情報付き）"""

    property_name: str  # "boiling_point", "vapor_pressure" 等
    value: float  # SI単位の数値
    unit: str  # "K", "Pa" 等

    # 条件（温度・圧力依存の物性用）
    temperature: float | None = None  # K
    pressure: float | None = None  # Pa

    # 出典情報
    source: str = ""  # "pubchem", "thermo", "manual"
    reference: str = ""  # URL/文献名
    confidence: str = "unknown"  # "experimental", "estimated", "predicted"
    retrieved_at: str = ""  # ISO datetime
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "value": self.value,
            "unit": self.unit,
        }
        if self.temperature is not None:
            d["temperature"] = self.temperature
        if self.pressure is not None:
            d["pressure"] = self.pressure
        if self.source:
            d["source"] = self.source
        if self.reference:
            d["reference"] = self.reference
        if self.confidence and self.confidence != "unknown":
            d["confidence"] = self.confidence
        if self.retrieved_at:
            d["retrieved_at"] = self.retrieved_at
        if self.notes:
            d["notes"] = self.notes
        return d

    @classmethod
    def from_dict(cls, property_name: str, data: dict[str, Any]) -> PropertyValue:
        return cls(
            property_name=property_name,
            value=float(data["value"]),
            unit=str(data.get("unit", "")),
            temperature=data.get("temperature"),
            pressure=data.get("pressure"),
            source=str(data.get("source", "")),
            reference=str(data.get("reference", "")),
            confidence=str(data.get("confidence", "unknown")),
            retrieved_at=str(data.get("retrieved_at", "")),
            notes=str(data.get("notes", "")),
        )


@dataclass
class SubstanceRecord:
    """物質レコード（複数ソースの物性値を保持）"""

    name: str
    name_ja: str = ""
    cas: str = ""
    formula: str = ""
    molecular_weight: float | None = None
    inchi: str = ""
    smiles: str = ""
    pubchem_cid: int | None = None
    aliases: list[str] = field(default_factory=list)
    category: str = ""

    # 物性データ（物性名 → 値のリスト、複数ソース対応）
    properties: dict[str, list[PropertyValue]] = field(default_factory=dict)

    # メタデータ
    added_at: str = ""
    updated_at: str = ""
    sources_used: list[str] = field(default_factory=list)

    def get_best_property(self, property_name: str) -> PropertyValue | None:
        """最良の物性値を取得（experimental > estimated > predicted）"""
        values = self.properties.get(property_name, [])
        if not values:
            return None
        priority = {"experimental": 0, "estimated": 1, "predicted": 2, "unknown": 3}
        return sorted(values, key=lambda v: priority.get(v.confidence, 99))[0]

    def list_properties(self) -> list[str]:
        """利用可能な物性名リストを返す"""
        return list(self.properties.keys())

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name}
        if self.name_ja:
            d["name_ja"] = self.name_ja
        if self.cas:
            d["cas"] = self.cas
        if self.formula:
            d["formula"] = self.formula
        if self.molecular_weight is not None:
            d["molecular_weight"] = self.molecular_weight
        if self.inchi:
            d["inchi"] = self.inchi
        if self.smiles:
            d["smiles"] = self.smiles
        if self.pubchem_cid is not None:
            d["pubchem_cid"] = self.pubchem_cid
        if self.aliases:
            d["aliases"] = self.aliases
        if self.category:
            d["category"] = self.category
        if self.added_at:
            d["added_at"] = self.added_at
        if self.updated_at:
            d["updated_at"] = self.updated_at
        if self.sources_used:
            d["sources_used"] = self.sources_used

        if self.properties:
            props: dict[str, list[dict]] = {}
            for prop_name, values in self.properties.items():
                props[prop_name] = [v.to_dict() for v in values]
            d["properties"] = props

        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SubstanceRecord:
        properties: dict[str, list[PropertyValue]] = {}
        raw_props = data.get("properties", {})
        for prop_name, values in raw_props.items():
            if isinstance(values, list):
                properties[prop_name] = [
                    PropertyValue.from_dict(prop_name, v) for v in values
                ]
            elif isinstance(values, dict):
                # 単一値の場合もリストに
                properties[prop_name] = [PropertyValue.from_dict(prop_name, values)]

        return cls(
            name=str(data.get("name", "")),
            name_ja=str(data.get("name_ja", "")),
            cas=str(data.get("cas", "")),
            formula=str(data.get("formula", "")),
            molecular_weight=data.get("molecular_weight"),
            inchi=str(data.get("inchi", "")),
            smiles=str(data.get("smiles", "")),
            pubchem_cid=data.get("pubchem_cid"),
            aliases=data.get("aliases", []),
            category=str(data.get("category", "")),
            properties=properties,
            added_at=str(data.get("added_at", "")),
            updated_at=str(data.get("updated_at", "")),
            sources_used=data.get("sources_used", []),
        )

    def merge_from(self, other: SubstanceRecord) -> None:
        """別レコードの物性データをマージ（既存を上書きしない）"""
        # 基本情報の補完
        if not self.name_ja and other.name_ja:
            self.name_ja = other.name_ja
        if not self.cas and other.cas:
            self.cas = other.cas
        if not self.formula and other.formula:
            self.formula = other.formula
        if self.molecular_weight is None and other.molecular_weight is not None:
            self.molecular_weight = other.molecular_weight
        if not self.smiles and other.smiles:
            self.smiles = other.smiles
        if self.pubchem_cid is None and other.pubchem_cid is not None:
            self.pubchem_cid = other.pubchem_cid

        # エイリアスの追加
        for alias in other.aliases:
            if alias not in self.aliases:
                self.aliases.append(alias)

        # 物性値の追加（同ソースの重複は避ける）
        for prop_name, values in other.properties.items():
            existing = self.properties.setdefault(prop_name, [])
            existing_sources = {v.source for v in existing}
            for v in values:
                if v.source not in existing_sources:
                    existing.append(v)

        # ソース追加
        for src in other.sources_used:
            if src not in self.sources_used:
                self.sources_used.append(src)

        self.updated_at = datetime.now().isoformat()
