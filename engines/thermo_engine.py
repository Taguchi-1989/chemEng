"""
Thermo/Chemicals エンジン

thermo と chemicals ライブラリを使用した物性推算・相平衡計算。
30,000種以上の有機・無機化合物に対応。
"""

from typing import Any

from .base import (
    CalculationEngine,
    EngineCapability,
    SubstanceNotFoundError,
    PropertyNotAvailableError,
    ConditionsOutOfRangeError,
)

# 条件付きインポート
try:
    from thermo import Chemical, Mixture
    THERMO_AVAILABLE = True
except ImportError:
    THERMO_AVAILABLE = False

try:
    from chemicals import CAS_from_any
    CHEMICALS_AVAILABLE = True
except ImportError:
    CHEMICALS_AVAILABLE = False


class ThermoEngine(CalculationEngine):
    """thermo/chemicals ライブラリラッパー"""

    # 物性名マッピング（外部名 → 内部処理用）
    PROPERTY_MAP = {
        "vapor_pressure": "vapor_pressure",
        "liquid_density": "liquid_density",
        "gas_density": "gas_density",
        "liquid_viscosity": "liquid_viscosity",
        "gas_viscosity": "gas_viscosity",
        "heat_capacity_liquid": "heat_capacity_liquid",
        "heat_capacity_gas": "heat_capacity_gas",
        "thermal_conductivity_liquid": "thermal_conductivity_liquid",
        "thermal_conductivity_gas": "thermal_conductivity_gas",
        "surface_tension": "surface_tension",
        "heat_of_vaporization": "heat_of_vaporization",
        "critical_temperature": "critical_temperature",
        "critical_pressure": "critical_pressure",
        "acentric_factor": "acentric_factor",
        "molecular_weight": "molecular_weight",
        "boiling_point": "boiling_point",
    }

    @property
    def name(self) -> str:
        return "thermo"

    @property
    def capabilities(self) -> EngineCapability:
        return EngineCapability(
            property_types=[
                "vapor_pressure",
                "liquid_density",
                "gas_density",
                "liquid_viscosity",
                "gas_viscosity",
                "heat_capacity_liquid",
                "heat_capacity_gas",
                "thermal_conductivity_liquid",
                "thermal_conductivity_gas",
                "surface_tension",
                "heat_of_vaporization",
                "critical_temperature",
                "critical_pressure",
                "acentric_factor",
                "molecular_weight",
                "boiling_point",
            ],
            calculation_types=[
                "property_estimation",
                "vle",
                "lle",
                "flash",
                "bubble_point",
                "dew_point",
            ],
            supported_substances="organic and inorganic (>30000 compounds)",
        )

    def is_available(self) -> bool:
        return THERMO_AVAILABLE and CHEMICALS_AVAILABLE

    def _get_chemical(self, substance: str, T: float = 298.15, P: float = 101325) -> "Chemical":
        """Chemicalオブジェクトを取得"""
        if not THERMO_AVAILABLE:
            raise ImportError("thermo library not installed")

        try:
            return Chemical(substance, T=T, P=P)
        except Exception as e:
            raise SubstanceNotFoundError(self.name, substance) from e

    def get_property(
        self, substance: str, property_name: str, conditions: dict[str, float]
    ) -> float:
        """物性値を取得"""
        if not self.is_available():
            raise ImportError("thermo/chemicals library not installed")

        if property_name not in self.PROPERTY_MAP:
            raise PropertyNotAvailableError(self.name, property_name, substance)

        T = conditions.get("temperature", 298.15)  # K
        P = conditions.get("pressure", 101325)  # Pa

        try:
            chem = self._get_chemical(substance, T, P)

            # 各物性の計算（Chemicalクラスの属性を使用）
            property_attr_map = {
                "vapor_pressure": "Psat",
                "liquid_density": "rhol",
                "gas_density": "rhog",
                "liquid_viscosity": "mul",
                "gas_viscosity": "mug",
                "heat_capacity_liquid": "Cpl",
                "heat_capacity_gas": "Cpg",
                "thermal_conductivity_liquid": "kl",
                "thermal_conductivity_gas": "kg",
                "surface_tension": "sigma",
                "heat_of_vaporization": "Hvap",
                "critical_temperature": "Tc",
                "critical_pressure": "Pc",
                "acentric_factor": "omega",
                "molecular_weight": "MW",
                "boiling_point": "Tb",
            }

            attr = property_attr_map.get(property_name)
            if attr is None:
                raise PropertyNotAvailableError(self.name, property_name, substance)

            value = getattr(chem, attr, None)
            if value is None:
                raise PropertyNotAvailableError(self.name, property_name, substance)

            return value

        except SubstanceNotFoundError:
            raise
        except PropertyNotAvailableError:
            raise
        except Exception as e:
            raise ConditionsOutOfRangeError(self.name, str(e)) from e

    def calculate_equilibrium(
        self,
        substances: list[str],
        composition: dict[str, float],
        conditions: dict[str, float],
    ) -> dict[str, Any]:
        """相平衡計算（VLE）- Mixtureクラス使用"""
        if not self.is_available():
            raise ImportError("thermo/chemicals library not installed")

        T = conditions.get("temperature", 298.15)
        P = conditions.get("pressure", 101325)

        try:
            zs = [composition.get(s, 0.0) for s in substances]

            # 組成の正規化
            total = sum(zs)
            if total > 0:
                zs = [z / total for z in zs]

            # Mixtureオブジェクトを作成
            mix = Mixture(substances, zs=zs, T=T, P=P)

            # K値を各成分の蒸気圧から近似計算（Raoultの法則）
            K_values = {}
            for i, s in enumerate(substances):
                chem = Chemical(s, T=T, P=P)
                Psat = chem.Psat if chem.Psat else P
                K_values[s] = Psat / P

            # 相対揮発度（最初の成分基準）
            alpha = {}
            ref_K = K_values.get(substances[0], 1.0)
            for s in substances:
                alpha[s] = K_values[s] / ref_K if ref_K > 0 else 1.0

            return {
                "temperature": T,
                "pressure": P,
                "K_values": K_values,
                "relative_volatility": alpha,
                "feed_composition": dict(zip(substances, zs)),
            }

        except Exception as e:
            raise ConditionsOutOfRangeError(self.name, str(e)) from e

    def calculate_bubble_point(
        self,
        substances: list[str],
        composition: dict[str, float],
        pressure: float,
    ) -> dict[str, Any]:
        """泡点計算（与えられた圧力での沸騰開始温度）"""
        if not self.is_available():
            raise ImportError("thermo/chemicals library not installed")

        try:
            zs = [composition.get(s, 0.0) for s in substances]

            # 初期推定：純成分の沸点の組成平均
            T_guess = 0.0
            for i, s in enumerate(substances):
                chem = Chemical(s)
                Tb = chem.Tb if chem.Tb else 350.0
                T_guess += zs[i] * Tb

            # 反復計算で泡点を求める
            T = T_guess
            for _ in range(50):
                # 各成分の蒸気圧
                Psats = []
                for s in substances:
                    chem = Chemical(s, T=T, P=pressure)
                    Psats.append(chem.Psat if chem.Psat else 0)

                # Raoultの法則: P = Σ(xi * Psat_i)
                P_calc = sum(zs[i] * Psats[i] for i in range(len(substances)))

                if abs(P_calc - pressure) < 100:  # 100 Pa以内で収束
                    break

                if P_calc < pressure:
                    T += 1.0
                else:
                    T -= 1.0

            # 蒸気相組成
            y = {}
            for i, s in enumerate(substances):
                y[s] = zs[i] * Psats[i] / pressure if pressure > 0 else 0

            return {
                "bubble_point_temperature": T,
                "pressure": pressure,
                "liquid_composition": dict(zip(substances, zs)),
                "vapor_composition": y,
            }

        except Exception as e:
            raise ConditionsOutOfRangeError(self.name, str(e)) from e

    def calculate_dew_point(
        self,
        substances: list[str],
        composition: dict[str, float],
        pressure: float,
    ) -> dict[str, Any]:
        """露点計算（与えられた圧力での凝縮開始温度）"""
        if not self.is_available():
            raise ImportError("thermo/chemicals library not installed")

        try:
            ys = [composition.get(s, 0.0) for s in substances]

            # 初期推定：純成分の沸点の組成平均 + 10K
            T_guess = 0.0
            for i, s in enumerate(substances):
                chem = Chemical(s)
                Tb = chem.Tb if chem.Tb else 350.0
                T_guess += ys[i] * Tb
            T_guess += 10.0

            # 反復計算
            T = T_guess
            for _ in range(50):
                inv_P = 0.0
                for i, s in enumerate(substances):
                    chem = Chemical(s, T=T, P=pressure)
                    Psat = chem.Psat if chem.Psat else 1e-10
                    inv_P += ys[i] / Psat

                P_calc = 1.0 / inv_P if inv_P > 0 else 0

                if abs(P_calc - pressure) < 100:
                    break

                if P_calc > pressure:
                    T += 1.0
                else:
                    T -= 1.0

            # 液相組成
            x = {}
            for i, s in enumerate(substances):
                chem = Chemical(s, T=T, P=pressure)
                Psat = chem.Psat if chem.Psat else 1e-10
                x[s] = ys[i] * pressure / Psat

            return {
                "dew_point_temperature": T,
                "pressure": pressure,
                "vapor_composition": dict(zip(substances, ys)),
                "liquid_composition": x,
            }

        except Exception as e:
            raise ConditionsOutOfRangeError(self.name, str(e)) from e

    def get_substance_info(self, substance: str) -> dict[str, Any]:
        """物質情報を取得"""
        if not self.is_available():
            raise ImportError("thermo/chemicals library not installed")

        try:
            chem = Chemical(substance)

            return {
                "name": chem.name,
                "cas_number": chem.CAS,
                "formula": chem.formula,
                "molecular_weight": chem.MW,
                "critical_temperature": chem.Tc,
                "critical_pressure": chem.Pc,
                "acentric_factor": chem.omega,
                "boiling_point": chem.Tb,
                "melting_point": chem.Tm,
            }

        except Exception as e:
            raise SubstanceNotFoundError(self.name, substance) from e
