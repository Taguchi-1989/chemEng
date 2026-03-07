"""
ローカル物性データベース

カスタム物質データのYAML読み書き、検索、マージを行う。
common_substances.yaml との統合ビューも提供。
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from . import PropertyValue, SubstanceRecord

logger = logging.getLogger("chemeng")

_db_instance: PropertyDatabase | None = None


def get_property_db(data_dir: Path | None = None) -> PropertyDatabase:
    """シングルトンでPropertyDatabaseを取得"""
    global _db_instance
    if _db_instance is None:
        _db_instance = PropertyDatabase(data_dir)
    return _db_instance


class PropertyDatabase:
    """ローカル物性データベース

    data/custom_substances.yaml に物性データを永続化する。
    skills/defaults/common_substances.yaml とのマージビューも提供。
    """

    def __init__(self, data_dir: Path | None = None):
        if data_dir is None:
            data_dir = Path(__file__).parent
        self.data_dir = data_dir
        self.db_file = data_dir / "custom_substances.yaml"
        self._records: dict[str, SubstanceRecord] = {}
        self._load()

    def _load(self) -> None:
        """custom_substances.yaml を読み込み"""
        if not self.db_file.exists():
            return
        try:
            with open(self.db_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not data or not isinstance(data, dict):
                return
            substances = data.get("substances", {})
            for key, sub_data in substances.items():
                try:
                    self._records[key] = SubstanceRecord.from_dict(sub_data)
                except Exception as e:
                    logger.warning("Failed to load substance %s: %s", key, e)
        except Exception as e:
            logger.warning("Failed to load custom_substances.yaml: %s", e)

    def _save(self) -> None:
        """custom_substances.yaml に書き出し"""
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "substances": {},
        }
        for key, record in sorted(self._records.items()):
            data["substances"][key] = record.to_dict()

        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.db_file, "w", encoding="utf-8") as f:
            yaml.dump(
                data,
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
                width=120,
            )

    @staticmethod
    def _normalize_key(name: str) -> str:
        """物質名をキーに正規化"""
        key = name.strip().lower()
        key = re.sub(r"[^a-z0-9\u3040-\u9fff-]", "_", key)
        key = re.sub(r"_+", "_", key).strip("_")
        return key

    def search(self, query: str) -> list[SubstanceRecord]:
        """ローカルDBを名前、CAS、分子式、エイリアスで検索"""
        query_lower = query.strip().lower()
        results = []
        for record in self._records.values():
            if self._matches(record, query_lower):
                results.append(record)
        return results

    @staticmethod
    def _matches(record: SubstanceRecord, query: str) -> bool:
        """レコードがクエリにマッチするか"""
        if query in record.name.lower():
            return True
        if record.name_ja and query in record.name_ja:
            return True
        if record.cas and query == record.cas:
            return True
        if record.formula and query == record.formula.lower():
            return True
        for alias in record.aliases:
            if query in alias.lower():
                return True
        return False

    def get(self, identifier: str) -> SubstanceRecord | None:
        """名前、CAS、キーで取得"""
        key = self._normalize_key(identifier)
        if key in self._records:
            return self._records[key]
        # CAS番号検索
        for record in self._records.values():
            if record.cas == identifier:
                return record
        # 名前検索
        id_lower = identifier.lower()
        for record in self._records.values():
            if record.name.lower() == id_lower:
                return record
        return None

    def add_or_update(self, record: SubstanceRecord) -> SubstanceRecord:
        """物質を追加またはマージ"""
        key = self._normalize_key(record.name or record.cas or "unknown")
        existing = self._records.get(key)
        if existing:
            existing.merge_from(record)
            self._save()
            return existing
        else:
            if not record.added_at:
                record.added_at = datetime.now().isoformat()
            record.updated_at = datetime.now().isoformat()
            self._records[key] = record
            self._save()
            return record

    def add_property(
        self, identifier: str, prop: PropertyValue
    ) -> bool:
        """既存物質に物性値を追加"""
        record = self.get(identifier)
        if record is None:
            return False
        values = record.properties.setdefault(prop.property_name, [])
        # 同ソースの重複チェック
        for existing in values:
            if existing.source == prop.source:
                existing.value = prop.value
                existing.unit = prop.unit
                existing.retrieved_at = prop.retrieved_at
                record.updated_at = datetime.now().isoformat()
                self._save()
                return True
        values.append(prop)
        record.updated_at = datetime.now().isoformat()
        self._save()
        return True

    def list_all(self, category: str | None = None) -> list[SubstanceRecord]:
        """全物質一覧（カテゴリフィルタ可）"""
        records = list(self._records.values())
        if category:
            records = [r for r in records if r.category == category]
        return sorted(records, key=lambda r: r.name)

    def delete(self, identifier: str) -> bool:
        """物質を削除"""
        key = self._normalize_key(identifier)
        if key in self._records:
            del self._records[key]
            self._save()
            return True
        # 名前/CASで探してキーを特定
        for k, record in list(self._records.items()):
            if record.cas == identifier or record.name.lower() == identifier.lower():
                del self._records[k]
                self._save()
                return True
        return False

    def get_property_value(
        self, substance: str, property_name: str
    ) -> PropertyValue | None:
        """物質の物性値を取得（best valueを返す）"""
        record = self.get(substance)
        if record is None:
            return None
        return record.get_best_property(property_name)

    def count(self) -> int:
        """登録物質数"""
        return len(self._records)
