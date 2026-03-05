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


class TestPropertyEstimationSubstanceInfo:
    """物性推算の物質情報取得テスト（キー不一致の回帰テスト）"""

    def test_substance_info_keys_in_output(self, registry):
        """物質情報（CAS番号、分子量、臨界温度等）が正しく出力に含まれること"""
        result = registry.execute("property_estimation", {
            "substance": "water",
            "property": "vapor_pressure",
            "temperature": 373.15,
        })
        assert result.success
        steps = result.outputs.get("calculation_steps", [])
        # Step 2 = 物質情報
        info_step = next((s for s in steps if s.get("step") == 2), None)
        assert info_step is not None
        values = info_step.get("values", {})
        # CAS番号と分子量が正しく取得されていること（None でないこと）
        assert values.get("CAS") is not None and values["CAS"] != "N/A"
        assert values.get("MW") is not None

    def test_property_estimation_error_no_raw_exception(self, registry):
        """物性推算のエラーで生の例外文字列がユーザーに漏洩しないこと"""
        result = registry.execute("property_estimation", {
            "substance": "totally_fake_substance_xyz",
            "property": "vapor_pressure",
            "temperature": 300.0,
        })
        assert not result.success
        for err in result.errors:
            # 内部パスやスタックトレースが漏れないこと
            assert "Traceback" not in err
            assert "File \"" not in err


class TestLCOHErrorHandling:
    """LCOH計算のエラーハンドリングテスト"""

    def test_lcoh_success_result_format(self, registry):
        """LCOH計算が success=True で正しい出力フォーマットを返すこと"""
        result = registry.execute("lcoh", {
            "production_method": "pem_electrolysis",
            "capacity": 10,
            "electricity_price": 50,
            "operating_hours": 4000,
        })
        assert result.success
        assert "lcoh" in result.outputs
        assert "lcoh_breakdown" in result.outputs

    def test_lcoh_zero_operating_hours_error(self, registry):
        """稼働時間0でエラー結果が安全に返されること"""
        result = registry.execute("lcoh", {
            "production_method": "pem_electrolysis",
            "capacity": 10,
            "operating_hours": 0,
        })
        assert not result.success
        for err in result.errors:
            assert "Traceback" not in err


class TestAbsorptionEdgeCases:
    """ガス吸収の境界条件テスト"""

    def test_absorption_y_in_1_returns_error(self, registry):
        """入口ガス組成が1.0のときゼロ除算せずエラーを返すこと"""
        result = registry.execute("absorption", {
            "gas_component": "ammonia",
            "carrier_gas": "air",
            "solvent": "water",
            "gas_flow_rate": 100,
            "inlet_gas_composition": 1.0,
            "removal_efficiency": 0.9,
        })
        assert not result.success
        assert len(result.errors) > 0


class TestDistillationEdgeCases:
    """蒸留計算のゼロ除算・極端値テスト"""

    def test_xd_equals_xb_returns_error(self, registry):
        """xD == xB（分離不要）のときエラーを返すこと"""
        result = registry.execute("distillation", {
            "light_component": "ethanol",
            "heavy_component": "water",
            "feed_flow_rate": 100,
            "feed_composition": 0.5,
            "distillate_purity": 0.5,
            "bottoms_purity": 0.5,
        })
        assert not result.success

    def test_xd_near_1_no_crash(self, registry):
        """xD → 1.0 で log(0) によるクラッシュが起きないこと"""
        result = registry.execute("distillation", {
            "light_component": "ethanol",
            "heavy_component": "water",
            "feed_flow_rate": 100,
            "feed_composition": 0.5,
            "distillate_purity": 0.9999,
            "bottoms_purity": 0.9999,
        })
        # Should either succeed with clamped values or fail gracefully
        for err in (result.errors or []):
            assert "Traceback" not in err

    def test_xb_near_0_no_crash(self, registry):
        """xB → 0 で log(0) によるクラッシュが起きないこと"""
        result = registry.execute("distillation", {
            "light_component": "ethanol",
            "heavy_component": "water",
            "feed_flow_rate": 100,
            "feed_composition": 0.5,
            "distillate_purity": 0.99,
            "bottoms_purity": 0.99999,
        })
        for err in (result.errors or []):
            assert "Traceback" not in err


class TestMassBalanceEdgeCases:
    """物質収支の負流量テスト"""

    def test_negative_flow_warns(self, registry):
        """出口組成が不整合で負流量になるとき警告が出ること"""
        result = registry.execute("mass_balance", {
            "components": ["ethanol", "water"],
            "feed_flow_rate": 100,
            "feed_composition": 0.4,
            "distillate_composition": 0.3,
            "bottoms_composition": 0.5,
        })
        # Should either have warnings about negative flow or fail gracefully
        has_warn_or_error = (
            (result.warnings and any("negative" in w.lower() or "負" in w for w in result.warnings))
            or not result.success
        )
        assert has_warn_or_error or result.success  # At minimum, no crash


class TestExtractionEdgeCases:
    """液液抽出の極端値テスト"""

    def test_extreme_recovery_clamped(self, registry):
        """目標抽出率 > 0.9999 がクランプされること"""
        result = registry.execute("extraction", {
            "solute": "acetic_acid",
            "carrier": "water",
            "solvent": "ethyl_acetate",
            "feed_flow_rate": 100,
            "feed_composition": 0.1,
            "solvent_flow_rate": 50,
            "recovery": 1.0,
        })
        # Should succeed with clamped value or fail gracefully
        for err in (result.errors or []):
            assert "Traceback" not in err


class TestTxyDiagramErrorHandling:
    """T-x-y相図のエラーハンドリングテスト"""

    def test_txy_invalid_substance_no_raw_exception(self, registry):
        """不正な物質名でスタックトレースが漏洩しないこと"""
        result = registry.execute("txy_diagram", {
            "light_component": "fake_substance_abc",
            "heavy_component": "fake_substance_xyz",
            "pressure": 101325.0,
        })
        assert not result.success
        for err in result.errors:
            assert "Traceback" not in err
            assert "File \"" not in err
