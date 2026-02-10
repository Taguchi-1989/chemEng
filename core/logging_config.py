"""
ログ設定

環境変数 CHEMENG_LOG_LEVEL でログレベルを制御（デフォルト: WARNING）。
stderr出力でVercelサーバーレス環境と互換性あり。
"""

from __future__ import annotations

import logging
import os


def setup_logging() -> None:
    """chemengロガーを設定する。"""
    level_name = os.environ.get("CHEMENG_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)

    logger = logging.getLogger("chemeng")
    if logger.handlers:
        return  # 既に設定済み

    handler = logging.StreamHandler()  # stderr
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(level)
