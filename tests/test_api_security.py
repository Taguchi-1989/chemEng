"""APIセキュリティテスト

入力バリデーション、エラーメッセージの安全性、パラメータ境界値を検証する。
"""

import pytest
from pydantic import ValidationError


class TestPropertyRequestValidation:
    """PropertyRequest モデルのバリデーション"""

    def test_valid_property_name(self):
        """正常な物性名が受け付けられること"""
        from interface.api import PropertyRequest
        req = PropertyRequest(substance="water", property="vapor_pressure")
        assert req.property == "vapor_pressure"

    def test_invalid_property_name_special_chars(self):
        """特殊文字を含む物性名が拒否されること"""
        from interface.api import PropertyRequest
        with pytest.raises(ValidationError):
            PropertyRequest(substance="water", property="vapor<script>")

    def test_invalid_property_name_uppercase(self):
        """大文字を含む物性名が拒否されること（pattern: ^[a-z_]+$）"""
        from interface.api import PropertyRequest
        with pytest.raises(ValidationError):
            PropertyRequest(substance="water", property="VaporPressure")

    def test_substance_max_length(self):
        """substance が最大長を超えると拒否されること"""
        from interface.api import PropertyRequest
        with pytest.raises(ValidationError):
            PropertyRequest(substance="x" * 201, property="vapor_pressure")

    def test_temperature_negative_rejected(self):
        """負の温度が拒否されること"""
        from interface.api import PropertyRequest
        with pytest.raises(ValidationError):
            PropertyRequest(substance="water", property="vapor_pressure", temperature=-1)

    def test_temperature_too_high_rejected(self):
        """極端に高い温度が拒否されること"""
        from interface.api import PropertyRequest
        with pytest.raises(ValidationError):
            PropertyRequest(substance="water", property="vapor_pressure", temperature=20000)

    def test_pressure_negative_rejected(self):
        """負の圧力が拒否されること"""
        from interface.api import PropertyRequest
        with pytest.raises(ValidationError):
            PropertyRequest(substance="water", property="vapor_pressure", pressure=-100)

    def test_quality_out_of_range(self):
        """乾き度 > 1 が拒否されること"""
        from interface.api import PropertyRequest
        with pytest.raises(ValidationError):
            PropertyRequest(substance="water", property="vapor_pressure", quality=1.5)


class TestEquilibriumRequestValidation:
    """EquilibriumRequest モデルのバリデーション"""

    def test_valid_request(self):
        """正常なリクエストが受け付けられること"""
        from interface.api import EquilibriumRequest
        req = EquilibriumRequest(
            substances=["ethanol", "water"],
            composition={"ethanol": 0.5, "water": 0.5},
        )
        assert len(req.substances) == 2

    def test_temperature_bounds(self):
        """温度の境界値が検証されること"""
        from interface.api import EquilibriumRequest
        with pytest.raises(ValidationError):
            EquilibriumRequest(
                substances=["ethanol", "water"],
                composition={"ethanol": 0.5, "water": 0.5},
                temperature=-10,
            )


class TestSafeErrorMessage:
    """safe_error_message のテスト"""

    def test_known_engine_error(self):
        """既知のエンジン例外がユーザー向けメッセージに変換されること"""
        from core.errors import safe_error_message
        from engines.base import SubstanceNotFoundError
        exc = SubstanceNotFoundError("thermo", "nonexistent_substance")
        msg = safe_error_message(exc)
        assert "nonexistent_substance" in msg
        # スタックトレースが含まれないこと
        assert "Traceback" not in msg
        assert ".py" not in msg

    def test_property_not_available_error(self):
        """PropertyNotAvailableError の変換"""
        from core.errors import safe_error_message
        from engines.base import PropertyNotAvailableError
        exc = PropertyNotAvailableError("thermo", "invalid_prop", "water")
        msg = safe_error_message(exc)
        assert "invalid_prop" in msg

    def test_unknown_exception_hides_details(self):
        """未知の例外が汎用メッセージに変換され、詳細が隠されること"""
        from core.errors import safe_error_message
        exc = RuntimeError("Internal file path /var/lib/secrets/key.pem not found")
        msg = safe_error_message(exc)
        # 内部パスが含まれないこと
        assert "/var/lib/secrets" not in msg
        # 参照IDが含まれること
        assert "ref:" in msg

    def test_value_error_passes_through(self):
        """ValueError はメッセージがそのまま返ること"""
        from core.errors import safe_error_message
        exc = ValueError("Temperature must be positive")
        msg = safe_error_message(exc)
        assert msg == "Temperature must be positive"


class TestConditionsOutOfRange:
    """温度・圧力の範囲チェック"""

    def test_temperature_zero_rejected(self):
        """T=0 が拒否されること"""
        from engines.base import ConditionsOutOfRangeError
        from engines.thermo_engine import ThermoEngine
        engine = ThermoEngine()
        if not engine.is_available():
            pytest.skip("thermo engine not available")
        with pytest.raises(ConditionsOutOfRangeError):
            engine.get_property("water", "vapor_pressure", {"temperature": 0})

    def test_temperature_extreme_rejected(self):
        """T=5000K が拒否されること"""
        from engines.base import ConditionsOutOfRangeError
        from engines.thermo_engine import ThermoEngine
        engine = ThermoEngine()
        if not engine.is_available():
            pytest.skip("thermo engine not available")
        with pytest.raises(ConditionsOutOfRangeError):
            engine.get_property("water", "vapor_pressure", {"temperature": 5000})

    def test_pressure_negative_rejected(self):
        """P<0 が拒否されること"""
        from engines.base import ConditionsOutOfRangeError
        from engines.thermo_engine import ThermoEngine
        engine = ThermoEngine()
        if not engine.is_available():
            pytest.skip("thermo engine not available")
        with pytest.raises(ConditionsOutOfRangeError):
            engine.get_property("water", "vapor_pressure", {"pressure": -100})
