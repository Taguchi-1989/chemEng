"""
互換性ユーティリティ

Vercel（フラットインポート）とローカル（パッケージインポート）の
両方をサポートするインポートヘルパー。
"""

from __future__ import annotations


def import_engine(engine_class_name: str, module_name: str):
    """
    エンジンクラスをインポートする。

    Vercel環境では `engines.xxx` として、ローカル環境では
    `chemeng.engines.xxx` としてインポートを試みる。

    Args:
        engine_class_name: クラス名 (e.g. "ThermoEngine")
        module_name: モジュール名 (e.g. "thermo_engine")

    Returns:
        インポートされたクラス

    Raises:
        ImportError: いずれの方法でもインポートできない場合
    """
    # 1. フラット (Vercel / sys.path にプロジェクトルートがある場合)
    try:
        mod = __import__(f"engines.{module_name}", fromlist=[engine_class_name])
        return getattr(mod, engine_class_name)
    except ImportError:
        pass

    # 2. パッケージ (ローカル開発環境)
    try:
        mod = __import__(f"chemeng.engines.{module_name}", fromlist=[engine_class_name])
        return getattr(mod, engine_class_name)
    except ImportError:
        pass

    raise ImportError(
        f"Cannot import {engine_class_name} from engines.{module_name} "
        f"or chemeng.engines.{module_name}"
    )


def get_thermo_engine():
    """ThermoEngineのインスタンスを取得する便利関数"""
    cls = import_engine("ThermoEngine", "thermo_engine")
    return cls()
