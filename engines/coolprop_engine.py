"""
CoolProp エンジン

冷媒・純物質の高精度熱力学物性を提供。
120種以上の流体に対応。
"""

from __future__ import annotations

from typing import Any

from .base import (
    CalculationEngine,
    ConditionsOutOfRangeError,
    EngineCapability,
    PropertyNotAvailableError,
    SubstanceNotFoundError,
)

# 条件付きインポート
try:
    import CoolProp.CoolProp as CP
    from CoolProp.CoolProp import PhaseSI, PropsSI
    COOLPROP_AVAILABLE = True
except ImportError:
    COOLPROP_AVAILABLE = False


class CoolPropEngine(CalculationEngine):
    """CoolProp ライブラリラッパー"""

    # 物性キーのマッピング（外部名 → CoolPropキー）
    PROPERTY_MAP = {
        "density": "D",
        "viscosity": "V",
        "thermal_conductivity": "L",
        "heat_capacity": "C",  # Cp
        "heat_capacity_cv": "O",  # Cv
        "enthalpy": "H",
        "entropy": "S",
        "internal_energy": "U",
        "gibbs_energy": "G",
        "helmholtz_energy": "HELMHOLTZMASS",
        "speed_of_sound": "SPEED_OF_SOUND",
        "vapor_pressure": "P",  # at saturation
        "saturation_temperature": "T",  # at saturation
        "surface_tension": "I",
        "prandtl_number": "Prandtl",
        "compressibility": "Z",
        "quality": "Q",
    }

    # よく使う冷媒のエイリアス
    REFRIGERANT_ALIASES = {
        "r134a": "R134a",
        "r410a": "R410A",
        "r32": "R32",
        "r22": "R22",
        "r404a": "R404A",
        "r407c": "R407C",
        "r507a": "R507A",
        "r717": "Ammonia",  # アンモニア
        "r744": "CO2",  # 二酸化炭素
        "r290": "Propane",  # プロパン
        "r600a": "IsoButane",  # イソブタン
    }

    @property
    def name(self) -> str:
        return "coolprop"

    @property
    def capabilities(self) -> EngineCapability:
        return EngineCapability(
            property_types=[
                "density",
                "viscosity",
                "thermal_conductivity",
                "heat_capacity",
                "enthalpy",
                "entropy",
                "internal_energy",
                "speed_of_sound",
                "vapor_pressure",
                "saturation_temperature",
                "surface_tension",
                "prandtl_number",
                "compressibility",
            ],
            calculation_types=[
                "property_estimation",
                "saturation",
                "phase_diagram",
                "refrigeration_cycle",
            ],
            supported_substances="refrigerants and pure fluids (>120 compounds)",
        )

    def is_available(self) -> bool:
        return COOLPROP_AVAILABLE

    def _resolve_fluid_name(self, substance: str) -> str:
        """流体名を解決"""
        # エイリアスをチェック
        lower = substance.lower()
        if lower in self.REFRIGERANT_ALIASES:
            return self.REFRIGERANT_ALIASES[lower]
        return substance

    def get_property(
        self, substance: str, property_name: str, conditions: dict[str, float]
    ) -> float:
        """物性値を取得"""
        if not COOLPROP_AVAILABLE:
            raise ImportError("CoolProp library not installed")

        fluid = self._resolve_fluid_name(substance)
        prop_key = self.PROPERTY_MAP.get(property_name)

        if prop_key is None:
            raise PropertyNotAvailableError(self.name, property_name, substance)

        T = conditions.get("temperature")
        P = conditions.get("pressure")
        Q = conditions.get("quality")  # 乾き度（0=飽和液、1=飽和蒸気）

        try:
            if T is not None and P is not None:
                # T, P指定
                return PropsSI(prop_key, "T", T, "P", P, fluid)

            elif T is not None and Q is not None:
                # T, Q指定（飽和状態）
                return PropsSI(prop_key, "T", T, "Q", Q, fluid)

            elif P is not None and Q is not None:
                # P, Q指定（飽和状態）
                return PropsSI(prop_key, "P", P, "Q", Q, fluid)

            elif T is not None:
                # Tのみ → 飽和液として計算
                return PropsSI(prop_key, "T", T, "Q", 0, fluid)

            elif P is not None:
                # Pのみ → 飽和液として計算
                return PropsSI(prop_key, "P", P, "Q", 0, fluid)

            else:
                raise ConditionsOutOfRangeError(
                    self.name, "Either temperature or pressure must be specified"
                )

        except ValueError as e:
            if "not in the two-phase" in str(e) or "out of range" in str(e).lower():
                raise ConditionsOutOfRangeError(self.name, str(e)) from e
            raise SubstanceNotFoundError(self.name, substance) from e

    def calculate_equilibrium(
        self,
        substances: list[str],
        composition: dict[str, float],
        conditions: dict[str, float],
    ) -> dict[str, Any]:
        """
        相平衡計算（純物質の飽和状態）

        CoolPropは純物質に特化しているため、混合物は限定的。
        """
        if not COOLPROP_AVAILABLE:
            raise ImportError("CoolProp library not installed")

        if len(substances) > 1:
            raise NotImplementedError(
                "CoolProp mixture support is limited. Use 'thermo' engine for mixtures."
            )

        fluid = self._resolve_fluid_name(substances[0])
        T = conditions.get("temperature")
        P = conditions.get("pressure")

        try:
            if T is not None:
                P_sat = PropsSI("P", "T", T, "Q", 0, fluid)
                rho_l = PropsSI("D", "T", T, "Q", 0, fluid)
                rho_v = PropsSI("D", "T", T, "Q", 1, fluid)
                h_l = PropsSI("H", "T", T, "Q", 0, fluid)
                h_v = PropsSI("H", "T", T, "Q", 1, fluid)

                return {
                    "temperature": T,
                    "saturation_pressure": P_sat,
                    "liquid_density": rho_l,
                    "vapor_density": rho_v,
                    "liquid_enthalpy": h_l,
                    "vapor_enthalpy": h_v,
                    "heat_of_vaporization": h_v - h_l,
                }

            elif P is not None:
                T_sat = PropsSI("T", "P", P, "Q", 0, fluid)
                rho_l = PropsSI("D", "P", P, "Q", 0, fluid)
                rho_v = PropsSI("D", "P", P, "Q", 1, fluid)
                h_l = PropsSI("H", "P", P, "Q", 0, fluid)
                h_v = PropsSI("H", "P", P, "Q", 1, fluid)

                return {
                    "pressure": P,
                    "saturation_temperature": T_sat,
                    "liquid_density": rho_l,
                    "vapor_density": rho_v,
                    "liquid_enthalpy": h_l,
                    "vapor_enthalpy": h_v,
                    "heat_of_vaporization": h_v - h_l,
                }

            else:
                raise ConditionsOutOfRangeError(
                    self.name, "Either temperature or pressure must be specified"
                )

        except Exception as e:
            raise ConditionsOutOfRangeError(self.name, str(e)) from e

    def get_phase(
        self, substance: str, temperature: float, pressure: float
    ) -> str:
        """相を判定"""
        if not COOLPROP_AVAILABLE:
            raise ImportError("CoolProp library not installed")

        fluid = self._resolve_fluid_name(substance)
        try:
            return PhaseSI("T", temperature, "P", pressure, fluid)
        except Exception:
            return "unknown"

    def get_critical_point(self, substance: str) -> dict[str, float]:
        """臨界点を取得"""
        if not COOLPROP_AVAILABLE:
            raise ImportError("CoolProp library not installed")

        fluid = self._resolve_fluid_name(substance)
        try:
            return {
                "critical_temperature": PropsSI("Tcrit", fluid),
                "critical_pressure": PropsSI("Pcrit", fluid),
                "critical_density": PropsSI("rhocrit", fluid),
            }
        except Exception as e:
            raise SubstanceNotFoundError(self.name, substance) from e

    def get_triple_point(self, substance: str) -> dict[str, float]:
        """三重点を取得"""
        if not COOLPROP_AVAILABLE:
            raise ImportError("CoolProp library not installed")

        fluid = self._resolve_fluid_name(substance)
        try:
            return {
                "triple_temperature": PropsSI("Ttriple", fluid),
                "triple_pressure": PropsSI("ptriple", fluid),
            }
        except Exception as e:
            raise SubstanceNotFoundError(self.name, substance) from e

    def calculate_refrigeration_cycle(
        self,
        refrigerant: str,
        evaporator_temperature: float,
        condenser_temperature: float,
        superheat: float = 5.0,
        subcooling: float = 5.0,
        compressor_efficiency: float = 0.75,
    ) -> dict[str, Any]:
        """
        冷凍サイクルの計算（理想蒸気圧縮サイクル）

        Args:
            refrigerant: 冷媒名
            evaporator_temperature: 蒸発温度 (K)
            condenser_temperature: 凝縮温度 (K)
            superheat: 過熱度 (K)
            subcooling: 過冷却度 (K)
            compressor_efficiency: 圧縮機断熱効率

        Returns:
            サイクル特性（COP、冷凍能力等）
        """
        if not COOLPROP_AVAILABLE:
            raise ImportError("CoolProp library not installed")

        fluid = self._resolve_fluid_name(refrigerant)

        try:
            # 蒸発圧力・凝縮圧力
            P_evap = PropsSI("P", "T", evaporator_temperature, "Q", 1, fluid)
            P_cond = PropsSI("P", "T", condenser_temperature, "Q", 0, fluid)

            # 状態点1: 圧縮機入口（過熱蒸気）
            T1 = evaporator_temperature + superheat
            h1 = PropsSI("H", "T", T1, "P", P_evap, fluid)
            s1 = PropsSI("S", "T", T1, "P", P_evap, fluid)

            # 状態点2s: 等エントロピー圧縮後
            h2s = PropsSI("H", "S", s1, "P", P_cond, fluid)

            # 状態点2: 実際の圧縮後
            h2 = h1 + (h2s - h1) / compressor_efficiency
            T2 = PropsSI("T", "H", h2, "P", P_cond, fluid)

            # 状態点3: 凝縮器出口（過冷却液）
            T3 = condenser_temperature - subcooling
            h3 = PropsSI("H", "T", T3, "P", P_cond, fluid)

            # 状態点4: 膨張弁後（等エンタルピー膨張）
            h4 = h3
            T4 = PropsSI("T", "H", h4, "P", P_evap, fluid)
            x4 = PropsSI("Q", "H", h4, "P", P_evap, fluid)  # 乾き度

            # サイクル特性
            q_evap = h1 - h4  # 蒸発器熱量 (J/kg)
            w_comp = h2 - h1  # 圧縮仕事 (J/kg)
            q_cond = h2 - h3  # 凝縮器熱量 (J/kg)

            cop_cooling = q_evap / w_comp  # 冷房COP
            cop_heating = q_cond / w_comp  # 暖房COP

            return {
                "refrigerant": fluid,
                "evaporator_pressure": P_evap,
                "condenser_pressure": P_cond,
                "pressure_ratio": P_cond / P_evap,
                "state_points": {
                    "1_compressor_inlet": {"T": T1, "P": P_evap, "h": h1, "s": s1},
                    "2_compressor_outlet": {"T": T2, "P": P_cond, "h": h2},
                    "3_condenser_outlet": {"T": T3, "P": P_cond, "h": h3},
                    "4_evaporator_inlet": {"T": T4, "P": P_evap, "h": h4, "x": x4},
                },
                "specific_refrigeration_effect": q_evap,  # J/kg
                "specific_compressor_work": w_comp,  # J/kg
                "specific_condenser_heat": q_cond,  # J/kg
                "cop_cooling": cop_cooling,
                "cop_heating": cop_heating,
                "compressor_efficiency": compressor_efficiency,
            }

        except Exception as e:
            raise ConditionsOutOfRangeError(self.name, str(e)) from e

    def get_fluid_list(self) -> list[str]:
        """利用可能な流体のリストを取得"""
        if not COOLPROP_AVAILABLE:
            raise ImportError("CoolProp library not installed")

        # CoolPropの全流体リスト
        fluids = CP.get_global_param_string("FluidsList").split(",")
        return [f.strip() for f in fluids]

    def get_fluid_info(self, substance: str) -> dict[str, Any]:
        """流体情報を取得"""
        if not COOLPROP_AVAILABLE:
            raise ImportError("CoolProp library not installed")

        fluid = self._resolve_fluid_name(substance)
        try:
            return {
                "name": fluid,
                "molecular_weight": PropsSI("M", fluid) * 1000,  # kg/mol → g/mol
                "critical_temperature": PropsSI("Tcrit", fluid),
                "critical_pressure": PropsSI("Pcrit", fluid),
                "critical_density": PropsSI("rhocrit", fluid),
                "triple_temperature": PropsSI("Ttriple", fluid),
                "triple_pressure": PropsSI("ptriple", fluid),
                "acentric_factor": PropsSI("acentric", fluid),
                "gas_constant": PropsSI("gas_constant", fluid),
            }
        except Exception as e:
            raise SubstanceNotFoundError(self.name, substance) from e
