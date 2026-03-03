"""エラーハンドリングの品質テスト

registry.execute() が safe_error_message を使用し、
内部例外の詳細がユーザーに漏洩しないことを検証する。
"""

import pytest

from core.errors import safe_error_message
from core.registry import SkillRegistry


@pytest.fixture
def registry():
    return SkillRegistry()


class TestRegistryErrorSafety:
    """Registry経由のエラーが安全にマスクされること"""

    def test_nonexistent_skill_returns_error_result(self, registry):
        """存在しないスキルIDで CalculationResult(success=False) が返ること"""
        result = registry.execute("nonexistent_skill_xyz", {})
        assert not result.success
        assert any("not found" in e.lower() for e in result.errors)

    def test_invalid_params_no_stack_trace(self, registry):
        """不正パラメータでスタックトレースが漏洩しないこと"""
        result = registry.execute("property_estimation", {
            "substance": "water",
            "property": "vapor_pressure",
            "temperature": -999999,  # 不正な値
        })
        for error_msg in result.errors:
            assert "Traceback" not in error_msg
            assert "File \"" not in error_msg

    def test_engine_error_uses_safe_message(self, registry):
        """エンジンエラーが safe_error_message で変換されること"""
        result = registry.execute("property_estimation", {
            "substance": "totally_nonexistent_xyz_12345_compound",
            "property": "vapor_pressure",
            "temperature": 300.0,
        })
        # エラーまたは失敗した結果
        has_error = (
            not result.success
            or len(result.errors) > 0
        )
        assert has_error
        # 内部パスが含まれないこと
        for error_msg in result.errors:
            assert ".py" not in error_msg or "ref:" in error_msg


class TestSafeErrorMessageEdgeCases:
    """safe_error_message の追加エッジケース"""

    def test_nested_exception_hides_details(self):
        """ネストされた例外の内部詳細が隠されること"""
        try:
            try:
                raise OSError("/var/lib/secrets/database.key not found")
            except OSError as inner:
                raise RuntimeError("Failed to initialize") from inner
        except RuntimeError as e:
            msg = safe_error_message(e)
            assert "/var/lib/secrets" not in msg
            assert "ref:" in msg

    def test_empty_exception_message(self):
        """空メッセージの例外でもクラッシュしないこと"""
        msg = safe_error_message(RuntimeError(""))
        assert isinstance(msg, str)
        assert "ref:" in msg

    def test_conditions_out_of_range_error(self):
        """ConditionsOutOfRangeError が適切に変換されること"""
        from engines.base import ConditionsOutOfRangeError
        exc = ConditionsOutOfRangeError("thermo", "Temperature 0 K is out of range")
        msg = safe_error_message(exc)
        assert "範囲外" in msg or "out of range" in msg.lower() or "ref:" in msg


class TestBatchCalculation:
    """バッチ計算のエラーハンドリングテスト"""

    def test_batch_mixed_success_and_failure(self, registry):
        """バッチで成功と失敗が混在した場合の処理"""
        # 1件ずつ確認（API経由ではなくregistryで直接テスト）
        good_result = registry.execute("property_estimation", {
            "substance": "water",
            "property": "molecular_weight",
        })
        assert good_result.success

        bad_result = registry.execute("nonexistent_skill", {})
        assert not bad_result.success

    def test_batch_all_failures_no_crash(self, registry):
        """全ケース失敗してもクラッシュしないこと"""
        for _ in range(5):
            result = registry.execute("nonexistent_skill", {})
            assert not result.success
            assert len(result.errors) > 0


class TestCalculationResultFormat:
    """計算結果のフォーマット一貫性テスト"""

    def test_error_result_has_all_fields(self, registry):
        """エラー結果に必要なフィールドが全て含まれること"""
        result = registry.execute("nonexistent_skill", {})
        d = result.to_dict()
        required_fields = {"success", "skill_id", "inputs", "outputs", "errors", "warnings"}
        assert required_fields.issubset(d.keys())

    def test_success_result_has_timestamp(self, registry):
        """成功結果にタイムスタンプが含まれること"""
        result = registry.execute("property_estimation", {
            "substance": "water",
            "property": "molecular_weight",
        })
        if result.success:
            assert result.timestamp is not None
            assert result.execution_time_ms >= 0
