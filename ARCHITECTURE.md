# chuk-mcp-tides Architecture

## Design Principles

1. **Async-first** — All tool entry points are async; sync I/O (HTTP calls, harmonic computation) runs via `asyncio.to_thread()`
2. **Single responsibility** — Tools validate inputs, providers handle API specifics, TideManager orchestrates workflows
3. **Pydantic v2 native** — All responses use `extra="forbid"` with `to_text()` method for dual output
4. **No magic strings** — All constants (datums, providers, scenarios, error messages) live in `constants.py`
5. **Pluggable storage** — chuk-artifacts abstraction (memory, filesystem, S3) for time series and constituents
6. **Multi-provider** — Unified interface across NOAA, EA, UKHO, and local harmonic engine
7. **90%+ coverage** — Per-file test requirements enforced in CI

## Module Structure

```
src/chuk_mcp_tides/
├── __init__.py              # Package docstring
├── server.py                # CLI entry point (artifact store init, transport selection)
├── async_server.py          # MCP server instance + tool registration
├── constants.py             # Enums, datums, providers, scenarios, error messages
├── core/
│   ├── __init__.py
│   └── tide_manager.py      # Central orchestrator (provider dispatch, caching, storage)
├── models/
│   ├── __init__.py          # Response model exports
│   └── responses.py         # Pydantic v2 response models (extra="forbid", to_text())
├── providers/
│   ├── __init__.py
│   ├── base.py              # Abstract provider interface
│   ├── noaa.py              # NOAA CO-OPS API client
│   ├── ea.py                # UK Environment Agency API client
│   ├── ukho.py              # UKHO Admiralty API client
│   └── local.py             # Local harmonic engine (utide)
└── tools/
    ├── __init__.py          # Exports all register_*_tools functions
    ├── stations/
    │   ├── __init__.py
    │   └── api.py           # tides_list_stations, tides_describe_station, tides_find_nearest
    ├── predictions/
    │   ├── __init__.py
    │   └── api.py           # tides_predict, tides_predict_local
    ├── observations/
    │   ├── __init__.py
    │   └── api.py           # tides_observations, tides_latest
    ├── analysis/
    │   ├── __init__.py
    │   └── api.py           # tides_threshold_exceedance, tides_project_flooding,
    │                        # tides_harmonic_analysis, tides_residual,
    │                        # tides_sea_level_trend, tides_extreme_levels
    ├── flood/
    │   ├── __init__.py
    │   └── api.py           # tides_flood_outlook, tides_flooding_calendar
    └── discovery/
        ├── __init__.py
        └── api.py           # tides_status, tides_capabilities
```

## Data Flow

```
LLM / Client
    │
    ▼
MCP Transport (stdio / HTTP)
    │
    ▼
Tool Layer (tools/*/api.py)
    │  - Input validation
    │  - Parameter defaults
    │  - output_mode formatting
    ▼
TideManager (core/tide_manager.py)
    │  - Provider selection
    │  - Response caching
    │  - Artifact storage
    ▼
Provider Layer (providers/*.py)
    │  - API-specific HTTP calls
    │  - Response normalisation
    │  - Datum conversion
    ▼
External APIs / Local Engine
    │  - NOAA CO-OPS
    │  - EA Flood Monitoring
    │  - UKHO Admiralty
    │  - utide (local)
```

## Tool Groups

| Group | Module | Tools | Count |
|-------|--------|-------|-------|
| Station Discovery | `tools/stations/` | list_stations, describe_station, find_nearest | 3 |
| Predictions | `tools/predictions/` | predict, predict_local | 2 |
| Observations | `tools/observations/` | observations, latest | 2 |
| Analysis | `tools/analysis/` | threshold_exceedance, project_flooding, harmonic_analysis, residual, sea_level_trend, extreme_levels | 6 |
| Flood Risk | `tools/flood/` | flood_outlook, flooding_calendar | 2 |
| Discovery | `tools/discovery/` | status, capabilities | 2 |
| | | **Total** | **18** |

## Provider Architecture

Each provider implements a common interface:

- `list_stations()` — Station discovery with location/region filtering
- `get_station_detail()` — Full station metadata
- `get_predictions()` — Tidal height predictions
- `get_observations()` — Observed water levels
- `get_latest()` — Most recent reading
- `get_extremes()` — Historical extreme events
- `get_sea_level_trend()` — Long-term MSL trend

The TideManager dispatches to the correct provider based on the `provider`
parameter or auto-detection from station ID format.

## Caching Strategy

- **Response cache** — In-memory TTL cache (default 1 hour) for API responses
- **Constituent store** — Disk-persisted harmonic constituents at `TIDES_CONSTITUENTS_DIR`
- **Station metadata** — Cached after first lookup per session

## Testing

Tests are in `tests/` with provider-specific mocking:

- `test_constants.py` — Enum validation, scenario definitions
- `test_models.py` — Pydantic model serialization, to_text() output
- `test_tide_manager.py` — Provider dispatch, caching, storage
- `test_station_tools.py` — Station discovery tools
- `test_prediction_tools.py` — Prediction tools
- `test_observation_tools.py` — Observation tools
- `test_analysis_tools.py` — Analysis tools
- `test_flood_tools.py` — Flood risk tools
- `test_discovery_tools.py` — Status and capabilities
- `test_server.py` — Entry point and transport selection

Coverage threshold: **90% per file** enforced in CI.
