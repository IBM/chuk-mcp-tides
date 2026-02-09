"""Tests for response models."""

import json

from chuk_mcp_tides.models.responses import (
    ErrorResponse,
    ProviderStatus,
    StatusResponse,
    SuccessResponse,
    format_response,
)


def test_error_response():
    r = ErrorResponse(error="something broke")
    assert r.error == "something broke"
    assert r.to_text() == "Error: something broke"


def test_success_response():
    r = SuccessResponse(message="all good")
    assert r.message == "all good"
    assert r.to_text() == "all good"


def test_status_response():
    r = StatusResponse(
        server="chuk-mcp-tides",
        version="0.1.0",
        storage_provider="memory",
        providers=[
            ProviderStatus(
                name="NOAA CO-OPS",
                available=True,
                station_count=3000,
                auth_configured=True,
            )
        ],
        harmonic_engine="utide",
        stored_constituents=0,
    )
    text = r.to_text()
    assert "chuk-mcp-tides" in text
    assert "NOAA CO-OPS" in text


def test_format_response_json():
    r = ErrorResponse(error="test")
    result = format_response(r, "json")
    parsed = json.loads(result)
    assert parsed["error"] == "test"


def test_format_response_text():
    r = ErrorResponse(error="test")
    result = format_response(r, "text")
    assert result == "Error: test"
