"""
計算エンジン基底クラス

各OSSライブラリ（thermo, Cantera, CoolProp）のラッパーの共通インターフェースを定義。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EngineCapability:
    """エンジン能力"""

    # 対応する物性タイプ
    property_types: list[str] = field(default_factory=list)
    # vapor_pressure, density, viscosity, thermal_conductivity,
    # heat_capacity, enthalpy, entropy, fugacity, surface_tension

    # 対応する計算タイプ
    calculation_types: list[str] = field(default_factory=list)
    # property_estimation, vle, lle, sle, flash,
    # bubble_point, dew_point, equilibrium, kinetics

    # 対応する物質
    supported_substances: str = ""
    # organic, inorganic, refrigerants, gases, etc.

    def supports_property(self, property_type: str) -> bool:
        """物性タイプをサポートしているか"""
        return property_type in self.property_types

    def supports_calculation(self, calculation_type: str) -> bool:
        """計算タイプをサポートしているか"""
        return calculation_type in self.calculation_types


class CalculationEngine(ABC):
    """計算エンジン基底クラス"""

    @property
    @abstractmethod
    def name(self) -> str:
        """エンジン名"""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> EngineCapability:
        """エンジン能力"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """ライブラリが利用可能か"""
        pass

    @abstractmethod
    def get_property(
        self, substance: str, property_name: str, conditions: dict[str, float]
    ) -> float:
        """
        物性値を取得

        Args:
            substance: 物質名またはCAS番号
            property_name: 物性名（vapor_pressure, density等）
            conditions: 条件（temperature, pressure等）

        Returns:
            物性値（SI単位）
        """
        pass

    @abstractmethod
    def calculate_equilibrium(
        self,
        substances: list[str],
        composition: dict[str, float],
        conditions: dict[str, float],
    ) -> dict[str, Any]:
        """
        相平衡計算

        Args:
            substances: 物質リスト
            composition: 組成（モル分率）
            conditions: 条件（temperature, pressure等）

        Returns:
            計算結果
        """
        pass

    def get_multiple_properties(
        self,
        substance: str,
        property_names: list[str],
        conditions: dict[str, float],
    ) -> dict[str, float]:
        """
        複数の物性値を一度に取得

        Args:
            substance: 物質名
            property_names: 物性名リスト
            conditions: 条件

        Returns:
            物性名→値の辞書
        """
        result = {}
        for prop in property_names:
            try:
                result[prop] = self.get_property(substance, prop, conditions)
            except (ValueError, NotImplementedError) as e:
                result[prop] = None
        return result

    def __repr__(self) -> str:
        available = "available" if self.is_available() else "not available"
        return f"{self.__class__.__name__}({self.name}, {available})"


class EngineError(Exception):
    """計算エンジンエラー"""

    def __init__(self, engine: str, message: str):
        self.engine = engine
        self.message = message
        super().__init__(f"[{engine}] {message}")


class SubstanceNotFoundError(EngineError):
    """物質が見つからないエラー"""

    def __init__(self, engine: str, substance: str):
        super().__init__(engine, f"Substance not found: {substance}")
        self.substance = substance


class PropertyNotAvailableError(EngineError):
    """物性が利用できないエラー"""

    def __init__(self, engine: str, property_name: str, substance: str):
        super().__init__(engine, f"Property {property_name} not available for {substance}")
        self.property_name = property_name
        self.substance = substance


class ConditionsOutOfRangeError(EngineError):
    """条件が範囲外エラー"""

    def __init__(self, engine: str, message: str):
        super().__init__(engine, f"Conditions out of range: {message}")
