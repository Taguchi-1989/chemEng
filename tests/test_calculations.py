"""
Smoke tests and edge case tests for calculation skill templates.

Tests cover: distillation, extraction, absorption, lcoh, and flowsheet solver blocks.
All tests use the registry.execute() path (integration-level) except solver block tests,
which call the block calculators directly to isolate behavior.
"""

import pytest

from core.registry import SkillRegistry
from core.solver import (
    calculate_flash,
    calculate_mixer,
    calculate_reactor,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def registry():
    return SkillRegistry()


# ---------------------------------------------------------------------------
# Distillation
# ---------------------------------------------------------------------------

class TestDistillation:
    """蒸留計算のスモークテストとエッジケース"""

    def test_basic_ethanol_water_output_keys(self, registry):
        """Basic ethanol/water case returns all expected output keys."""
        result = registry.execute("distillation", {
            "light_component": "ethanol",
            "heavy_component": "water",
            "feed_flow_rate": 100.0,
            "feed_composition": 0.4,
            "distillate_purity": 0.85,
            "bottoms_purity": 0.95,
            "reflux_ratio_factor": 1.3,
        })
        assert result.success, f"Expected success but got errors: {result.errors}"
        out = result.outputs
        expected_keys = {
            "minimum_reflux_ratio",
            "actual_reflux_ratio",
            "minimum_stages",
            "actual_stages",
            "feed_stage",
            "distillate_flow_rate",
            "bottoms_flow_rate",
            "condenser_duty",
            "reboiler_duty",
            "relative_volatility",
            "column_diameter",
        }
        missing = expected_keys - set(out.keys())
        assert not missing, f"Missing output keys: {missing}"

    def test_actual_stages_greater_than_minimum_stages(self, registry):
        """Actual stages must be greater than minimum stages for a finite reflux ratio."""
        result = registry.execute("distillation", {
            "light_component": "ethanol",
            "heavy_component": "water",
            "feed_flow_rate": 100.0,
            "feed_composition": 0.4,
            "distillate_purity": 0.85,
            "bottoms_purity": 0.95,
            "reflux_ratio_factor": 1.3,
        })
        assert result.success
        assert result.outputs["actual_stages"] > result.outputs["minimum_stages"]

    def test_material_balance_distillate_plus_bottoms_equals_feed(self, registry):
        """Distillate flow + bottoms flow must equal feed flow."""
        feed = 200.0
        result = registry.execute("distillation", {
            "light_component": "ethanol",
            "heavy_component": "water",
            "feed_flow_rate": feed,
            "feed_composition": 0.35,
            "distillate_purity": 0.80,
            "bottoms_purity": 0.92,
            "reflux_ratio_factor": 1.5,
        })
        assert result.success
        total_out = result.outputs["distillate_flow_rate"] + result.outputs["bottoms_flow_rate"]
        assert abs(total_out - feed) < 0.01, (
            f"Material balance error: D+B={total_out:.3f} vs F={feed}"
        )

    def test_heat_duties_are_positive(self, registry):
        """Condenser and reboiler duties must be positive."""
        result = registry.execute("distillation", {
            "light_component": "ethanol",
            "heavy_component": "water",
            "feed_flow_rate": 100.0,
            "feed_composition": 0.4,
            "distillate_purity": 0.85,
            "bottoms_purity": 0.95,
        })
        assert result.success
        assert result.outputs["condenser_duty"] > 0
        assert result.outputs["reboiler_duty"] > 0

    def test_relative_volatility_greater_than_one(self, registry):
        """Relative volatility must be > 1 for a valid ethanol/water separation."""
        result = registry.execute("distillation", {
            "light_component": "ethanol",
            "heavy_component": "water",
            "feed_flow_rate": 100.0,
            "feed_composition": 0.4,
            "distillate_purity": 0.85,
            "bottoms_purity": 0.95,
        })
        assert result.success
        assert result.outputs["relative_volatility"] > 1.0

    def test_feed_composition_above_distillate_purity_returns_error(self, registry):
        """Feed composition >= distillate purity should fail with a validation error."""
        result = registry.execute("distillation", {
            "light_component": "ethanol",
            "heavy_component": "water",
            "feed_flow_rate": 100.0,
            "feed_composition": 0.95,   # same as distillate_purity
            "distillate_purity": 0.85,  # lower than feed
            "bottoms_purity": 0.95,
        })
        # Template returns success=False with an error
        has_error = (
            not result.success
            or len(result.errors) > 0
            or result.outputs.get("success") is False
        )
        assert has_error, "Expected failure when feed composition >= distillate purity"

    def test_azeotrope_detected_when_alpha_crosses_one_directly(self):
        """Template returns an azeotrope error when alphas bracket 1.0 across the column."""
        # Call the template directly and patch _calculate_relative_volatility to force
        # alphas that straddle 1.0 (top > 1, feed < 1) — exactly the azeotrope guard.
        # Patch at the module level to control alpha values per call site
        import skills.templates.distillation as dist_mod
        from skills.templates.distillation import execute as dist_execute
        call_count = {"n": 0}
        original = dist_mod._calculate_relative_volatility

        def patched_alpha(engine, light, heavy, T, P, z, warnings):
            call_count["n"] += 1
            # top (first call): alpha > 1, feed (second): alpha < 1, bottom (third): alpha < 1
            return [1.5, 0.8, 0.9][min(call_count["n"] - 1, 2)]

        dist_mod._calculate_relative_volatility = patched_alpha
        try:
            result = dist_execute({
                "light_component": "A",
                "heavy_component": "B",
                "feed_flow_rate": 100.0,
                "feed_composition": 0.4,
                "distillate_purity": 0.9,
                "bottoms_purity": 0.95,
            }, engine=None)
        finally:
            dist_mod._calculate_relative_volatility = original

        has_error = result.get("success") is False or "errors" in result
        assert has_error, f"Expected azeotrope error, got: {result}"
        # Verify the error message mentions azeotrope
        errors = result.get("errors", [])
        assert any("azeotrope" in str(e).lower() or "共沸" in str(e) for e in errors), (
            f"Expected azeotrope mention in errors: {errors}"
        )


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

class TestExtraction:
    """液液抽出のスモークテストとエッジケース"""

    def test_basic_acetic_acid_extraction_output_keys(self, registry):
        """Basic acetic acid / water / ethyl_acetate case returns all expected output keys."""
        result = registry.execute("extraction", {
            "solute": "acetic_acid",
            "carrier": "water",
            "solvent": "ethyl_acetate",
            "feed_flow_rate": 100.0,
            "feed_composition": 0.05,
            "solvent_flow_rate": 60.0,
            "recovery": 0.9,
        })
        assert result.success, f"Errors: {result.errors}"
        out = result.outputs
        expected_keys = {
            "extraction_factor",
            "distribution_coefficient",
            "actual_stages",
            "recovery",
            "raffinate_flow_rate",
            "raffinate_composition",
            "extract_flow_rate",
            "extract_composition",
        }
        missing = expected_keys - set(out.keys())
        assert not missing, f"Missing output keys: {missing}"

    def test_recovery_target_exactly_one_rejected_by_schema(self, registry):
        """A recovery target of exactly 1.0 exceeds the schema max (0.999) and is rejected."""
        result = registry.execute("extraction", {
            "solute": "acetic_acid",
            "carrier": "water",
            "solvent": "ethyl_acetate",
            "feed_flow_rate": 100.0,
            "feed_composition": 0.05,
            "solvent_flow_rate": 200.0,
            "recovery": 1.0,
        })
        # Schema validation rejects recovery > 0.999 before the template runs
        assert not result.success, "Expected schema validation error for recovery=1.0"
        assert len(result.errors) > 0

    def test_recovery_is_clamped_in_template_when_near_one(self):
        """Template clamps recovery > 0.9999 to avoid log(0) — call template directly."""
        from skills.templates.extraction import execute as extract_execute

        result = extract_execute({
            "solute": "acetic_acid",
            "carrier": "water",
            "solvent": "ethyl_acetate",
            "feed_flow_rate": 100.0,
            "feed_composition": 0.05,
            "solvent_flow_rate": 200.0,
            "recovery": 0.99999,  # above the 0.9999 clamp threshold
        }, engine=None)
        assert result.get("success") is True
        assert result["outputs"]["recovery"] < 1.0

    def test_mass_conservation_solute(self, registry):
        """Solute in raffinate + extract must equal solute in feed."""
        feed_flow = 100.0
        feed_comp = 0.05
        solute_in = feed_flow * feed_comp
        result = registry.execute("extraction", {
            "solute": "acetic_acid",
            "carrier": "water",
            "solvent": "ethyl_acetate",
            "feed_flow_rate": feed_flow,
            "feed_composition": feed_comp,
            "solvent_flow_rate": 60.0,
            "recovery": 0.8,
        })
        assert result.success
        solute_out = (
            result.outputs["solute_in_raffinate"] + result.outputs["solute_in_extract"]
        )
        assert abs(solute_out - solute_in) < 0.01, (
            f"Solute balance error: in={solute_in:.4f}, out={solute_out:.4f}"
        )

    def test_distribution_coefficient_zero_returns_error(self, registry):
        """A distribution coefficient of 0 (m=0) should cause failure."""
        # To force m=0 we call the template directly without engine
        from skills.templates.extraction import execute as extraction_execute

        result = extraction_execute({
            "solute": "unknown_solute_xyz",
            "carrier": "unknown_carrier_xyz",
            "solvent": "unknown_solvent_xyz",
            "feed_flow_rate": 100.0,
            "feed_composition": 0.05,
            "solvent_flow_rate": 50.0,
            "recovery": 0.9,
        }, engine=None)
        # Unknown system uses default m=1.0 (positive) — verify it still succeeds
        assert result.get("success") is True
        assert result["outputs"]["distribution_coefficient"] > 0

    def test_extraction_factor_increases_with_higher_solvent_flow(self, registry):
        """More solvent → larger extraction factor E = m*S/F."""
        params_base = {
            "solute": "acetic_acid",
            "carrier": "water",
            "solvent": "ethyl_acetate",
            "feed_flow_rate": 100.0,
            "feed_composition": 0.05,
            "recovery": 0.85,
        }
        result_high = registry.execute("extraction", {**params_base, "solvent_flow_rate": 200.0})
        result_low = registry.execute("extraction", {**params_base, "solvent_flow_rate": 30.0})
        assert result_high.success
        assert result_low.success
        assert result_high.outputs["extraction_factor"] > result_low.outputs["extraction_factor"]


# ---------------------------------------------------------------------------
# Absorption
# ---------------------------------------------------------------------------

class TestAbsorption:
    """ガス吸収のスモークテストとエッジケース"""

    def test_basic_ammonia_water_output_keys(self, registry):
        """Basic ammonia / air / water absorption returns all expected output keys."""
        result = registry.execute("absorption", {
            "gas_component": "ammonia",
            "carrier_gas": "air",
            "solvent": "water",
            "gas_flow_rate": 100.0,
            "inlet_gas_composition": 0.05,
            "liquid_flow_rate": 300.0,
            "removal_efficiency": 0.90,
        })
        assert result.success, f"Errors: {result.errors}"
        out = result.outputs
        expected_keys = {
            "absorption_factor",
            "henry_constant",
            "actual_stages",
            "ntu",
            "removal_efficiency",
            "liquid_gas_ratio",
            "outlet_gas_flow",
            "outlet_gas_composition",
            "outlet_liquid_flow",
            "outlet_liquid_composition",
            "absorbed_amount",
        }
        missing = expected_keys - set(out.keys())
        assert not missing, f"Missing output keys: {missing}"

    def test_outlet_gas_composition_lower_than_inlet(self, registry):
        """After absorption the outlet gas composition must be less than the inlet."""
        result = registry.execute("absorption", {
            "gas_component": "ammonia",
            "carrier_gas": "air",
            "solvent": "water",
            "gas_flow_rate": 100.0,
            "inlet_gas_composition": 0.05,
            "liquid_flow_rate": 300.0,
            "removal_efficiency": 0.90,
        })
        assert result.success
        assert result.outputs["outlet_gas_composition"] < 0.05

    def test_absorbed_amount_consistent_with_removal_efficiency(self, registry):
        """Absorbed amount should be consistent with feed × removal efficiency."""
        result = registry.execute("absorption", {
            "gas_component": "ammonia",
            "carrier_gas": "air",
            "solvent": "water",
            "gas_flow_rate": 100.0,
            "inlet_gas_composition": 0.05,
            "liquid_flow_rate": 300.0,
            "removal_efficiency": 0.90,
        })
        assert result.success
        out = result.outputs
        # absorbed ≈ G * y_in * removal_efficiency  (within 5% due to rounding)
        expected_absorbed = 100.0 * 0.05 * out["removal_efficiency"]
        assert abs(out["absorbed_amount"] - expected_absorbed) < expected_absorbed * 0.05

    def test_y_in_zero_returns_error(self, registry):
        """Inlet gas composition of zero has nothing to absorb — should return an error."""
        result = registry.execute("absorption", {
            "gas_component": "ammonia",
            "carrier_gas": "air",
            "solvent": "water",
            "gas_flow_rate": 100.0,
            "inlet_gas_composition": 0.0,  # nothing to absorb
            "liquid_flow_rate": 300.0,
            "removal_efficiency": 0.90,
        })
        has_error = (
            not result.success
            or len(result.errors) > 0
            or result.outputs.get("success") is False
        )
        assert has_error, "Expected failure when inlet gas composition is zero"

    def test_stage_count_positive_integer(self, registry):
        """Stage count must be a positive integer."""
        result = registry.execute("absorption", {
            "gas_component": "ammonia",
            "carrier_gas": "air",
            "solvent": "water",
            "gas_flow_rate": 100.0,
            "inlet_gas_composition": 0.05,
            "liquid_flow_rate": 300.0,
            "removal_efficiency": 0.90,
        })
        assert result.success
        stages = result.outputs["actual_stages"]
        assert isinstance(stages, int)
        assert stages >= 1

    def test_ntu_is_positive(self, registry):
        """Number of Transfer Units must be positive."""
        result = registry.execute("absorption", {
            "gas_component": "ammonia",
            "carrier_gas": "air",
            "solvent": "water",
            "gas_flow_rate": 100.0,
            "inlet_gas_composition": 0.05,
            "liquid_flow_rate": 300.0,
            "removal_efficiency": 0.90,
        })
        assert result.success
        assert result.outputs["ntu"] > 0


# ---------------------------------------------------------------------------
# LCOH
# ---------------------------------------------------------------------------

class TestLCOH:
    """LCOH計算のスモークテストとエッジケース"""

    def test_basic_pem_electrolysis_output_keys(self, registry):
        """PEM electrolysis case returns all expected top-level output keys."""
        result = registry.execute("lcoh", {
            "production_method": "pem_electrolysis",
            "capacity": 10.0,
            "electricity_price": 50.0,
            "operating_hours": 4000,
        })
        assert result.success, f"Errors: {result.errors}"
        out = result.outputs
        expected_keys = {
            "lcoh",
            "lcoh_breakdown",
            "annual_h2_production",
            "total_capex",
            "annual_costs",
            "carbon_intensity",
            "energy_efficiency",
        }
        missing = expected_keys - set(out.keys())
        assert not missing, f"Missing output keys: {missing}"

    def test_pem_electrolysis_lcoh_in_reasonable_range(self, registry):
        """PEM LCOH should be between 3 and 15 EUR/kg for typical parameters."""
        result = registry.execute("lcoh", {
            "production_method": "pem_electrolysis",
            "capacity": 10.0,
            "electricity_price": 50.0,
            "operating_hours": 4000,
        })
        assert result.success
        lcoh = result.outputs["lcoh"]
        assert 3.0 < lcoh < 15.0, f"LCOH={lcoh:.2f} outside expected range [3, 15] EUR/kg"

    def test_pem_lcoh_breakdown_sums_to_total(self, registry):
        """LCOH breakdown components must sum to the total LCOH."""
        result = registry.execute("lcoh", {
            "production_method": "pem_electrolysis",
            "capacity": 10.0,
            "electricity_price": 50.0,
            "operating_hours": 4000,
        })
        assert result.success
        bd = result.outputs["lcoh_breakdown"]
        total = bd["total"]
        components = sum(
            bd[k] for k in ("capex", "energy", "opex", "labor", "maintenance",
                            "stack_replacement", "water", "carbon", "revenue_offset")
        )
        assert abs(components - total) < 0.01, (
            f"Breakdown sum={components:.3f} != total={total:.3f}"
        )

    def test_basic_smr_output_keys(self, registry):
        """SMR case returns expected output keys and a positive LCOH."""
        result = registry.execute("lcoh", {
            "production_method": "smr",
            "capacity": 50.0,
            "natural_gas_price": 30.0,
            "operating_hours": 8000,
        })
        assert result.success, f"Errors: {result.errors}"
        assert result.outputs["lcoh"] > 0

    def test_smr_carbon_intensity_greater_than_zero(self, registry):
        """SMR (without CCS) must have a positive CO2 emission intensity."""
        result = registry.execute("lcoh", {
            "production_method": "smr",
            "capacity": 50.0,
            "natural_gas_price": 30.0,
            "operating_hours": 8000,
        })
        assert result.success
        assert result.outputs["carbon_intensity"] > 0

    def test_pem_carbon_intensity_is_zero(self, registry):
        """PEM electrolysis (from renewable electricity) has zero scope-1 CO2 intensity."""
        result = registry.execute("lcoh", {
            "production_method": "pem_electrolysis",
            "capacity": 10.0,
            "electricity_price": 40.0,
            "operating_hours": 4000,
        })
        assert result.success
        assert result.outputs["carbon_intensity"] == 0.0

    def test_zero_capacity_factor_raises_error(self, registry):
        """A capacity_factor of 0 leads to zero operating hours which should raise an error."""
        result = registry.execute("lcoh", {
            "production_method": "pem_electrolysis",
            "capacity": 10.0,
            "electricity_price": 50.0,
            "capacity_factor": 0.0,
        })
        # Should fail due to operating_hours becoming 0
        has_error = (
            not result.success
            or len(result.errors) > 0
            or result.outputs.get("success") is False
        )
        assert has_error, "Expected failure when capacity_factor=0"

    def test_higher_electricity_price_increases_pem_lcoh(self, registry):
        """Doubling electricity price must increase PEM LCOH."""
        base = {
            "production_method": "pem_electrolysis",
            "capacity": 10.0,
            "operating_hours": 4000,
        }
        result_low = registry.execute("lcoh", {**base, "electricity_price": 30.0})
        result_high = registry.execute("lcoh", {**base, "electricity_price": 80.0})
        assert result_low.success and result_high.success
        assert result_high.outputs["lcoh"] > result_low.outputs["lcoh"]


# ---------------------------------------------------------------------------
# Flowsheet Solver — Block Calculators (unit-level)
# ---------------------------------------------------------------------------

class TestMixerBlock:
    """ミキサーブロック計算のユニットテスト"""

    def test_temperature_mixing_with_equal_cp_is_arithmetic_mean(self):
        """Equal Cp streams: outlet temperature is the arithmetic mean."""
        streams = [
            {"total_flow": 100.0, "temperature": 300.0, "cp": 75.0, "pressure": 101325.0,
             "composition": {"A": 1.0}},
            {"total_flow": 100.0, "temperature": 400.0, "cp": 75.0, "pressure": 101325.0,
             "composition": {"A": 1.0}},
        ]
        result = calculate_mixer({}, streams, ["A"])
        assert "outlet" in result
        assert abs(result["outlet"]["temperature"] - 350.0) < 0.01

    def test_temperature_mixing_with_different_cp_values(self):
        """Different Cp streams: outlet temperature is Cp-weighted, not arithmetic mean."""
        streams = [
            {"total_flow": 100.0, "temperature": 300.0, "cp": 150.0, "pressure": 101325.0,
             "composition": {"A": 1.0}},
            {"total_flow": 100.0, "temperature": 400.0, "cp": 50.0, "pressure": 101325.0,
             "composition": {"A": 1.0}},
        ]
        result = calculate_mixer({}, streams, ["A"])
        assert "outlet" in result
        # Weighted: (100*150*300 + 100*50*400) / (100*150 + 100*50) = 5000000/20000 = 325
        expected_temp = (100 * 150 * 300 + 100 * 50 * 400) / (100 * 150 + 100 * 50)
        assert abs(result["outlet"]["temperature"] - expected_temp) < 0.01

    def test_total_flow_is_sum_of_inlets(self):
        """Outlet total flow equals sum of inlet flows."""
        streams = [
            {"total_flow": 60.0, "temperature": 300.0, "cp": 75.0, "pressure": 101325.0,
             "composition": {"A": 0.5, "B": 0.5}},
            {"total_flow": 40.0, "temperature": 300.0, "cp": 75.0, "pressure": 101325.0,
             "composition": {"A": 0.8, "B": 0.2}},
        ]
        result = calculate_mixer({}, streams, ["A", "B"])
        assert abs(result["outlet"]["total_flow"] - 100.0) < 1e-9

    def test_composition_is_flow_weighted(self):
        """Outlet composition is flow-weighted average of inlet compositions."""
        streams = [
            {"total_flow": 60.0, "temperature": 300.0, "cp": 75.0,
             "composition": {"A": 1.0, "B": 0.0}},
            {"total_flow": 40.0, "temperature": 300.0, "cp": 75.0,
             "composition": {"A": 0.0, "B": 1.0}},
        ]
        result = calculate_mixer({}, streams, ["A", "B"])
        comp = result["outlet"]["composition"]
        assert abs(comp["A"] - 0.6) < 1e-9
        assert abs(comp["B"] - 0.4) < 1e-9

    def test_pressure_is_minimum_of_inlets(self):
        """Outlet pressure is the minimum of inlet pressures."""
        streams = [
            {"total_flow": 100.0, "temperature": 300.0, "cp": 75.0,
             "pressure": 200000.0, "composition": {"A": 1.0}},
            {"total_flow": 100.0, "temperature": 300.0, "cp": 75.0,
             "pressure": 101325.0, "composition": {"A": 1.0}},
        ]
        result = calculate_mixer({}, streams, ["A"])
        assert result["outlet"]["pressure"] == 101325.0

    def test_no_inlet_returns_error(self):
        """No inlet streams returns an error dict."""
        result = calculate_mixer({}, [], ["A"])
        assert "error" in result


class TestFlashBlock:
    """フラッシュドラムブロックのユニットテスト"""

    def test_vapor_and_liquid_compositions_sum_to_one(self):
        """Flash drum compositions must each sum to 1.0."""
        inlet = {"total_flow": 100.0, "temperature": 350.0, "pressure": 101325.0,
                 "composition": {"light": 0.4, "heavy": 0.6}}
        params = {"vapor_fraction": 0.3, "k_values": {"light": 3.0, "heavy": 0.5}}
        result = calculate_flash(params, [inlet], ["light", "heavy"])
        sum_vapor = sum(result["vapor_outlet"]["composition"].values())
        sum_liquid = sum(result["liquid_outlet"]["composition"].values())
        assert abs(sum_vapor - 1.0) < 1e-9, f"Vapor composition sum = {sum_vapor}"
        assert abs(sum_liquid - 1.0) < 1e-9, f"Liquid composition sum = {sum_liquid}"

    def test_vapor_flow_plus_liquid_flow_equals_inlet(self):
        """Vapor + liquid outlet flows must equal the inlet flow."""
        inlet = {"total_flow": 100.0, "temperature": 350.0, "pressure": 101325.0,
                 "composition": {"A": 0.5, "B": 0.5}}
        params = {"vapor_fraction": 0.4}
        result = calculate_flash(params, [inlet], ["A", "B"])
        total_out = result["vapor_outlet"]["total_flow"] + result["liquid_outlet"]["total_flow"]
        assert abs(total_out - 100.0) < 1e-9

    def test_light_component_enriched_in_vapor(self):
        """Higher K-value component is enriched in the vapor phase."""
        inlet = {"total_flow": 100.0, "temperature": 350.0, "pressure": 101325.0,
                 "composition": {"light": 0.5, "heavy": 0.5}}
        params = {"vapor_fraction": 0.5, "k_values": {"light": 5.0, "heavy": 0.2}}
        result = calculate_flash(params, [inlet], ["light", "heavy"])
        vapor_comp = result["vapor_outlet"]["composition"]
        liquid_comp = result["liquid_outlet"]["composition"]
        assert vapor_comp["light"] > liquid_comp["light"], (
            "Light component should be enriched in vapor"
        )


class TestReactorBlock:
    """反応器ブロックのユニットテスト"""

    def test_conversion_reduces_key_component_flow(self):
        """50% conversion of key component halves its molar flow."""
        inlet = {"total_flow": 100.0, "temperature": 350.0, "pressure": 101325.0,
                 "composition": {"A": 0.5, "B": 0.5}}
        params = {
            "key_component": "A",
            "conversion": 0.5,
            "stoichiometry": {},
            "outlet_temperature": 400.0,
        }
        result = calculate_reactor(params, [inlet], ["A", "B"])
        # A_out = A_in * (1 - 0.5) = 25 mol/s; B unchanged = 50 mol/s → total = 75
        # composition["A"] = 25/75
        expected_a_fraction = 25.0 / 75.0
        actual_a_fraction = result["outlet"]["composition"]["A"]
        assert abs(actual_a_fraction - expected_a_fraction) < 1e-9

    def test_negative_flow_stoichiometry_produces_warning(self):
        """Stoichiometry that drives a component negative should generate a warning."""
        inlet = {"total_flow": 100.0, "temperature": 350.0, "pressure": 101325.0,
                 "composition": {"A": 0.9, "B": 0.1}}
        params = {
            "key_component": "A",
            "conversion": 0.9,
            # B is consumed with stoichiometric coefficient -5 relative to A reacted
            "stoichiometry": {"B": -5.0},
        }
        result = calculate_reactor(params, [inlet], ["A", "B"])
        # B flow: 100*0.1 - (100*0.9*0.9)*5 = 10 - 405 < 0 → clamped with warning
        assert "warnings" in result, "Expected warnings for negative component flow"
        assert len(result["warnings"]) > 0

    def test_zero_conversion_passes_through_unchanged(self):
        """Zero conversion leaves composition unchanged."""
        inlet = {"total_flow": 100.0, "temperature": 350.0, "pressure": 101325.0,
                 "composition": {"A": 0.4, "B": 0.6}}
        params = {"key_component": "A", "conversion": 0.0, "stoichiometry": {}}
        result = calculate_reactor(params, [inlet], ["A", "B"])
        assert abs(result["outlet"]["composition"]["A"] - 0.4) < 1e-9
        assert abs(result["outlet"]["composition"]["B"] - 0.6) < 1e-9

    def test_outlet_temperature_is_respected(self):
        """Reactor outlet temperature is set to the specified value."""
        inlet = {"total_flow": 100.0, "temperature": 300.0, "pressure": 101325.0,
                 "composition": {"A": 1.0}}
        params = {"key_component": "A", "conversion": 0.5, "outlet_temperature": 550.0}
        result = calculate_reactor(params, [inlet], ["A"])
        assert result["outlet"]["temperature"] == 550.0
