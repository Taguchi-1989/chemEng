"""物性データベースのテスト"""

import tempfile
from pathlib import Path

import pytest

from data import PropertyValue, SubstanceRecord
from data.property_db import PropertyDatabase
from data.units import (
    convert_to_si,
    parse_value_with_unit,
    to_kelvin,
    to_kg_per_m3,
    to_pascal,
)


# --- データモデルテスト ---


class TestPropertyValue:
    def test_to_dict_minimal(self):
        pv = PropertyValue(property_name="boiling_point", value=373.15, unit="K")
        d = pv.to_dict()
        assert d["value"] == 373.15
        assert d["unit"] == "K"
        assert "source" not in d  # 空文字は含まない

    def test_to_dict_full(self):
        pv = PropertyValue(
            property_name="vapor_pressure",
            value=101325.0,
            unit="Pa",
            temperature=373.15,
            source="pubchem",
            reference="CRC Handbook",
            confidence="experimental",
        )
        d = pv.to_dict()
        assert d["temperature"] == 373.15
        assert d["source"] == "pubchem"
        assert d["confidence"] == "experimental"

    def test_from_dict(self):
        d = {"value": 373.15, "unit": "K", "source": "pubchem"}
        pv = PropertyValue.from_dict("boiling_point", d)
        assert pv.property_name == "boiling_point"
        assert pv.value == 373.15
        assert pv.source == "pubchem"

    def test_roundtrip(self):
        pv = PropertyValue(
            property_name="density",
            value=997.0,
            unit="kg/m³",
            temperature=298.15,
            source="thermo",
            confidence="estimated",
        )
        d = pv.to_dict()
        pv2 = PropertyValue.from_dict("density", d)
        assert pv2.value == pv.value
        assert pv2.temperature == pv.temperature
        assert pv2.source == pv.source


class TestSubstanceRecord:
    def test_get_best_property_prefers_experimental(self):
        record = SubstanceRecord(
            name="water",
            properties={
                "boiling_point": [
                    PropertyValue("boiling_point", 373.0, "K", confidence="estimated"),
                    PropertyValue("boiling_point", 373.15, "K", confidence="experimental"),
                ]
            },
        )
        best = record.get_best_property("boiling_point")
        assert best is not None
        assert best.value == 373.15
        assert best.confidence == "experimental"

    def test_get_best_property_missing(self):
        record = SubstanceRecord(name="water")
        assert record.get_best_property("density") is None

    def test_list_properties(self):
        record = SubstanceRecord(
            name="ethanol",
            properties={
                "boiling_point": [PropertyValue("boiling_point", 351.4, "K")],
                "density": [PropertyValue("density", 789.0, "kg/m³")],
            },
        )
        props = record.list_properties()
        assert "boiling_point" in props
        assert "density" in props

    def test_merge_from(self):
        r1 = SubstanceRecord(
            name="water",
            cas="7732-18-5",
            properties={
                "boiling_point": [
                    PropertyValue("boiling_point", 373.15, "K", source="pubchem"),
                ]
            },
            sources_used=["pubchem"],
        )
        r2 = SubstanceRecord(
            name="water",
            formula="H2O",
            properties={
                "boiling_point": [
                    PropertyValue("boiling_point", 373.1, "K", source="thermo"),
                ],
                "density": [
                    PropertyValue("density", 997.0, "kg/m³", source="thermo"),
                ],
            },
            sources_used=["thermo"],
        )
        r1.merge_from(r2)
        assert r1.formula == "H2O"
        assert len(r1.properties["boiling_point"]) == 2
        assert "density" in r1.properties
        assert "thermo" in r1.sources_used

    def test_to_dict_from_dict_roundtrip(self):
        record = SubstanceRecord(
            name="ethanol",
            name_ja="エタノール",
            cas="64-17-5",
            formula="C2H6O",
            molecular_weight=46.07,
            properties={
                "boiling_point": [
                    PropertyValue("boiling_point", 351.4, "K", source="pubchem"),
                ]
            },
            sources_used=["pubchem"],
        )
        d = record.to_dict()
        r2 = SubstanceRecord.from_dict(d)
        assert r2.name == "ethanol"
        assert r2.name_ja == "エタノール"
        assert r2.cas == "64-17-5"
        assert len(r2.properties["boiling_point"]) == 1


# --- 単位変換テスト ---


