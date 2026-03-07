"""
データフェッチャー基底クラス

engines/base.py のパターンに倣い、外部データソースの共通インターフェースを定義。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from data import SubstanceRecord


@dataclass
class FetcherCapability:
    """フェッチャー能力"""

    source_name: str  # "PubChem", "NIST WebBook"
    source_url: str
    requires_api_key: bool = False
    available_properties: list[str] = field(default_factory=list)
    compound_count: str = ""  # "115M+ compounds"
    rate_limit: str = ""  # "5 requests/second"
    supports_japanese: bool = False


@dataclass
class SearchResult:
    """外部ソースの検索結果"""

    name: str
    cas: str = ""
    formula: str = ""
    molecular_weight: float | None = None
    source: str = ""
    source_id: str = ""  # PubChem CID等
    available_properties: list[str] = field(default_factory=list)


class DataFetcher(ABC):
    """データフェッチャー基底クラス"""

    @property
    @abstractmethod
    def name(self) -> str:
        """フェッチャー名 (例: "pubchem")"""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> FetcherCapability:
        """フェッチャー能力"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """利用可能か（ネットワーク、APIキー等）"""
        pass

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """物質を検索（名前、CAS、分子式）"""
        pass

    @abstractmethod
    def fetch_properties(
        self,
        identifier: str,
        properties: list[str] | None = None,
    ) -> SubstanceRecord:
        """物性データを取得

        Args:
            identifier: 物質名、CAS番号、またはソース固有ID
            properties: 取得する物性（None=全て）

        Returns:
            取得データを含むSubstanceRecord
        """
        pass

    def __repr__(self) -> str:
        available = "available" if self.is_available() else "not available"
        return f"{self.__class__.__name__}({self.name}, {available})"
