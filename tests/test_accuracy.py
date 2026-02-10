"""計算精度ベンチマーク

文献値と比較して計算結果の精度を検証する。
"""

import pytest


class TestPropertyAccuracy:
    """物性値の精度テスト"""

    @pytest.fixture(autouse=True)
    def setup_engine(self):
        from engines.thermo_engine import ThermoEngine
        self.engine = ThermoEngine()
        if not self.engine.is_available():
            pytest.skip("thermo engine not available")

    def test_water_boiling_point(self):
        """水の沸点 ≈ 373.15 K (±1K)"""
        bp = self.engine.get_property("water", "boiling_point", {})
        assert abs(bp - 373.15) < 1.0, f"Water boiling point = {bp} K, expected ~373.15 K"

    def test_water_molecular_weight(self):
        """水の分子量 ≈ 18.015 g/mol (±0.01)"""
        mw = self.engine.get_property("water", "molecular_weight", {})
        assert abs(mw - 18.015) < 0.01, f"Water MW = {mw}, expected ~18.015"

    def test_ethanol_boiling_point(self):
        """エタノールの沸点 ≈ 351.4 K (±1K)"""
        bp = self.engine.get_property("ethanol", "boiling_point", {})
        assert abs(bp - 351.4) < 1.0, f"Ethanol boiling point = {bp} K, expected ~351.4 K"

    def test_water_vapor_pressure_at_100C(self):
        """水の100℃蒸気圧 ≈ 101325 Pa (±2%)"""
        vp = self.engine.get_property("water", "vapor_pressure", {"temperature": 373.15})
        rel_error = abs(vp - 101325) / 101325
        assert rel_error < 0.02, f"Water VP at 100°C = {vp} Pa, expected ~101325 Pa (error: {rel_error*100:.1f}%)"

    def test_ethanol_critical_temperature(self):
        """エタノールの臨界温度 ≈ 513.9 K (±2K)"""
        tc = self.engine.get_property("ethanol", "critical_temperature", {})
        assert abs(tc - 513.9) < 2.0, f"Ethanol Tc = {tc} K, expected ~513.9 K"


class TestBubblePointAccuracy:
    """泡点計算の精度テスト"""

    @pytest.fixture(autouse=True)
    def setup_engine(self):
        from engines.thermo_engine import ThermoEngine
        self.engine = ThermoEngine()
        if not self.engine.is_available():
            pytest.skip("thermo engine not available")

    def test_pure_water_bubble_point(self):
        """純水の泡点 ≈ 373.15 K at 1 atm (±2K)"""
        result = self.engine.calculate_bubble_point(
            ["water"], {"water": 1.0}, 101325.0
        )
        T = result["bubble_point_temperature"]
        assert abs(T - 373.15) < 2.0, f"Pure water bubble point = {T} K, expected ~373.15 K"

    def test_pure_ethanol_bubble_point(self):
        """純エタノールの泡点 ≈ 351.4 K at 1 atm (±2K)"""
        result = self.engine.calculate_bubble_point(
            ["ethanol"], {"ethanol": 1.0}, 101325.0
        )
        T = result["bubble_point_temperature"]
        assert abs(T - 351.4) < 2.0, f"Pure ethanol bubble point = {T} K, expected ~351.4 K"

    def test_convergence_flag(self):
        """収束フラグが返されること"""
        result = self.engine.calculate_bubble_point(
            ["ethanol", "water"], {"ethanol": 0.5, "water": 0.5}, 101325.0
        )
        assert "converged" in result


class TestMassBalanceClosure:
    """物質収支のクロージャテスト"""

    def test_simple_balance_closure(self):
        """単純な2成分収支の閉合率 = 100%"""
        from skills.templates.mass_balance import execute

        params = {
            "components": ["ethanol", "water"],
            "inlet_streams": [
                {
                    "name": "Feed",
                    "flow_rate": 100.0,
                    "composition": {"ethanol": 0.4, "water": 0.6},
                }
            ],
            "outlet_streams": [
                {
                    "name": "Distillate",
                    "composition": {"ethanol": 0.9, "water": 0.1},
                },
                {
                    "name": "Bottoms",
                    "composition": {"ethanol": 0.05, "water": 0.95},
                },
            ],
        }

        result = execute(params)
        assert result["success"]
        closure = result["outputs"]["closure"]
        assert closure > 99.0, f"Closure = {closure}%, expected > 99%"
