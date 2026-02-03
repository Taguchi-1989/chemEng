"""コアモジュールのテスト"""


import pytest
from chemeng.core.requirement import (
    CalculationType,
    Condition,
    RequirementSpec,
    Substance,
)
from chemeng.core.skill import (
    CalculationResult,
    ParameterSchema,
    SkillDefinition,
)


class TestSubstance:
    """Substanceクラスのテスト"""

    def test_create_simple(self):
        """基本的な物質作成"""
        s = Substance(name="ethanol")
        assert s.name == "ethanol"
        assert s.cas_number is None
        assert s.formula is None

    def test_create_full(self):
        """全属性を指定して作成"""
        s = Substance(
            name="ethanol",
            cas_number="64-17-5",
            formula="C2H5OH",
            synonyms=["ethyl alcohol", "alcohol"],
        )
        assert s.name == "ethanol"
        assert s.cas_number == "64-17-5"
        assert s.formula == "C2H5OH"
        assert len(s.synonyms) == 2

    def test_empty_name_raises(self):
        """空の名前はエラー"""
        with pytest.raises(ValueError):
            Substance(name="")

    def test_to_dict_roundtrip(self):
        """辞書変換の往復"""
        s = Substance(name="water", cas_number="7732-18-5", formula="H2O")
        d = s.to_dict()
        s2 = Substance.from_dict(d)
        assert s.name == s2.name
        assert s.cas_number == s2.cas_number
        assert s.formula == s2.formula


class TestCondition:
    """Conditionクラスのテスト"""

    def test_create_simple(self):
        """基本的な条件作成"""
        c = Condition(temperature=350.0, pressure=101325.0)
        assert c.temperature == 350.0
        assert c.pressure == 101325.0

    def test_composition_validation(self):
        """組成の合計が1.0でないとエラー"""
        with pytest.raises(ValueError):
            Condition(composition={"ethanol": 0.5, "water": 0.3})  # 合計0.8

    def test_composition_valid(self):
        """組成の合計が1.0なら正常"""
        c = Condition(composition={"ethanol": 0.4, "water": 0.6})
        assert abs(sum(c.composition.values()) - 1.0) < 0.01

    def test_to_dict_roundtrip(self):
        """辞書変換の往復"""
        c = Condition(temperature=300.0, pressure=200000.0, phase="liquid")
        d = c.to_dict()
        c2 = Condition.from_dict(d)
        assert c.temperature == c2.temperature
        assert c.pressure == c2.pressure
        assert c.phase == c2.phase


class TestRequirementSpec:
    """RequirementSpecクラスのテスト"""

    def test_create_default(self):
        """デフォルト値で作成"""
        r = RequirementSpec()
        assert r.id is not None
        assert r.calculation_type == CalculationType.PROPERTY_ESTIMATION

    def test_create_with_substances(self):
        """物質を含めて作成"""
        r = RequirementSpec(
            description="Calculate vapor pressure",
            calculation_type=CalculationType.PROPERTY_ESTIMATION,
            substances=[
                Substance(name="ethanol"),
                Substance(name="water"),
            ],
        )
        assert len(r.substances) == 2
        assert r.substances[0].name == "ethanol"

    def test_add_substance(self):
        """物質を追加"""
        r = RequirementSpec()
        r.add_substance(Substance(name="benzene"))
        assert len(r.substances) == 1

    def test_set_target(self):
        """目標値を設定"""
        r = RequirementSpec()
        r.set_target("purity", 0.95)
        assert r.targets["purity"] == 0.95

    def test_to_dict_roundtrip(self):
        """辞書変換の往復"""
        r = RequirementSpec(
            description="Test requirement",
            calculation_type=CalculationType.DISTILLATION,
            substances=[Substance(name="ethanol")],
            targets={"purity": 0.99},
        )
        d = r.to_dict()
        r2 = RequirementSpec.from_dict(d)
        assert r.description == r2.description
        assert r.calculation_type == r2.calculation_type
        assert len(r.substances) == len(r2.substances)