class TestUnits:
    def test_to_kelvin_from_celsius(self):
        assert to_kelvin(100, "°C") == pytest.approx(373.15)

    def test_to_kelvin_from_fahrenheit(self):
        assert to_kelvin(212, "°F") == pytest.approx(373.15)

    def test_to_kelvin_from_kelvin(self):
        assert to_kelvin(373.15, "K") == 373.15

    def test_to_pascal_from_atm(self):
        assert to_pascal(1, "atm") == pytest.approx(101325.0)

    def test_to_pascal_from_mmhg(self):
        assert to_pascal(760, "mmHg") == pytest.approx(101324.72, rel=1e-3)

    def test_to_kg_per_m3_from_g_cm3(self):
        assert to_kg_per_m3(0.997, "g/cm3") == pytest.approx(997.0)

    def test_convert_to_si_boiling_point(self):
        val, unit = convert_to_si(100, "°C", "boiling_point")
        assert val == pytest.approx(373.15)
        assert unit == "K"

    def test_convert_to_si_unknown_property(self):
        val, unit = convert_to_si(42, "foo", "unknown_prop")
        assert val == 42
        assert unit == "foo"

    def test_parse_value_with_unit(self):
        val, unit = parse_value_with_unit("0.7893 g/cm3")
        assert val == pytest.approx(0.7893)

    def test_parse_value_with_unit_negative(self):
        val, unit = parse_value_with_unit("-33.34 °C")
        assert val == pytest.approx(-33.34)

    def test_parse_value_with_unit_empty(self):
        val, unit = parse_value_with_unit("")
        assert val is None


# --- PropertyDatabase テスト ---


class TestPropertyDatabase:
    def test_empty_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = PropertyDatabase(Path(tmpdir))
            assert db.count() == 0
            assert db.list_all() == []

    def test_add_and_get(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = PropertyDatabase(Path(tmpdir))
            record = SubstanceRecord(
                name="ethanol",
                cas="64-17-5",
                formula="C2H6O",
                molecular_weight=46.07,
                properties={
                    "boiling_point": [
                        PropertyValue("boiling_point", 351.4, "K", source="test"),
                    ]
                },
                sources_used=["test"],
            )
            db.add_or_update(record)
            assert db.count() == 1

            got = db.get("ethanol")
            assert got is not None
            assert got.cas == "64-17-5"

    def test_get_by_cas(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = PropertyDatabase(Path(tmpdir))
            record = SubstanceRecord(name="ethanol", cas="64-17-5")
            db.add_or_update(record)

            got = db.get("64-17-5")
            assert got is not None
            assert got.name == "ethanol"

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db1 = PropertyDatabase(Path(tmpdir))
            db1.add_or_update(SubstanceRecord(name="water", cas="7732-18-5"))
            assert db1.count() == 1

            # 新インスタンスで再読み込み
            db2 = PropertyDatabase(Path(tmpdir))
            assert db2.count() == 1
            assert db2.get("water") is not None

    def test_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = PropertyDatabase(Path(tmpdir))
            db.add_or_update(SubstanceRecord(name="water"))
            assert db.count() == 1
            assert db.delete("water")
            assert db.count() == 0

    def test_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = PropertyDatabase(Path(tmpdir))
            db.add_or_update(SubstanceRecord(
                name="ethanol", name_ja="エタノール", cas="64-17-5",
            ))
            db.add_or_update(SubstanceRecord(name="water", cas="7732-18-5"))

            assert len(db.search("ethanol")) == 1
            assert len(db.search("エタノール")) == 1
            assert len(db.search("64-17-5")) == 1
            assert len(db.search("nonexistent")) == 0

    def test_get_property_value(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = PropertyDatabase(Path(tmpdir))
            record = SubstanceRecord(
                name="water",
                properties={
                    "boiling_point": [
                        PropertyValue("boiling_point", 373.15, "K",
                                      source="pubchem", confidence="experimental"),
                    ]
                },
            )
            db.add_or_update(record)
            pv = db.get_property_value("water", "boiling_point")
            assert pv is not None
            assert pv.value == 373.15
            assert db.get_property_value("water", "density") is None

    def test_merge_on_update(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = PropertyDatabase(Path(tmpdir))
            r1 = SubstanceRecord(
                name="water",
                properties={
                    "boiling_point": [
                        PropertyValue("boiling_point", 373.15, "K", source="pubchem"),
                    ]
                },
                sources_used=["pubchem"],
            )
            db.add_or_update(r1)

            r2 = SubstanceRecord(
                name="water",
                properties={
                    "density": [
                        PropertyValue("density", 997.0, "kg/m³", source="thermo"),
                    ]
                },
                sources_used=["thermo"],
            )
            db.add_or_update(r2)

            record = db.get("water")
            assert record is not None
            assert "boiling_point" in record.properties
            assert "density" in record.properties
            assert "pubchem" in record.sources_used
            assert "thermo" in record.sources_used
