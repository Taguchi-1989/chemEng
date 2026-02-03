"""計算エンジンのテスト"""

import pytest
from chemeng.engines import get_available_engines
from chemeng.engines.base import EngineCapability


class TestEngineCapability:
    """EngineCapabilityのテスト"""

    def test_supports_property(self):
        """物性サポートの確認"""
        cap = EngineCapability(
            property_types=["vapor_pressure", "density"],
            calculation_types=["vle"],
        )
        assert cap.supports_property("vapor_pressure")
        assert cap.supports_property("density")
        assert not cap.supports_property("viscosity")

    def test_supports_calculation(self):
        """計算タイプサポートの確認"""
        cap = EngineCapability(
            property_types=[],
            calculation_types=["vle", "flash"],
        )
        assert cap.supports_calculation("vle")
        assert cap.supports_calculation("flash")
        assert not cap.supports_calculation("kinetics")


class TestThermoEngine:
    """ThermoEngineのテスト（ライブラリがインストールされている場合）"""

    @pytest.fixture
    def engine(self):
        """ThermoEngineインスタンスを取得"""
        try:
            from chemeng.engines.thermo_engine import ThermoEngine

            engine = ThermoEngine()
            if not engine.is_available():
                pytest.skip("thermo library not available")
            return engine
        except ImportError:
            pytest.skip("thermo library not installed")

    def test_name(self, engine):
        """エンジン名"""
        assert engine.name == "thermo"

    def test_capabilities(self, engine):
        """エンジン能力"""
        cap = engine.capabilities
        assert cap.supports_property("vapor_pressure")
        assert cap.supports_calculation("vle")

    def test_get_property_vapor_pressure(self, engine):
        """蒸気圧の取得"""
        # エタノールの蒸気圧（350K）
        P_vap = engine.get_property(
            "ethanol", "vapor_pressure", {"temperature": 350.0}
        )
        # 350Kでの蒸気圧は約100 kPa程度
        assert P_vap is not None
        assert 50000 < P_vap < 200000  # 50-200 kPa

    def test_get_property_critical_temperature(self, engine):
        """臨界温度の取得"""
        Tc = engine.get_property("water", "critical_temperature", {})
        # 水の臨界温度は約647 K
        assert Tc is not None
        assert 640 < Tc < 660

    def test_get_property_molecular_weight(self, engine):
        """分子量の取得"""
        MW = engine.get_property("ethanol", "molecular_weight", {})
        # エタノールの分子量は約46
        assert MW is not None
        assert 45 < MW < 47

    def test_get_substance_info(self, engine):
        """物質情報の取得"""
        info = engine.get_substance_info("ethanol")
        assert "name" in info
        assert "molecular_weight" in info
        assert "critical_temperature" in info

    def test_calculate_equilibrium(self, engine):
        """相平衡計算"""
        result = engine.calculate_equilibrium(
            substances=["ethanol", "water"],
            composition={"ethanol": 0.4, "water": 0.6},
            conditions={"temperature": 350.0, "pressure": 101325.0},
        )
        assert "K_values" in result
        assert "ethanol" in result["K_values"]
        assert "water" in result["K_values"]
        # エタノールの方が揮発性が高い
        assert result["K_values"]["ethanol"] > result["K_values"]["water"]

    def test_calculate_bubble_point(self, engine):
        """泡点計算"""
        result = engine.calculate_bubble_point(
            substances=["ethanol", "water"],
            composition={"ethanol": 0.5, "water": 0.5},
            pressure=101325.0,
        )
        assert "bubble_point_temperature" in result
        # 50mol%エタノール水溶液の泡点は約78-100°C (351-373K)
        T_bp = result["bubble_point_temperature"]
        assert 340 < T_bp < 380

    def test_calculate_dew_point(self, engine):
        """露点計算"""
        result = engine.calculate_dew_point(
            substances=["ethanol", "water"],
            composition={"ethanol": 0.5, "water": 0.5},
            pressure=101325.0,
        )
        assert "dew_point_temperature" in result
        T_dp = result["dew_point_temperature"]
        # 露点は泡点より高い
        assert T_dp > 340


class TestGetAvailableEngines:
    """get_available_engines関数のテスト"""

    def test_returns_list(self):
        """リストを返す"""
        engines = get_available_engines()
        assert isinstance(engines, list)

    def test_engines_have_required_methods(self):
        """エンジンが必要なメソッドを持つ"""
        engines = get_available_engines()
        for engine in engines:
            assert hasattr(engine, "name")
            assert hasattr(engine, "capabilities")
            assert hasattr(engine, "is_available")
            assert hasattr(engine, "get_property")
            assert hasattr(engine, "calculate_equilibrium")
