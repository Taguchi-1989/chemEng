import pytest
from chemeng.__main__ import _default_port, _parse_port
from pydantic import ValidationError


class TestMainPortParsing:
    def test_default_port_uses_env(self, monkeypatch):
        monkeypatch.setenv("PORT", "9100")
        assert _default_port() == 9100

    def test_default_port(self, monkeypatch):
        monkeypatch.delenv("PORT", raising=False)
        assert _default_port() == 8000

    def test_default_port_without_args_uses_default(self, monkeypatch):
        monkeypatch.delenv("PORT", raising=False)
        assert _parse_port(["python", "-m", "chemeng", "--api"]) == 8000

    def test_custom_port(self):
        assert _parse_port(["python", "-m", "chemeng", "--api", "--port", "9000"]) == 9000

    def test_port_requires_value(self):
        with pytest.raises(ValueError):
            _parse_port(["python", "-m", "chemeng", "--api", "--port"])

    def test_port_must_be_integer(self):
        with pytest.raises(ValueError):
            _parse_port(["python", "-m", "chemeng", "--api", "--port", "abc"])

    def test_port_must_be_in_range(self):
        with pytest.raises(ValueError):
            _parse_port(["python", "-m", "chemeng", "--api", "--port", "70000"])

    def test_invalid_env_port(self, monkeypatch):
        monkeypatch.setenv("PORT", "abc")
        with pytest.raises(ValueError):
            _default_port()


class TestServerDefaults:
    def test_default_host_uses_env(self, monkeypatch):
        from server import _default_host

        monkeypatch.setenv("HOST", "127.0.0.1")
        assert _default_host() == "127.0.0.1"

    def test_default_port_uses_env(self, monkeypatch):
        from server import _default_port

        monkeypatch.setenv("PORT", "9200")
        assert _default_port() == 9200


class TestAdditionalApiValidation:
    def test_property_request_rejects_blank_substance(self):
        from interface.api import PropertyRequest

        with pytest.raises(ValidationError):
            PropertyRequest(substance="   ", property="vapor_pressure")

    def test_equilibrium_request_requires_multiple_substances(self):
        from interface.api import EquilibriumRequest

        with pytest.raises(ValidationError):
            EquilibriumRequest(
                substances=["water"],
                composition={"water": 1.0},
            )

    def test_equilibrium_request_rejects_invalid_composition_sum(self):
        from interface.api import EquilibriumRequest

        with pytest.raises(ValidationError):
            EquilibriumRequest(
                substances=["ethanol", "water"],
                composition={"ethanol": 0.2, "water": 0.2},
            )
