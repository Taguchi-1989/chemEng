"""統合テスト

Registry経由でスキルをエンドツーエンド実行し、結果の構造を検証する。
"""

import pytest

from core.registry import SkillRegistry


@pytest.fixture
def registry():
    return SkillRegistry()


class TestSkillLoading:
    """スキル読み込みの統合テスト"""

    def test_all_schemas_load(self, registry):
        """全7スキルのYAMLスキーマが正常に読み込まれること"""
        skills = registry.list_skills()
        skill_ids = {s.id for s in skills}
        expected = {
            "property_estimation", "mass_balance", "heat_balance",
            "distillation", "extraction", "absorption", "lcoh",
            "txy_diagram",
        }
        assert expected.issubset(skill_ids), f"Missing skills: {expected - skill_ids}"

    def test_each_skill_has_template(self, registry):
        """各スキルにテンプレートが存在すること"""
        for skill in registry.list_skills():
            assert skill.template_path is not None, f"Skill {skill.id} has no template"
            assert skill.template_path.exists(), f"Template missing for {skill.id}: {skill.template_path}"


class TestPropertyEstimation:
    """物性推算の統合テスト"""

    def test_water_vapor_pressure(self, registry):
        """Registry経由で水の蒸気圧が計算できること"""
        result = registry.execute("property_estimation", {
            "substance": "water",
            "property": "vapor_pressure",
            "temperature": 373.15,
            "pressure": 101325.0,
        })
        assert result.success, f"Failed: {result.errors}"
        assert "value" in result.outputs or "calculation_steps" in result.outputs

    def test_invalid_substance(self, registry):
        """存在しない物質でエラーが返ること"""
        result = registry.execute("property_estimation", {
            "substance": "nonexistent_xyz_12345",
            "property": "vapor_pressure",
            "temperature": 300.0,
        })
        # テンプレートがエラーをoutputs内に返す場合もある
        has_error = (
            not result.success
            or len(result.errors) > 0
            or result.outputs.get("success") is False
        )
        assert has_error


class TestDistillation:
    """蒸留計算の統合テスト"""

    def test_ethanol_water_distillation(self, registry):
        """エタノール/水系蒸留計算の基本フロー"""
        result = registry.execute("distillation", {
            "light_component": "ethanol",
            "heavy_component": "water",
            "feed_flow_rate": 100.0,
            "feed_composition": 0.4,
            "feed_temperature": 350.0,
            "distillate_purity": 0.9,
            "bottoms_purity": 0.95,
            "reflux_ratio_factor": 1.3,
        })
        assert result.success, f"Failed: {result.errors}"
        out = result.outputs
        assert "actual_stages" in out
        assert "minimum_reflux_ratio" in out
        assert "condenser_duty" in out
        assert out["actual_stages"] > 0


class TestMassBalance:
    """物質収支の統合テスト"""

    def test_two_component_balance(self, registry):
        """2成分物質収支が正常に計算されること"""
        result = registry.execute("mass_balance", {
            "components": ["ethanol", "water"],
            "inlet_streams": [{
                "name": "Feed",
                "flow_rate": 100.0,
                "composition": {"ethanol": 0.3, "water": 0.7},
            }],
            "outlet_streams": [
                {"name": "Product", "composition": {"ethanol": 0.8, "water": 0.2}},
                {"name": "Waste", "composition": {"ethanol": 0.05, "water": 0.95}},
            ],
        })
        assert result.success, f"Failed: {result.errors}"
        assert result.outputs["closure"] > 99.0


class TestCalculationResult:
    """計算結果のフォーマットテスト"""

    def test_result_has_timestamp(self, registry):
        """結果にタイムスタンプが含まれること"""
        result = registry.execute("property_estimation", {
            "substance": "water",
            "property": "molecular_weight",
        })
        assert result.timestamp is not None

    def test_result_has_execution_time(self, registry):
        """結果に実行時間が含まれること"""
        result = registry.execute("property_estimation", {
            "substance": "water",
            "property": "molecular_weight",
        })
        assert result.execution_time_ms >= 0

    def test_result_to_dict(self, registry):
        """結果がdict変換可能であること"""
        result = registry.execute("property_estimation", {
            "substance": "water",
            "property": "molecular_weight",
        })
        d = result.to_dict()
        assert "success" in d
        assert "skill_id" in d
        assert "outputs" in d
