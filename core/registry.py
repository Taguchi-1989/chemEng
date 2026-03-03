"""
スキルレジストリ

スキル（計算テンプレート）の登録・検索・実行を管理する。
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from .errors import safe_error_message
from .skill import CalculationResult, SkillDefinition

logger = logging.getLogger("chemeng")

# Use try/except to support both package import and direct module import (Vercel)
try:
    from ..engines import get_available_engines
    from ..engines.base import CalculationEngine
except ImportError:
    from engines import get_available_engines
    from engines.base import CalculationEngine


class SkillRegistry:
    """スキルレジストリ"""

    def __init__(self, skills_dir: Path | None = None):
        """
        Args:
            skills_dir: スキル定義ディレクトリ（デフォルト: chemeng/skills）
        """
        if skills_dir is None:
            skills_dir = Path(__file__).parent.parent / "skills"
        self.skills_dir = skills_dir
        self.schema_dir = skills_dir / "schema"
        self.templates_dir = skills_dir / "templates"
        self.defaults_dir = skills_dir / "defaults"

        self._skills: dict[str, SkillDefinition] = {}
        self._templates: dict[str, Callable] = {}
        self._engines: list[CalculationEngine] = []

        self._load_skills()
        self._load_engines()

    def _load_skills(self):
        """スキル定義を読み込み"""
        if not self.schema_dir.exists():
            return

        for schema_file in self.schema_dir.glob("*.yaml"):
            try:
                skill = SkillDefinition.from_yaml(schema_file)
                # テンプレートパスを設定
                template_file = self.templates_dir / f"{schema_file.stem}.py"
                if template_file.exists():
                    skill.template_path = template_file
                # デフォルト値を読み込み
                skill.defaults = self._load_defaults(skill)
                self._skills[skill.id] = skill
            except Exception as e:
                logger.warning("Failed to load skill %s: %s", schema_file.name, e)

    def _load_defaults(self, skill: SkillDefinition) -> dict[str, Any]:
        """スキルのデフォルト値を読み込み"""
        defaults = dict(skill.defaults)  # スキーマ内のデフォルト値

        # defaults_file が指定されていれば読み込み
        defaults_file = self.defaults_dir / "common_substances.yaml"
        if defaults_file.exists():
            try:
                with open(defaults_file, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                # calculation_type に対応するデフォルト条件を取得
                if "default_conditions" in data:
                    calc_defaults = data["default_conditions"].get(
                        skill.calculation_type, {}
                    )
                    for key, value in calc_defaults.items():
                        if key not in defaults:
                            defaults[key] = value
            except Exception:
                pass

        return defaults

    def _load_engines(self):
        """利用可能なエンジンを読み込み"""
        self._engines = get_available_engines()

    def _load_template(self, skill: SkillDefinition) -> Callable | None:
        """テンプレートモジュールを読み込み"""
        if skill.id in self._templates:
            return self._templates[skill.id]

        if skill.template_path is None or not skill.template_path.exists():
            return None

        try:
            spec = importlib.util.spec_from_file_location(
                f"chemeng.skills.templates.{skill.id}",
                skill.template_path,
            )
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            # Ensure module is in sys.modules for decorators (e.g., dataclasses)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            if hasattr(module, "execute"):
                self._templates[skill.id] = module.execute
                return module.execute

        except Exception as e:
            logger.warning("Failed to load template for %s: %s", skill.id, e)

        return None

    def _get_engine(self, engine_name: str) -> CalculationEngine | None:
        """エンジンを取得"""
        for engine in self._engines:
            if engine.name == engine_name:
                return engine
        return None

    def register(self, skill: SkillDefinition):
        """スキルを登録"""
        self._skills[skill.id] = skill

    def get_skill(self, skill_id: str) -> SkillDefinition | None:
        """スキルを取得"""
        return self._skills.get(skill_id)

    def list_skills(self) -> list[SkillDefinition]:
        """全スキルを取得"""
        return list(self._skills.values())

    def find_skills(
        self,
        calculation_type: str | None = None,
        tags: list[str] | None = None,
    ) -> list[SkillDefinition]:
        """条件に合うスキルを検索"""
        results = []
        for skill in self._skills.values():
            if calculation_type and skill.calculation_type != calculation_type:
                continue
            if tags:
                if not any(tag in skill.tags for tag in tags):
                    continue
            results.append(skill)
        return results

    def execute(
        self,
        skill_id: str,
        params: dict[str, Any],
        engine_name: str | None = None,
    ) -> CalculationResult:
        """
        スキルを実行

        Args:
            skill_id: スキルID
            params: 入力パラメータ
            engine_name: 使用するエンジン名（指定しない場合は自動選択）

        Returns:
            計算結果
        """
        skill = self.get_skill(skill_id)
        if skill is None:
            return CalculationResult.error_result(
                skill_id=skill_id,
                inputs=params,
                errors=[f"Skill not found: {skill_id}"],
            )

        # デフォルト値を適用
        full_params = skill.get_input_with_defaults(params)

        # 入力検証
        valid, errors = skill.validate_inputs(full_params)
        if not valid:
            return CalculationResult.error_result(
                skill_id=skill_id,
                inputs=full_params,
                errors=errors,
            )

        # エンジン選択
        engine = None
        if engine_name:
            engine = self._get_engine(engine_name)
        else:
            for eng_name in skill.required_engines:
                engine = self._get_engine(eng_name)
                if engine:
                    break

        # テンプレート実行
        template = self._load_template(skill)
        if template:
            try:
                start_time = time.time()
                result = template(full_params, engine=engine)
                execution_time = int((time.time() - start_time) * 1000)

                if isinstance(result, dict):
                    if result.get("success") is False:
                        return CalculationResult.error_result(
                            skill_id=skill_id,
                            inputs=full_params,
                            errors=result.get("errors", ["Calculation failed"]),
                        )
                    return CalculationResult.success_result(
                        skill_id=skill_id,
                        inputs=full_params,
                        outputs=result.get("outputs", result),
                        engine=engine.name if engine else "",
                        warnings=result.get("warnings", []),
                        execution_time_ms=execution_time,
                    )
                else:
                    return CalculationResult.success_result(
                        skill_id=skill_id,
                        inputs=full_params,
                        outputs={"result": result},
                        engine=engine.name if engine else "",
                        execution_time_ms=execution_time,
                    )

            except Exception as e:
                return CalculationResult.error_result(
                    skill_id=skill_id,
                    inputs=full_params,
                    errors=[safe_error_message(e)],
                )

        # テンプレートがない場合はエンジン直接実行
        if engine is None:
            return CalculationResult.error_result(
                skill_id=skill_id,
                inputs=full_params,
                errors=["No template or engine available"],
            )

        # 汎用的なエンジン実行（物性推算など）
        try:
            start_time = time.time()
            outputs = self._execute_with_engine(skill, full_params, engine)
            execution_time = int((time.time() - start_time) * 1000)

            return CalculationResult.success_result(
                skill_id=skill_id,
                inputs=full_params,
                outputs=outputs,
                engine=engine.name,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            return CalculationResult.error_result(
                skill_id=skill_id,
                inputs=full_params,
                errors=[safe_error_message(e)],
            )

    def _execute_with_engine(
        self,
        skill: SkillDefinition,
        params: dict[str, Any],
        engine: CalculationEngine,
    ) -> dict[str, Any]:
        """エンジンを使用して実行"""
        calc_type = skill.calculation_type

        if calc_type == "property_estimation":
            substance = params.get("substance")
            property_name = params.get("property")
            conditions = {
                "temperature": params.get("temperature", 298.15),
                "pressure": params.get("pressure", 101325.0),
            }
            value = engine.get_property(substance, property_name, conditions)
            return {"value": value, "property": property_name, "substance": substance}

        elif calc_type == "vle":
            substances = params.get("substances", [])
            composition = params.get("composition", {})
            conditions = {
                "temperature": params.get("temperature", 298.15),
                "pressure": params.get("pressure", 101325.0),
            }
            return engine.calculate_equilibrium(substances, composition, conditions)

        else:
            raise NotImplementedError(f"Calculation type not supported: {calc_type}")


# グローバルレジストリインスタンス
_registry: SkillRegistry | None = None


def get_registry() -> SkillRegistry:
    """グローバルレジストリを取得"""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry


def execute_skill(skill_id: str, params: dict[str, Any]) -> CalculationResult:
    """スキルを実行（便利関数）"""
    return get_registry().execute(skill_id, params)
