"""Tests for constants module."""

from chuk_mcp_tides.constants import (
    DATUM_NAMES,
    PRINCIPAL_CONSTITUENTS,
    PROVIDER_DEFAULT_DATUMS,
    PROVIDER_INFO,
    SLR_SCENARIOS,
    Datum,
    ServerConfig,
    TideProvider,
)


def test_server_config():
    assert ServerConfig.NAME.value == "chuk-mcp-tides"
    assert ServerConfig.VERSION.value == "0.4.0"


def test_all_providers_have_info():
    for provider in TideProvider:
        assert provider in PROVIDER_INFO


def test_all_providers_have_default_datum():
    for provider in TideProvider:
        assert provider in PROVIDER_DEFAULT_DATUMS


def test_all_datums_have_names():
    for datum in Datum:
        assert datum in DATUM_NAMES


def test_slr_scenarios_have_rates():
    for name, scenario in SLR_SCENARIOS.items():
        assert "rate_mm_yr" in scenario
        assert "source" in scenario
        assert scenario["rate_mm_yr"] > 0


def test_principal_constituents():
    assert "M2" in PRINCIPAL_CONSTITUENTS
    assert "S2" in PRINCIPAL_CONSTITUENTS
    assert PRINCIPAL_CONSTITUENTS["M2"]["period_hours"] == 12.4206
