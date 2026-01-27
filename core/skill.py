"""
スキル（計算テンプレート）定義データクラス

計算スキルのスキーマと実行結果を定義する。
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
import yaml


@dataclass
class ParameterSchema:
    """パラメータスキーマ"""

    name: str
    type: str  # float, int, str, list, dict, bool
    description: str = ""
    unit: str | None = None
    required: bool = True
    default: Any = None
    min_value: float | None = None
    max_value: float | None = None
    choices: list[Any] | None = None
    example: Any = None

    def validate(self, value: Any) -> tuple[bool, str | None]:
        """値を検証"""
        if value is None:
            if self.required and self.default is None:
                return False, f"{self.name} is required"
            return True, None

        # 型チェック
        type_map = {
            "float": (int, float),
            "int": int,
            "str": str,
            "list": list,
            "dict": dict,
            "bool": bool,
        }

        expected_type = type_map.get(self.type)
        if expected_type and not isinstance(value, expected_type):
            return False, f"{self.name} must be {self.type}, got {type(value).__name__}"

        # 数値範囲チェック
        if isinstance(value, (int, float)):
            if self.min_value is not None and value < self.min_value:
                return False, f"{self.name} must be >= {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"{self.name} must be <= {self.max_value}"

        # 選択肢チェック
        if self.choices is not None and value not in self.choices:
            return False, f"{self.name} must be one of {self.choices}"

        return True, None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParameterSchema":
        """辞書から生成"""
        return cls(
            name=data["name"],
            type=data.get("type", "float"),
            description=data.get("description", ""),
            unit=data.get("unit"),
            required=data.get("required", True),
            default=data.get("default"),
            min_value=data.get("min_value"),
            max_value=data.get("max_value"),
            choices=data.get("choices"),
            example=data.get("example"),
        )

    def to_dict(self) -> dict[str, Any]:
        """辞書に変換"""
        result = {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "required": self.required,
        }
        if self.unit:
            result["unit"] = self.unit
        if self.default is not None:
            result["default"] = self.default
        if self.min_value is not None:
            result["min_value"] = self.min_value
        if self.max_value is not None:
            result["max_value"] = self.max_value
        if self.choices:
            result["choices"] = self.choices
        if self.example is not None:
            result["example"] = self.example
        return result


@dataclass
class SkillDefinition:
    """スキル（計算テンプレート）定義"""

    id: str
    name: str
    description: str
    calculation_type: str

    # スキーマ
    input_schema: list[ParameterSchema] = field(default_factory=list)
    output_schema: list[ParameterSchema] = field(default_factory=list)

    # エンジン指定
    required_engines: list[str] = field(default_factory=list)

    # テンプレートパス
    template_path: Path | None = None

    # デフォルト値
    defaults: dict[str, Any] = field(default_factory=dict)

    # 検証ルール
    validation_rules: list[str] = field(default_factory=list)

    # メタデータ
    version: str = "1.0.0"
    author: str = "system"
    tags: list[str] = field(default_factory=list)

    def validate_inputs(self, params: dict[str, Any]) -> tuple[bool, list[str]]:
        """入力パラメータを検証"""
        errors = []

        for schema in self.input_schema:
            value = params.get(schema.name, schema.default)
            valid, error = schema.validate(value)
            if not valid:
                errors.append(error)

        return len(errors) == 0, errors

    def get_input_with_defaults(self, params: dict[str, Any]) -> dict[str, Any]:
        """デフォルト値を適用した入力を取得"""
        result = {}

        for schema in self.input_schema:
            if schema.name in params:
                result[schema.name] = params[schema.name]
            elif schema.name in self.defaults:
                result[schema.name] = self.defaults[schema.name]
            elif schema.default is not None:
                result[schema.name] = schema.default

        return result

    @classmethod
    def from_yaml(cls, path: Path) -> "SkillDefinition":
        """YAMLファイルから読み込み"""
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data, path.parent)

    @classmethod
    def from_dict(cls, data: dict[str, Any], base_path: Path | None = None) -> "SkillDefinition":
        """辞書から生成"""
        input_schema = [ParameterSchema.from_dict(p) for p in data.get("input_schema", [])]
        output_schema = [ParameterSchema.from_dict(p) for p in data.get("output_schema", [])]

        template_path = None
        if "template_path" in data and base_path:
            template_path = base_path / data["template_path"]

        return cls(
            id=data["skill_id"] if "skill_id" in data else data["id"],
            name=data["name"],
            description=data.get("description", ""),
            calculation_type=data.get("calculation_type", ""),
            input_schema=input_schema,
            output_schema=output_schema,
            required_engines=data.get("required_engines", []),
            template_path=template_path,
            defaults=data.get("defaults", {}),
            validation_rules=data.get("validation_rules", []),
            version=data.get("version", "1.0.0"),
            author=data.get("author", "system"),
            tags=data.get("tags", []),
        )

    def to_dict(self) -> dict[str, Any]:
        """辞書に変換"""
        return {
            "skill_id": self.id,
            "name": self.name,
            "description": self.description,
            "calculation_type": self.calculation_type,
            "input_schema": [p.to_dict() for p in self.input_schema],
            "output_schema": [p.to_dict() for p in self.output_schema],
            "required_engines": self.required_engines,
            "template_path": str(self.template_path) if self.template_path else None,
            "defaults": self.defaults,
            "validation_rules": self.validation_rules,
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
        }


@dataclass
class CalculationResult:
    """計算結果"""

    skill_id: str
    success: bool

    # 入出力
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)

    # 診断
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    # メタデータ
    execution_time_ms: int = 0
    engine_used: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    @classmethod
    def success_result(
        cls,
        skill_id: str,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        engine: str = "",
        warnings: list[str] | None = None,
        execution_time_ms: int = 0,
    ) -> "CalculationResult":
        """成功結果を生成"""
        return cls(
            skill_id=skill_id,
            success=True,
            inputs=inputs,
            outputs=outputs,
            warnings=warnings or [],
            errors=[],
            engine_used=engine,
            execution_time_ms=execution_time_ms,
        )

    @classmethod
    def error_result(
        cls,
        skill_id: str,
        inputs: dict[str, Any],
        errors: list[str],
    ) -> "CalculationResult":
        """エラー結果を生成"""
        return cls(
            skill_id=skill_id,
            success=False,
            inputs=inputs,
            outputs={},
            warnings=[],
            errors=errors,
        )

    def to_dict(self) -> dict[str, Any]:
        """辞書に変換"""
        return {
            "skill_id": self.skill_id,
            "success": self.success,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "warnings": self.warnings,
            "errors": self.errors,
            "execution_time_ms": self.execution_time_ms,
            "engine_used": self.engine_used,
            "timestamp": self.timestamp.isoformat(),
        }
