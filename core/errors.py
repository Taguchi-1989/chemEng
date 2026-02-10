"""
安全なエラーハンドリング

内部例外をユーザー向けメッセージに変換し、詳細はログに記録する。
"""

from __future__ import annotations

import logging
import uuid

logger = logging.getLogger("chemeng")

# 既知のエンジン例外 → ユーザー向けメッセージ
_ENGINE_ERROR_MESSAGES = {
    "SubstanceNotFoundError": "指定された物質が見つかりません: {substance}",
    "PropertyNotAvailableError": "指定された物性は利用できません: {property_name} ({substance})",
    "ConditionsOutOfRangeError": "指定された条件が有効範囲外です",
}


def safe_error_message(exc: Exception) -> str:
    """
    例外をユーザー向けの安全なメッセージに変換する。

    既知の例外は具体的なメッセージに、未知の例外は参照IDと共に
    汎用メッセージに変換する。詳細はすべてログに記録される。

    Args:
        exc: キャッチした例外

    Returns:
        ユーザーに表示して安全なエラーメッセージ
    """
    exc_type = type(exc).__name__

    # 既知のエンジン例外
    if exc_type in _ENGINE_ERROR_MESSAGES:
        template = _ENGINE_ERROR_MESSAGES[exc_type]
        attrs = vars(exc) if hasattr(exc, "__dict__") else {}
        try:
            msg = template.format(**attrs)
        except (KeyError, IndexError):
            msg = str(exc)
        logger.warning("Known error: %s - %s", exc_type, exc)
        return msg

    # ValueError / TypeError はメッセージをそのまま返す（入力検証由来が多い）
    if isinstance(exc, (ValueError, TypeError)):
        logger.warning("Validation error: %s", exc)
        return str(exc)

    # NotImplementedError
    if isinstance(exc, NotImplementedError):
        logger.warning("Not implemented: %s", exc)
        return f"この操作はサポートされていません: {exc}"

    # 未知の例外 → 参照IDでログに記録し、汎用メッセージを返す
    ref_id = uuid.uuid4().hex[:8]
    logger.error("Unexpected error (ref: %s): %s", ref_id, exc, exc_info=True)
    return f"内部計算エラーが発生しました (ref: {ref_id})"
