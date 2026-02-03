"""pytest設定とフィクスチャ"""

import sys
from pathlib import Path

import pytest

# chemengモジュールをパスに追加
# chemEngフォルダをchemengとしてインポート可能にする
project_root = Path(__file__).parent.parent
parent_dir = project_root.parent
sys.path.insert(0, str(parent_dir))

# chemEngをchemengとしてエイリアス作成
import importlib
import importlib.util
spec = importlib.util.spec_from_file_location("chemeng", str(project_root / "__init__.py"),
    submodule_search_locations=[str(project_root)])
chemeng_module = importlib.util.module_from_spec(spec)
sys.modules["chemeng"] = chemeng_module
spec.loader.exec_module(chemeng_module)


@pytest.fixture
def sample_substances():
    """サンプル物質リスト"""
    from chemeng.core.requirement import Substance

    return [
        Substance(name="ethanol", cas_number="64-17-5", formula="C2H5OH"),
        Substance(name="water", cas_number="7732-18-5", formula="H2O"),
        Substance(name="methanol", cas_number="67-56-1", formula="CH3OH"),
    ]


@pytest.fixture
def sample_condition():
    """サンプル条件"""
    from chemeng.core.requirement import Condition

    return Condition(
        temperature=350.0,
        pressure=101325.0,
        composition={"ethanol": 0.4, "water": 0.6},
    )


@pytest.fixture
def sample_requirement(sample_substances, sample_condition):
    """サンプル要件"""
    from chemeng.core.requirement import CalculationType, RequirementSpec

    return RequirementSpec(
        description="Distillation column design for ethanol-water separation",
        calculation_type=CalculationType.DISTILLATION,
        substances=sample_substances[:2],
        inlet_conditions=[sample_condition],
        targets={"distillate_purity": 0.95, "bottoms_purity": 0.98},
    )


@pytest.fixture
def sample_skill():
    """サンプルスキル定義"""
    from chemeng.core.skill import ParameterSchema, SkillDefinition

    return SkillDefinition(
        id="property_estimation",
        name="物性推算",
        description="純物質の物性値を計算する",
        calculation_type="property_estimation",
        input_schema=[
            ParameterSchema(
                name="substance",
                type="str",
                description="物質名またはCAS番号",
                required=True,
            ),
            ParameterSchema(
                name="property",
                type="str",
                description="物性名",
                required=True,
                choices=[
                    "vapor_pressure",
                    "density",
                    "viscosity",
                    "heat_capacity",
                ],
            ),
            ParameterSchema(
                name="temperature",
                type="float",
                description="温度",
                unit="K",
                required=True,
                min_value=100.0,
                max_value=1000.0,
            ),
            ParameterSchema(
                name="pressure",
                type="float",
                description="圧力",
                unit="Pa",
                required=False,
                default=101325.0,
            ),
        ],
        output_schema=[
            ParameterSchema(
                name="value",
                type="float",
                description="計算された物性値",
            ),
            ParameterSchema(
                name="unit",
                type="str",
                description="単位",
            ),
        ],
        required_engines=["thermo"],
    )
