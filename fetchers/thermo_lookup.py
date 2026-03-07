"""
thermo/chemicals ライブラリ データフェッチャー

既にインストール済みの thermo ライブラリを使ってオフラインで物性データを取得する。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from data import PropertyValue, SubstanceRecord

from .base import DataFetcher, FetcherCapability, SearchResult

logger = logging.getLogger("chemeng")

# thermo Chemical属性 → (物性名, 単位, 信頼度)
ATTR_MAP: dict[str, tuple[str, str, str]] = {
    "Tb": ("boiling_point", "K", "experimental"),
    "Tm": ("melting_point", "K", "experimental"),
    "Tc": ("critical_temperature", "K", "experimental"),
    "Pc": ("critical_pressure", "Pa", "experimental"),
    "omega": ("acentric_factor", "-", "experimental"),
    "Hfus": ("heat_of_fusion", "J/mol", "experimental"),
    "Hvap": ("heat_of_vaporization", "J/mol", "estimated"),
    "Psat": ("vapor_pressure", "Pa", "estimated"),
    "rhol": ("liquid_density", "kg/m³", "estimated"),
    "rhog": ("gas_density", "kg/m³", "estimated"),
    "mul": ("liquid_viscosity", "Pa·s", "estimated"),
    "mug": ("gas_viscosity", "Pa·s", "estimated"),
    "Cpl": ("heat_capacity_liquid", "J/(mol·K)", "estimated"),
    "Cpg": ("heat_capacity_gas", "J/(mol·K)", "estimated"),
    "kl": ("thermal_conductivity_liquid", "W/(m·K)", "estimated"),
    "kg": ("thermal_conductivity_gas", "W/(m·K)", "estimated"),
    "sigma": ("surface_tension", "N/m", "estimated"),
}


class ThermoLookupFetcher(DataFetcher):
    """thermo/chemicals ライブラリフェッチャー（オフライン）"""

    @property
    def name(self) -> str:
        return "thermo"

    @property
    def capabilities(self) -> FetcherCapability:
        return FetcherCapability(
            source_name="thermo/chemicals",
            source_url="https://github.com/CalebBell/thermo",
            requires_api_key=False,
            available_properties=[v[0] for v in ATTR_MAP.values()],
            compound_count="30,000+ compounds",
            rate_limit="(offline)",
            supports_japanese=False,
        )

    def is_available(self) -> bool:
        try:
            from thermo import Chemical  # noqa: F401

            return True
        except ImportError:
            return False

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """thermo/chemicals で物質検索"""
        results: list[SearchResult] = []
        try:
            from thermo import Chemical

            chem = Chemical(query)
            results.append(
                SearchResult(
                    name=chem.name,
                    cas=chem.CAS,
                    formula=chem.formula,
                    molecular_weight=chem.MW,
                    source="thermo",
                    source_id=chem.CAS,
                    available_properties=[v[0] for v in ATTR_MAP.values()],
                )
            )
        except Exception as e:
            logger.debug("thermo search failed for %s: %s", query, e)

        return results

    def fetch_properties(
        self,
        identifier: str,
        properties: list[str] | None = None,
    ) -> SubstanceRecord:
        """thermoライブラリから物性データを取得"""
        from thermo import Chemical

        chem = Chemical(identifier)
        now = datetime.now().isoformat()

        prop_data: dict[str, list[PropertyValue]] = {}

        for attr, (prop_name, unit, confidence) in ATTR_MAP.items():
            if properties and prop_name not in properties:
                continue

            value = _safe_getattr(chem, attr)
            if value is not None:
                pv = PropertyValue(
                    property_name=prop_name,
                    value=float(value),
                    unit=unit,
                    source="thermo",
                    reference="thermo/chemicals library",
                    confidence=confidence,
                    retrieved_at=now,
                )
                # 温度・圧力依存の物性は条件を付与
                if confidence == "estimated":
                    pv.temperature = chem.T
                    pv.pressure = chem.P

                prop_data.setdefault(prop_name, []).append(pv)

        return SubstanceRecord(
            name=chem.name,
            cas=chem.CAS,
            formula=chem.formula,
            molecular_weight=chem.MW,
            smiles=getattr(chem, "smiles", ""),
            inchi=getattr(chem, "InChI", ""),
            properties=prop_data,
            added_at=now,
            updated_at=now,
            sources_used=["thermo"],
        )


def _safe_getattr(obj: Any, attr: str) -> float | None:
    """例外を飲み込んで属性値を取得"""
    try:
        val = getattr(obj, attr, None)
        if val is not None and not (isinstance(val, float) and (val != val)):  # NaN check
            return float(val)
    except Exception:
        pass
    return None
