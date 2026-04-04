"""
ChemEng package exports.

This module also keeps backward-compatible top-level imports working for
code that still imports `core`, `data`, `engines`, and similar packages
directly from the repository root.
"""

from importlib import import_module
import sys

__version__ = "0.1.0"
__author__ = "WalkTalk Hub Team"

from .core.registry import SkillRegistry, execute_skill, get_registry
from .core.requirement import CalculationType, Condition, RequirementSpec, Substance
from .core.skill import CalculationResult, ParameterSchema, SkillDefinition

__all__ = [
    "RequirementSpec",
    "Substance",
    "Condition",
    "CalculationType",
    "SkillDefinition",
    "ParameterSchema",
    "CalculationResult",
    "SkillRegistry",
    "get_registry",
    "execute_skill",
]


def _register_legacy_package_aliases() -> None:
    """Expose subpackages under their legacy top-level names."""
    legacy_packages = (
        "core",
        "data",
        "engines",
        "fetchers",
        "interface",
        "skills",
    )

    for package in legacy_packages:
        sys.modules.setdefault(package, import_module(f"{__name__}.{package}"))


_register_legacy_package_aliases()
