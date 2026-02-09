"""
Constants and configuration for chuk-mcp-tides.

All magic strings live here as enums or module-level constants.
"""

from enum import Enum
from typing import Any

# ─── Server Configuration ──────────────────────────────────────────────────────


class ServerConfig(str, Enum):
    NAME = "chuk-mcp-tides"
    VERSION = "0.4.0"
    DESCRIPTION = "Tidal Data Discovery & Analysis"


# ─── Storage / Session Providers ───────────────────────────────────────────────


class StorageProvider(str, Enum):
    MEMORY = "memory"
    S3 = "s3"
    FILESYSTEM = "filesystem"


class SessionProvider(str, Enum):
    MEMORY = "memory"
    REDIS = "redis"


# ─── Environment Variable Names ───────────────────────────────────────────────


class EnvVar:
    """Environment variable names used throughout the application."""

    ARTIFACTS_PROVIDER = "CHUK_ARTIFACTS_PROVIDER"
    BUCKET_NAME = "BUCKET_NAME"
    REDIS_URL = "REDIS_URL"
    ARTIFACTS_PATH = "CHUK_ARTIFACTS_PATH"
    AWS_ACCESS_KEY_ID = "AWS_ACCESS_KEY_ID"
    AWS_SECRET_ACCESS_KEY = "AWS_SECRET_ACCESS_KEY"
    AWS_ENDPOINT_URL_S3 = "AWS_ENDPOINT_URL_S3"
    MCP_STDIO = "MCP_STDIO"
    UKHO_API_KEY = "UKHO_API_KEY"
    DEFAULT_PROVIDER = "TIDES_DEFAULT_PROVIDER"
    CACHE_TTL = "TIDES_CACHE_TTL_SECONDS"
    CONSTITUENTS_DIR = "TIDES_CONSTITUENTS_DIR"


# ─── Tide Data Providers ──────────────────────────────────────────────────────


class TideProvider(str, Enum):
    NOAA = "noaa"
    EA = "ea"
    UKHO = "ukho"
    LOCAL = "local"


DEFAULT_PROVIDER = TideProvider.NOAA

PROVIDER_URLS = {
    TideProvider.NOAA: "https://api.tidesandcurrents.noaa.gov/api/prod/",
    TideProvider.EA: "https://environment.data.gov.uk/flood-monitoring/",
    TideProvider.UKHO: "https://admiraltyapi.azure-api.net/uktidalapi/api/V1/",
}

PROVIDER_INFO: dict[TideProvider, dict[str, Any]] = {
    TideProvider.NOAA: {
        "name": "NOAA CO-OPS",
        "coverage": "US coastline, Great Lakes, Pacific Islands",
        "auth": False,
        "station_count": 3000,
    },
    TideProvider.EA: {
        "name": "UK Environment Agency",
        "coverage": "England, Wales, N. Ireland",
        "auth": False,
        "station_count": 86,
    },
    TideProvider.UKHO: {
        "name": "UKHO Admiralty",
        "coverage": "UK coastline",
        "auth": True,
        "station_count": 607,
    },
    TideProvider.LOCAL: {
        "name": "Local Harmonic Engine",
        "coverage": "Any location with constituents",
        "auth": False,
        "station_count": 0,
    },
}


# ─── Vertical Datums ─────────────────────────────────────────────────────────


class Datum(str, Enum):
    MLLW = "MLLW"
    MLW = "MLW"
    MSL = "MSL"
    MHW = "MHW"
    MHHW = "MHHW"
    MTL = "MTL"
    NAVD = "NAVD"
    STND = "STND"
    LAT = "LAT"
    HAT = "HAT"
    AOD = "AOD"
    CD = "CD"


DATUM_NAMES = {
    Datum.MLLW: "Mean Lower Low Water",
    Datum.MLW: "Mean Low Water",
    Datum.MSL: "Mean Sea Level",
    Datum.MHW: "Mean High Water",
    Datum.MHHW: "Mean Higher High Water",
    Datum.MTL: "Mean Tide Level",
    Datum.NAVD: "North American Vertical Datum 1988",
    Datum.STND: "Station Datum",
    Datum.LAT: "Lowest Astronomical Tide",
    Datum.HAT: "Highest Astronomical Tide",
    Datum.AOD: "Above Ordnance Datum (Newlyn)",
    Datum.CD: "Chart Datum",
}

PROVIDER_DEFAULT_DATUMS = {
    TideProvider.NOAA: Datum.MLLW,
    TideProvider.EA: Datum.AOD,
    TideProvider.UKHO: Datum.CD,
    TideProvider.LOCAL: Datum.MSL,
}


# ─── Sea Level Rise Scenarios ────────────────────────────────────────────────


