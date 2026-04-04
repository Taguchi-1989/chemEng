from __future__ import annotations

from skills.templates.heat_balance import execute


class StubEngine:
    def __init__(self, values: dict[tuple[str, str], float], failures: set[tuple[str, str]] | None = None):
        self.values = values
        self.failures = failures or set()

    def get_property(self, substance: str, property_name: str, conditions: dict):
        key = (substance, property_name)
        if key in self.failures:
            raise RuntimeError(f"forced failure: {key}")
        if key not in self.values:
            raise RuntimeError(f"missing property: {key}")
        return self.values[key]


def test_heat_balance_liquid_to_vapor():
    engine = StubEngine(
        {
            ("water", "boiling_point"): 373.15,
            ("water", "heat_of_vaporization"): 40000.0,
            ("water", "heat_capacity_liquid"): 75.0,
            ("water", "heat_capacity_gas"): 35.0,
        }
    )
    result = execute(
        {
            "substance": "water",
            "flow_rate": 2.0,
            "inlet_temperature": 300.0,
            "outlet_temperature": 400.0,
            "pressure": 101325.0,
            "phase_change": True,
        },
        engine=engine,
    )

    assert result["success"] is True
    assert result["outputs"]["phase_info"]["inlet_phase"] == "liquid"
    assert result["outputs"]["phase_info"]["outlet_phase"] == "vapor"
    assert result["outputs"]["latent_heat"] == 80.0
    assert result["outputs"]["sensible_heat"] > 0


def test_heat_balance_vapor_to_liquid():
    engine = StubEngine(
        {
            ("water", "boiling_point"): 373.15,
            ("water", "heat_of_vaporization"): 40000.0,
            ("water", "heat_capacity_liquid"): 75.0,
            ("water", "heat_capacity_gas"): 35.0,
        }
    )
    result = execute(
        {
            "substance": "water",
            "flow_rate": 2.0,
            "inlet_temperature": 410.0,
            "outlet_temperature": 320.0,
            "pressure": 101325.0,
            "phase_change": True,
        },
        engine=engine,
    )

    assert result["success"] is True
    assert result["outputs"]["phase_info"]["inlet_phase"] == "vapor"
    assert result["outputs"]["phase_info"]["outlet_phase"] == "liquid"
    assert result["outputs"]["latent_heat"] == -80.0


def test_heat_balance_single_phase_uses_liquid_cp():
    engine = StubEngine(
        {
            ("water", "boiling_point"): 373.15,
            ("water", "heat_capacity_liquid"): 80.0,
        }
    )
    result = execute(
        {
            "substance": "water",
            "flow_rate": 1.5,
            "inlet_temperature": 300.0,
            "outlet_temperature": 330.0,
            "phase_change": True,
        },
        engine=engine,
    )

    assert result["success"] is True
    assert result["outputs"]["phase_info"]["has_phase_change"] is False
    assert result["outputs"]["latent_heat"] == 0.0
    assert result["outputs"]["sensible_heat"] == 3.6


def test_heat_balance_boiling_point_failure_disables_phase_change():
    engine = StubEngine({}, failures={("water", "boiling_point")})
    result = execute(
        {
            "substance": "water",
            "flow_rate": 2.0,
            "inlet_temperature": 300.0,
            "outlet_temperature": 330.0,
            "phase_change": True,
        },
        engine=engine,
    )

    assert result["success"] is True
    assert "Could not get boiling point, assuming no phase change" in result["warnings"]
    assert result["outputs"]["phase_info"]["boiling_point"] is None


def test_heat_balance_cp_fallback_and_efficiency_warning():
    engine = StubEngine(
        {
            ("water", "boiling_point"): 373.15,
        },
        failures={
            ("water", "heat_capacity_liquid"),
            ("water", "heat_capacity_gas"),
        },
    )
    result = execute(
        {
            "substance": "water",
            "flow_rate": 1.0,
            "inlet_temperature": 300.0,
            "outlet_temperature": 320.0,
            "phase_change": True,
            "efficiency": 0.0,
        },
        engine=engine,
    )

    assert result["success"] is True
    assert "Using default liquid Cp = 75.0 J/(mol*K)" in result["warnings"]
    assert "Efficiency is zero or negative, using ideal duty" in result["warnings"]
    assert result["outputs"]["actual_heat_duty"] == result["outputs"]["total_heat_duty"]
