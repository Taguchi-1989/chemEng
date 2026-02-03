"""
Cantera エンジン

反応速度論、化学平衡、燃焼計算を提供。
"""

from __future__ import annotations

from typing import Any

from .base import (
    CalculationEngine,
    ConditionsOutOfRangeError,
    EngineCapability,
    EngineError,
)

# 条件付きインポート
try:
    import cantera as ct
    CANTERA_AVAILABLE = True
except ImportError:
    CANTERA_AVAILABLE = False


class CanteraEngine(CalculationEngine):
    """Cantera ライブラリラッパー"""

    # デフォルトメカニズムファイル
    DEFAULT_MECHANISM = "gri30.yaml"  # GRI-Mech 3.0（メタン燃焼用）

    @property
    def name(self) -> str:
        return "cantera"

    @property
    def capabilities(self) -> EngineCapability:
        return EngineCapability(
            property_types=[
                "enthalpy",
                "entropy",
                "gibbs_energy",
                "heat_capacity",
                "density",
                "viscosity",
                "thermal_conductivity",
                "mean_molecular_weight",
            ],
            calculation_types=[
                "equilibrium",
                "kinetics",
                "combustion",
                "adiabatic_flame",
                "reactor",
            ],
            supported_substances="gases, ideal solutions, GRI-Mech species",
        )

    def is_available(self) -> bool:
        return CANTERA_AVAILABLE

    def _get_solution(self, mechanism: str | None = None) -> ct.Solution:
        """Solutionオブジェクトを取得"""
        if not CANTERA_AVAILABLE:
            raise ImportError("cantera library not installed")

        mech = mechanism or self.DEFAULT_MECHANISM
        try:
            return ct.Solution(mech)
        except Exception as e:
            raise EngineError(self.name, f"Failed to load mechanism {mech}: {e}")

    def get_property(
        self, substance: str, property_name: str, conditions: dict[str, float]
    ) -> float:
        """物性値を取得（純物質、理想気体として）"""
        if not CANTERA_AVAILABLE:
            raise ImportError("cantera library not installed")

        T = conditions.get("temperature", 298.15)
        P = conditions.get("pressure", 101325.0)

        try:
            gas = self._get_solution()
            gas.TPX = T, P, {substance: 1.0}

            property_map = {
                "enthalpy": lambda: gas.enthalpy_mass,  # J/kg
                "entropy": lambda: gas.entropy_mass,  # J/(kg·K)
                "gibbs_energy": lambda: gas.gibbs_mass,  # J/kg
                "heat_capacity": lambda: gas.cp_mass,  # J/(kg·K)
                "density": lambda: gas.density,  # kg/m³
                "viscosity": lambda: gas.viscosity,  # Pa·s
                "thermal_conductivity": lambda: gas.thermal_conductivity,  # W/(m·K)
                "mean_molecular_weight": lambda: gas.mean_molecular_weight,  # kg/kmol
            }

            if property_name not in property_map:
                raise EngineError(self.name, f"Unknown property: {property_name}")

            return property_map[property_name]()

        except Exception as e:
            raise ConditionsOutOfRangeError(self.name, str(e))

    def calculate_equilibrium(
        self,
        substances: list[str],
        composition: dict[str, float],
        conditions: dict[str, float],
    ) -> dict[str, Any]:
        """
        化学平衡計算

        Args:
            substances: 物質リスト（使用するメカニズムに含まれる種のみ）
            composition: 初期組成（モル分率）
            conditions: 温度・圧力

        Returns:
            平衡状態の組成と物性
        """
        if not CANTERA_AVAILABLE:
            raise ImportError("cantera library not installed")

        T = conditions.get("temperature", 298.15)
        P = conditions.get("pressure", 101325.0)

        try:
            gas = self._get_solution()
            gas.TPX = T, P, composition
            gas.equilibrate("TP")  # 定温定圧平衡

            # 結果を整理
            result_composition = {}
            for i, name in enumerate(gas.species_names):
                if gas.X[i] > 1e-10:  # 微量成分をフィルタ
                    result_composition[name] = gas.X[i]

            return {
                "temperature": gas.T,
                "pressure": gas.P,
                "composition": result_composition,
                "enthalpy": gas.enthalpy_mass,
                "entropy": gas.entropy_mass,
                "density": gas.density,
                "mean_molecular_weight": gas.mean_molecular_weight,
            }

        except Exception as e:
            raise ConditionsOutOfRangeError(self.name, str(e))

    def calculate_adiabatic_flame_temperature(
        self,
        fuel: str | dict[str, float],
        oxidizer: str | dict[str, float] = "O2:1.0, N2:3.76",
        equivalence_ratio: float = 1.0,
        initial_temperature: float = 298.15,
        pressure: float = 101325.0,
    ) -> dict[str, Any]:
        """
        断熱火炎温度を計算

        Args:
            fuel: 燃料（物質名または組成辞書）
            oxidizer: 酸化剤（デフォルト: 空気）
            equivalence_ratio: 当量比（1.0 = 化学量論）
            initial_temperature: 初期温度 (K)
            pressure: 圧力 (Pa)

        Returns:
            火炎温度と燃焼生成物
        """
        if not CANTERA_AVAILABLE:
            raise ImportError("cantera library not installed")

        try:
            gas = self._get_solution()

            # 燃料の設定
            if isinstance(fuel, str):
                fuel_comp = fuel
            else:
                fuel_comp = ", ".join(f"{k}:{v}" for k, v in fuel.items())

            # 酸化剤の設定
            if isinstance(oxidizer, str):
                ox_comp = oxidizer
            else:
                ox_comp = ", ".join(f"{k}:{v}" for k, v in oxidizer.items())

            # 当量比を設定
            gas.set_equivalence_ratio(equivalence_ratio, fuel_comp, ox_comp)
            gas.TP = initial_temperature, pressure

            # 初期状態を保存

            # 断熱平衡（定エンタルピー・定圧）
            gas.equilibrate("HP")

            # 主要生成物
            products = {}
            for i, name in enumerate(gas.species_names):
                if gas.X[i] > 1e-6:
                    products[name] = gas.X[i]

            return {
                "flame_temperature": gas.T,
                "initial_temperature": initial_temperature,
                "pressure": pressure,
                "equivalence_ratio": equivalence_ratio,
                "products": products,
                "enthalpy": gas.enthalpy_mass,
                "temperature_rise": gas.T - initial_temperature,
            }

        except Exception as e:
            raise ConditionsOutOfRangeError(self.name, str(e))

    def calculate_reaction_rates(
        self,
        composition: dict[str, float],
        temperature: float,
        pressure: float = 101325.0,
        mechanism: str | None = None,
    ) -> dict[str, Any]:
        """
        反応速度を計算

        Args:
            composition: 組成（モル分率）
            temperature: 温度 (K)
            pressure: 圧力 (Pa)
            mechanism: メカニズムファイル

        Returns:
            各反応の速度と種の生成速度
        """
        if not CANTERA_AVAILABLE:
            raise ImportError("cantera library not installed")

        try:
            gas = self._get_solution(mechanism)
            gas.TPX = temperature, pressure, composition

            # 反応速度
            forward_rates = {}
            reverse_rates = {}
            net_rates = {}

            for i in range(gas.n_reactions):
                rxn = gas.reaction(i)
                forward_rates[rxn.equation] = gas.forward_rates_of_progress[i]
                reverse_rates[rxn.equation] = gas.reverse_rates_of_progress[i]
                net_rates[rxn.equation] = gas.net_rates_of_progress[i]

            # 種の生成速度
            production_rates = {}
            for i, name in enumerate(gas.species_names):
                rate = gas.net_production_rates[i]
                if abs(rate) > 1e-20:
                    production_rates[name] = rate

            return {
                "temperature": temperature,
                "pressure": pressure,
                "forward_rates": forward_rates,
                "reverse_rates": reverse_rates,
                "net_rates": net_rates,
                "production_rates": production_rates,
                "n_reactions": gas.n_reactions,
            }

        except Exception as e:
            raise ConditionsOutOfRangeError(self.name, str(e))

    def simulate_batch_reactor(
        self,
        composition: dict[str, float],
        temperature: float,
        pressure: float = 101325.0,
        residence_time: float = 1.0,
        n_steps: int = 100,
        isothermal: bool = False,
    ) -> dict[str, Any]:
        """
        バッチ反応器のシミュレーション

        Args:
            composition: 初期組成
            temperature: 初期温度 (K)
            pressure: 初期圧力 (Pa)
            residence_time: 滞留時間 (s)
            n_steps: 出力ステップ数
            isothermal: 等温条件か

        Returns:
            時間履歴
        """
        if not CANTERA_AVAILABLE:
            raise ImportError("cantera library not installed")

        try:
            gas = self._get_solution()
            gas.TPX = temperature, pressure, composition

            # 反応器の設定
            if isothermal:
                reactor = ct.IdealGasConstPressureReactor(gas)
            else:
                reactor = ct.IdealGasReactor(gas)

            network = ct.ReactorNet([reactor])

            # 時間履歴
            times = []
            temperatures = []
            compositions = {name: [] for name in gas.species_names}

            dt = residence_time / n_steps
            for i in range(n_steps + 1):
                t = i * dt
                network.advance(t)

                times.append(t)
                temperatures.append(reactor.T)
                for j, name in enumerate(gas.species_names):
                    compositions[name].append(gas.X[j])

            # 主要種のみ抽出
            main_compositions = {}
            for name, values in compositions.items():
                if max(values) > 1e-6:
                    main_compositions[name] = values

            return {
                "times": times,
                "temperatures": temperatures,
                "compositions": main_compositions,
                "final_temperature": reactor.T,
                "final_pressure": reactor.thermo.P,
            }

        except Exception as e:
            raise ConditionsOutOfRangeError(self.name, str(e))

    def get_species_list(self, mechanism: str | None = None) -> list[str]:
        """メカニズムに含まれる種のリストを取得"""
        if not CANTERA_AVAILABLE:
            raise ImportError("cantera library not installed")

        gas = self._get_solution(mechanism)
        return list(gas.species_names)

    def get_reaction_list(self, mechanism: str | None = None) -> list[str]:
        """メカニズムに含まれる反応式のリストを取得"""
        if not CANTERA_AVAILABLE:
            raise ImportError("cantera library not installed")

        gas = self._get_solution(mechanism)
        return [gas.reaction(i).equation for i in range(gas.n_reactions)]