SLR_SCENARIOS: dict[str, dict[str, Any]] = {
    "low": {"rate_mm_yr": 3.0, "source": "IPCC SSP1-2.6 / UKCP18 low"},
    "intermediate_low": {"rate_mm_yr": 5.0, "source": "IPCC SSP2-4.5"},
    "intermediate": {"rate_mm_yr": 8.0, "source": "NOAA Intermediate"},
    "intermediate_high": {"rate_mm_yr": 12.0, "source": "IPCC SSP5-8.5"},
    "high": {"rate_mm_yr": 16.0, "source": "NOAA High"},
    "extreme": {"rate_mm_yr": 25.0, "source": "NOAA Extreme (ice sheet collapse)"},
}

SLR_BASELINE_YEAR = 2000


# ─── Harmonic Constituents ───────────────────────────────────────────────────


PRINCIPAL_CONSTITUENTS = {
    "M2": {"period_hours": 12.4206, "description": "Principal lunar semidiurnal"},
    "S2": {"period_hours": 12.0000, "description": "Principal solar semidiurnal"},
    "N2": {"period_hours": 12.6583, "description": "Larger lunar elliptic"},
    "K2": {"period_hours": 11.9672, "description": "Lunisolar semidiurnal"},
    "K1": {"period_hours": 23.9345, "description": "Lunisolar diurnal"},
    "O1": {"period_hours": 25.8193, "description": "Principal lunar diurnal"},
    "P1": {"period_hours": 24.0659, "description": "Principal solar diurnal"},
    "Q1": {"period_hours": 26.8684, "description": "Larger lunar elliptic diurnal"},
    "M4": {"period_hours": 6.2103, "description": "Shallow water overtide of M2"},
    "MS4": {"period_hours": 6.1033, "description": "Shallow water compound"},
    "M6": {"period_hours": 4.1402, "description": "Shallow water overtide"},
}


# ─── Tidal Classification ───────────────────────────────────────────────────


FORM_NUMBER_SEMIDIURNAL = 0.25
FORM_NUMBER_MIXED_MAX = 3.0


# ─── Cache Configuration ────────────────────────────────────────────────────


DEFAULT_CACHE_TTL_SECONDS = 3600
DEFAULT_CONSTITUENTS_DIR = "~/.chuk/tides/constituents"

# Reference data TTLs (seconds) — persisted via chuk-artifacts SANDBOX scope
REFERENCE_CACHE_TTL: dict[str, int] = {
    "stations": 86_400,  # 24 h — station lists change rarely
    "detail": 86_400,  # 24 h — station metadata is stable
    "trend": 172_800,  # 48 h — annual sea-level trend data
    "extremes": 172_800,  # 48 h — historical top-ten events
    "flood": 43_200,  # 12 h — seasonal flood outlook
    "current_stations": 86_400,  # 24 h — current station lists change rarely
}


# ─── Defaults ────────────────────────────────────────────────────────────────


DEFAULT_MAX_STATIONS = 20
DEFAULT_SEARCH_RADIUS_KM = 50.0
DEFAULT_PREDICTION_DAYS = 7
DEFAULT_OBSERVATION_DAYS = 1
DEFAULT_CURRENT_PREDICTION_DAYS = 2
SURGE_THRESHOLD_M = 0.3

DEFAULT_PROJECTION_YEARS = [2030, 2040, 2050, 2060, 2080, 2100]
DEFAULT_PROJECTION_SCENARIOS = ["low", "intermediate", "high"]


# ─── Error Messages ─────────────────────────────────────────────────────────


class ErrorMessages:
    STATION_NOT_FOUND = "Station '{id}' not found in {provider} database"
    UNSUPPORTED_DATUM = "Datum '{datum}' not available at station {id}. Available: {available}"
    DATE_RANGE_TOO_LARGE = "Date range exceeds {provider} limit of {limit}"
    PROVIDER_UNAVAILABLE = (
        "Provider '{name}' is not responding. Try again or use alternative provider."
    )
    NO_API_KEY = "UKHO provider requires API key. Set UKHO_API_KEY environment variable."
    INSUFFICIENT_DATA = "Harmonic analysis requires ≥30 days of observations. Got {n} days."
    NO_ARTIFACT_STORE = "No artifact store available. Configure CHUK_ARTIFACTS_PROVIDER..."
    THRESHOLD_BELOW_DATUM = "Threshold {value} is below minimum datum level {min}"


class SuccessMessages:
    STATIONS_FOUND = "Found {count} stations"
    PREDICTIONS_READY = "{count} predictions from {start} to {end}"
    OBSERVATIONS_READY = "{count} observations from {start} to {end}"
    ANALYSIS_COMPLETE = "Analysis complete: {summary}"
