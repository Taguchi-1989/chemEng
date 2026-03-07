"""
データフェッチャーモジュール

外部物性データソースへのアダプター群。
engines/__init__.py のパターンに倣い、遅延ロード＆レジストリ方式。

利用可能ソース:
- pubchem: PubChem REST API (115M+ compounds, 無料, APIキー不要)
- thermo: thermo/chemicals ライブラリ (30,000+ compounds, オフライン)
"""

from __future__ import annotations

import logging

from .base import DataFetcher, FetcherCapability, SearchResult

__all__ = [
    "DataFetcher",
    "FetcherCapability",
    "SearchResult",
    "get_available_fetchers",
    "get_fetcher",
    "search_all",
]

logger = logging.getLogger("chemeng")

_fetchers: list[DataFetcher] | None = None


def _init_fetchers() -> list[DataFetcher]:
    """フェッチャーを遅延初期化"""
    fetchers: list[DataFetcher] = []

    # PubChem (ネットワーク必要)
    try:
        from .pubchem import PubChemFetcher

        fetchers.append(PubChemFetcher())
    except Exception as e:
        logger.debug("PubChemFetcher init failed: %s", e)

    # thermo (オフライン)
    try:
        from .thermo_lookup import ThermoLookupFetcher

        f = ThermoLookupFetcher()
        if f.is_available():
            fetchers.append(f)
    except Exception as e:
        logger.debug("ThermoLookupFetcher init failed: %s", e)

    return fetchers


def get_available_fetchers() -> list[DataFetcher]:
    """利用可能なフェッチャー一覧"""
    global _fetchers
    if _fetchers is None:
        _fetchers = _init_fetchers()
    return _fetchers


def get_fetcher(name: str) -> DataFetcher | None:
    """名前でフェッチャーを取得"""
    for f in get_available_fetchers():
        if f.name == name:
            return f
    return None


def search_all(
    query: str, max_per_source: int = 3
) -> dict[str, list[SearchResult]]:
    """全ソースを横断検索"""
    results: dict[str, list[SearchResult]] = {}
    for fetcher in get_available_fetchers():
        try:
            results[fetcher.name] = fetcher.search(query, max_per_source)
        except Exception as e:
            logger.debug("Search failed on %s: %s", fetcher.name, e)
            results[fetcher.name] = []
    return results
