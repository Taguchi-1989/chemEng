"""
PubChem データフェッチャー

PubChem PUG REST / PUG View API を使用して物性データを取得する。
無料、APIキー不要、115M+ 化合物。

API docs: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from data import PropertyValue, SubstanceRecord
from data.units import convert_to_si, parse_value_with_unit

from .base import DataFetcher, FetcherCapability, SearchResult

logger = logging.getLogger("chemeng")

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PUBCHEM_VIEW = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view"
USER_AGENT = "ChemEng/0.1 (Chemical Engineering Calculator)"

# PubChem PUG View の見出し→内部物性名マッピング
HEADING_MAP: dict[str, str] = {
    "Boiling Point": "boiling_point",
    "Melting Point": "melting_point",
    "Density": "liquid_density",
    "Vapor Pressure": "vapor_pressure",
    "Viscosity": "liquid_viscosity",
    "Surface Tension": "surface_tension",
    "Heat of Vaporization": "heat_of_vaporization",
    "Enthalpy of Vaporization": "heat_of_vaporization",
    "Heat of Combustion": "heat_of_combustion",
    "Flash Point": "flash_point",
    "Autoignition Temperature": "autoignition_temperature",
    "Refractive Index": "refractive_index",
    "Solubility": "solubility",
}

# 温度系の物性（単位変換時に温度変換を使う）
TEMPERATURE_PROPERTIES = {
    "boiling_point",
    "melting_point",
    "flash_point",
    "autoignition_temperature",
}

# 圧力系の物性
PRESSURE_PROPERTIES = {"vapor_pressure"}

# 密度系の物性
DENSITY_PROPERTIES = {"liquid_density", "gas_density", "density"}

CACHE_TTL_HOURS = 24


class PubChemFetcher(DataFetcher):
    """PubChem REST APIフェッチャー"""

    def __init__(self, cache_dir: Path | None = None):
        if cache_dir is None:
            cache_dir = Path(__file__).resolve().parent.parent / "data" / "cache"
        self._cache_dir = cache_dir
        self._last_request_time = 0.0

    @property
    def name(self) -> str:
        return "pubchem"

    @property
    def capabilities(self) -> FetcherCapability:
        return FetcherCapability(
            source_name="PubChem",
            source_url="https://pubchem.ncbi.nlm.nih.gov",
            requires_api_key=False,
            available_properties=list(HEADING_MAP.values()),
            compound_count="115M+ compounds",
            rate_limit="5 requests/second",
            supports_japanese=False,
        )

    def is_available(self) -> bool:
        try:
            url = f"{PUBCHEM_BASE}/compound/name/water/property/MolecularWeight/JSON"
            self._get_json(url, timeout=5)
            return True
        except Exception:
            return False

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """PubChemで物質を検索"""
        results: list[SearchResult] = []

        try:
            encoded = urllib.parse.quote(query, safe="")
            url = (
                f"{PUBCHEM_BASE}/compound/name/{encoded}"
                f"/property/MolecularFormula,MolecularWeight,IUPACName/JSON"
            )
            data = self._get_json(url)
            props_list = data.get("PropertyTable", {}).get("Properties", [])
            for p in props_list[:max_results]:
                cid = p.get("CID", "")
                results.append(
                    SearchResult(
                        name=p.get("IUPACName", query),
                        formula=p.get("MolecularFormula", ""),
                        molecular_weight=_safe_float(p.get("MolecularWeight")),
                        source="pubchem",
                        source_id=str(cid),
                        available_properties=list(HEADING_MAP.values()),
                    )
                )
        except Exception as e:
            logger.debug("PubChem name search failed for %s: %s", query, e)

        # CAS番号っぽければ別ルートも試す
        if not results and _looks_like_cas(query):
            try:
                url = (
                    f"{PUBCHEM_BASE}/compound/name/{query}"
                    f"/property/MolecularFormula,MolecularWeight,IUPACName/JSON"
                )
                data = self._get_json(url)
                props_list = data.get("PropertyTable", {}).get("Properties", [])
                for p in props_list[:max_results]:
                    results.append(
                        SearchResult(
                            name=p.get("IUPACName", query),
                            formula=p.get("MolecularFormula", ""),
                            molecular_weight=_safe_float(p.get("MolecularWeight")),
                            source="pubchem",
                            source_id=str(p.get("CID", "")),
                            available_properties=list(HEADING_MAP.values()),
                        )
                    )
            except Exception:
                pass

        return results

    def fetch_properties(
        self,
        identifier: str,
        properties: list[str] | None = None,
    ) -> SubstanceRecord:
        """PubChemから物性データを取得"""
        # Step 1: CID解決
        cid = self._resolve_cid(identifier)

        # Step 2: 基本情報取得
        basic = self._fetch_basic_info(cid)

        # Step 3: CAS番号取得
        cas = self._fetch_cas(cid)

        # Step 4: 実験物性値取得
        exp_props = self._fetch_experimental_properties(cid, properties)

        now = datetime.now().isoformat()
        return SubstanceRecord(
            name=basic.get("IUPACName", identifier),
            cas=cas,
            formula=basic.get("MolecularFormula", ""),
            molecular_weight=_safe_float(basic.get("MolecularWeight")),
            smiles=basic.get("CanonicalSMILES", ""),
            inchi=basic.get("InChI", ""),
            pubchem_cid=cid,
            properties=exp_props,
            added_at=now,
            updated_at=now,
            sources_used=["pubchem"],
        )

    def _resolve_cid(self, identifier: str) -> int:
        """物質名/CASをPubChem CIDに解決"""
        encoded = urllib.parse.quote(identifier, safe="")
        url = f"{PUBCHEM_BASE}/compound/name/{encoded}/cids/JSON"
        data = self._get_json(url)
        cids = data.get("IdentifierList", {}).get("CID", [])
        if not cids:
            raise ValueError(f"PubChemで見つかりません: {identifier}")
        return cids[0]

    def _fetch_basic_info(self, cid: int) -> dict[str, Any]:
        """基本情報取得"""
        url = (
            f"{PUBCHEM_BASE}/compound/cid/{cid}"
            f"/property/MolecularFormula,MolecularWeight,"
            f"IUPACName,CanonicalSMILES,InChI/JSON"
        )
        data = self._get_json(url)
        props = data.get("PropertyTable", {}).get("Properties", [])
        return props[0] if props else {}

    def _fetch_cas(self, cid: int) -> str:
        """CAS番号を取得（Synonymsから）"""
        try:
            url = f"{PUBCHEM_BASE}/compound/cid/{cid}/synonyms/JSON"
            data = self._get_json(url)
            synonyms = (
                data.get("InformationList", {})
                .get("Information", [{}])[0]
                .get("Synonym", [])
            )
            for syn in synonyms:
                if _looks_like_cas(syn):
                    return syn
        except Exception:
            pass
        return ""

    def _fetch_experimental_properties(
        self, cid: int, filter_props: list[str] | None = None
    ) -> dict[str, list[PropertyValue]]:
        """PUG View APIから実験物性値を取得"""
        properties: dict[str, list[PropertyValue]] = {}
        now = datetime.now().isoformat()

        try:
            url = (
                f"{PUBCHEM_VIEW}/data/compound/{cid}/JSON"
                f"?heading=Experimental+Properties"
            )
            data = self._get_json(url)
        except Exception as e:
            logger.debug("PUG View failed for CID %d: %s", cid, e)
            return properties

        # PUG View のネスト構造を再帰的にパース
        sections = data.get("Record", {}).get("Section", [])
        for section in sections:
            self._parse_section(section, properties, cid, now, filter_props)

        return properties

    def _parse_section(
        self,
        section: dict,
        properties: dict[str, list[PropertyValue]],
        cid: int,
        now: str,
        filter_props: list[str] | None,
    ) -> None:
        """PUG Viewのセクションを再帰パース"""
        heading = section.get("TOCHeading", "")
        prop_name = HEADING_MAP.get(heading)

        if prop_name and (filter_props is None or prop_name in filter_props):
            # この見出しに対応する物性値を抽出
            infos = section.get("Information", [])
            for info in infos:
                pv = self._extract_property_value(info, prop_name, cid, now)
                if pv is not None:
                    properties.setdefault(prop_name, []).append(pv)
                    break  # 1つ目の有効な値だけ取る

        # 子セクションを再帰
        for child in section.get("Section", []):
            self._parse_section(child, properties, cid, now, filter_props)

    def _extract_property_value(
        self, info: dict, prop_name: str, cid: int, now: str
    ) -> PropertyValue | None:
        """PUG View Information から PropertyValue を抽出"""
        ref_text = info.get("Reference", [""])[0] if info.get("Reference") else ""

        # StringWithMarkup から値を取得
        value_section = info.get("Value", {})
        str_values = value_section.get("StringWithMarkup", [])

        if str_values:
            text = str_values[0].get("String", "")
            value, unit = parse_value_with_unit(text)
            if value is not None:
                # SI単位に変換
                si_value, si_unit = convert_to_si(value, unit, prop_name)
                return PropertyValue(
                    property_name=prop_name,
                    value=si_value,
                    unit=si_unit,
                    source="pubchem",
                    reference=f"PubChem CID:{cid}" + (f" ({ref_text})" if ref_text else ""),
                    confidence="experimental",
                    retrieved_at=now,
                )

        # Number形式
        num_value = value_section.get("Number", [None])
        if num_value and num_value[0] is not None:
            unit = value_section.get("Unit", "")
            si_value, si_unit = convert_to_si(float(num_value[0]), unit, prop_name)
            return PropertyValue(
                property_name=prop_name,
                value=si_value,
                unit=si_unit,
                source="pubchem",
                reference=f"PubChem CID:{cid}" + (f" ({ref_text})" if ref_text else ""),
                confidence="experimental",
                retrieved_at=now,
            )

        return None

    def _get_json(self, url: str, timeout: int = 15) -> dict:
        """HTTP GET（キャッシュ＆レート制限付き）"""
        # キャッシュチェック
        cache_key = hashlib.md5(url.encode()).hexdigest()
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        # レート制限（0.2秒間隔 = 5 req/sec）
        elapsed = time.time() - self._last_request_time
        if elapsed < 0.2:
            time.sleep(0.2 - elapsed)

        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        self._last_request_time = time.time()

        # キャッシュ書き込み
        self._write_cache(cache_key, result)
        return result

    def _read_cache(self, key: str) -> dict | None:
        """ディスクキャッシュ読み込み（TTL: 24h）"""
        cache_file = self._cache_dir / f"{key}.json"
        if not cache_file.exists():
            return None
        # TTLチェック
        import os

        mtime = os.path.getmtime(cache_file)
        age_hours = (time.time() - mtime) / 3600
        if age_hours > CACHE_TTL_HOURS:
            return None
        try:
            with open(cache_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _write_cache(self, key: str, data: dict) -> None:
        """ディスクキャッシュ書き込み"""
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = self._cache_dir / f"{key}.json"
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception as e:
            logger.debug("Cache write failed: %s", e)


def _looks_like_cas(text: str) -> bool:
    """CAS番号っぽいか"""
    return bool(re.match(r"^\d{2,7}-\d{2}-\d$", text.strip()))


def _safe_float(value: Any) -> float | None:
    """安全にfloat変換"""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