class TestParameterSchema:
    """ParameterSchemaクラスのテスト"""

    def test_validate_required(self):
        """必須パラメータの検証"""
        schema = ParameterSchema(name="temperature", type="float", required=True)
        valid, error = schema.validate(None)
        assert not valid
        assert "required" in error.lower()

    def test_validate_type_float(self):
        """float型の検証"""
        schema = ParameterSchema(name="temperature", type="float")
        valid, _ = schema.validate(350.0)
        assert valid
        valid, _ = schema.validate(350)  # intもOK
        assert valid
        valid, error = schema.validate("350")
        assert not valid

    def test_validate_range(self):
        """範囲の検証"""
        schema = ParameterSchema(
            name="temperature", type="float", min_value=200.0, max_value=600.0
        )
        valid, _ = schema.validate(350.0)
        assert valid
        valid, error = schema.validate(100.0)
        assert not valid
        valid, error = schema.validate(700.0)
        assert not valid

    def test_validate_choices(self):
        """選択肢の検証"""
        schema = ParameterSchema(
            name="phase", type="str", choices=["liquid", "vapor", "two-phase"]
        )
        valid, _ = schema.validate("liquid")
        assert valid
        valid, error = schema.validate("solid")
        assert not valid


class TestSkillDefinition:
    """SkillDefinitionクラスのテスト"""

    def test_create(self):
        """スキル作成"""
        skill = SkillDefinition(
            id="property_estimation",
            name="物性推算",
            description="物性値を計算",
            calculation_type="property_estimation",
            input_schema=[
                ParameterSchema(name="substance", type="str"),
                ParameterSchema(name="temperature", type="float", unit="K"),
            ],
            required_engines=["thermo"],
        )
        assert skill.id == "property_estimation"
        assert len(skill.input_schema) == 2

    def test_validate_inputs(self):
        """入力検証"""
        skill = SkillDefinition(
            id="test",
            name="Test",
            description="",
            calculation_type="test",
            input_schema=[
                ParameterSchema(name="temperature", type="float", required=True),
                ParameterSchema(
                    name="pressure", type="float", required=False, default=101325.0
                ),
            ],
        )

        valid, errors = skill.validate_inputs({"temperature": 350.0})
        assert valid
        assert len(errors) == 0

        valid, errors = skill.validate_inputs({})
        assert not valid
        assert len(errors) == 1

    def test_get_input_with_defaults(self):
        """デフォルト値の適用"""
        skill = SkillDefinition(
            id="test",
            name="Test",
            description="",
            calculation_type="test",
            input_schema=[
                ParameterSchema(name="temperature", type="float"),
                ParameterSchema(name="pressure", type="float", default=101325.0),
            ],
            defaults={"temperature": 298.15},
        )

        inputs = skill.get_input_with_defaults({})
        assert inputs["temperature"] == 298.15
        assert inputs["pressure"] == 101325.0

        inputs = skill.get_input_with_defaults({"temperature": 350.0})
        assert inputs["temperature"] == 350.0


class TestCalculationResult:
    """CalculationResultクラスのテスト"""

    def test_success_result(self):
        """成功結果の生成"""
        result = CalculationResult.success_result(
            skill_id="property_estimation",
            inputs={"substance": "ethanol", "temperature": 350.0},
            outputs={"vapor_pressure": 100000.0},
            engine="thermo",
        )
        assert result.success
        assert result.skill_id == "property_estimation"
        assert result.outputs["vapor_pressure"] == 100000.0
        assert len(result.errors) == 0

    def test_error_result(self):
        """エラー結果の生成"""
        result = CalculationResult.error_result(
            skill_id="property_estimation",
            inputs={"substance": "unknown"},
            errors=["Substance not found"],
        )
        assert not result.success
        assert len(result.errors) == 1
        assert "Substance not found" in result.errors[0]

    def test_to_dict(self):
        """辞書変換"""
        result = CalculationResult.success_result(
            skill_id="test",
            inputs={"a": 1},
            outputs={"b": 2},
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["inputs"] == {"a": 1}
        assert d["outputs"] == {"b": 2}
