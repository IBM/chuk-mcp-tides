# chuk-mcp-tides

Tidal Data Discovery & Analysis MCP Server

An MCP (Model Context Protocol) server providing tidal predictions, observed
water levels, harmonic analysis, and coastal flooding assessments from multiple
national tide gauge networks.

- **21 tools** across 7 categories (stations, predictions, observations, analysis, flood risk, currents, discovery)
- **Multi-provider** — NOAA CO-OPS, UK Environment Agency, UKHO Admiralty, local harmonic engine
- **Dual output** — JSON (structured) or human-readable text via `output_mode`
- **Local harmonic engine** — offline tidal predictions from fitted constituents via utide
- **Pluggable storage** — time series data stored via chuk-artifacts (memory, filesystem, S3)

## Quick Start

### Install

```bash
# No installation required (runs directly)
uvx chuk-mcp-tides

# Or install from PyPI
uv pip install chuk-mcp-tides

# Or install from source
git clone https://github.com/IBM/chuk-mcp-tides.git
cd chuk-mcp-tides
uv pip install -e ".[dev]"
```

### Claude Desktop Configuration

```json
{
  "mcpServers": {
    "tides": {
      "command": "uvx",
      "args": ["chuk-mcp-tides"]
    }
  }
}
```

### Run

```bash
# STDIO mode (Claude Desktop, mcp-cli)
chuk-mcp-tides stdio

# HTTP mode (API access)
chuk-mcp-tides http --port 8003
```

## Supported Providers

| Provider | Coverage | Auth | Stations |
|----------|----------|------|----------|
| **NOAA CO-OPS** | US coastline, Great Lakes, Pacific Islands | None | 3,000+ |
| **EA Flood Monitoring** | England, Wales, N. Ireland | None | 86 tide gauges |
| **UKHO Admiralty** | UK coastline | API key | 607 |
| **Local (utide)** | Any location with constituents | None | Offline |

## Tools

### Station Discovery (3 tools)

| Tool | Description |
|------|-------------|
| `tides_list_stations` | List stations filtered by location, region, or type |
| `tides_describe_station` | Detailed metadata: datums, sensors, tidal type, flood thresholds |
| `tides_find_nearest` | Find nearest station to coordinates, cross-provider search |

### Predictions (2 tools)

| Tool | Description |
|------|-------------|
| `tides_predict` | Tidal height predictions (hi/lo, hourly, 6-min, 1-min intervals) |
| `tides_predict_local` | Offline predictions from harmonic constituents via utide |

### Observations (2 tools)

| Tool | Description |
|------|-------------|
| `tides_observations` | Observed water levels (water_level, hourly, high_low, monthly_mean) |
| `tides_latest` | Most recent reading with tide state and next high/low |

### Analysis (7 tools)

| Tool | Description |
|------|-------------|
| `tides_threshold_exceedance` | Count threshold exceedances grouped by year/month/season |
| `tides_project_flooding` | Future flood frequency under sea level rise scenarios |
| `tides_harmonic_analysis` | Fit harmonic constituents to observation data |
| `tides_residual` | Non-tidal residual (storm surge extraction) |
| `tides_sea_level_trend` | Long-term sea level rise rate from historical data |
| `tides_extreme_levels` | Top 10 highest/lowest observed levels |
| `tides_classify_stage` | Tide height + stage at given timestamps (e.g. satellite acquisitions) for tide-stratified imagery selection |

### Flood Risk (2 tools)

| Tool | Description |
|------|-------------|
| `tides_flood_outlook` | NOAA high-tide flooding outlook (annual, decadal, next year) |
| `tides_flooding_calendar` | Day-by-day flooding calendar with optional SLR offset |

### Tidal Currents (3 tools)

| Tool | Description |
|------|-------------|
| `tides_currents_stations` | List NOAA tidal current prediction stations (~4,400) |
| `tides_currents_predictions` | Current velocity predictions (slack/flood/ebb, direction, depth) |
| `tides_currents_latest` | Most recent current observation with velocity and direction |

### Discovery (2 tools)

| Tool | Description |
|------|-------------|
| `tides_status` | Server status, provider availability, storage backend |
| `tides_capabilities` | Full capabilities for LLM workflow planning |

## Examples

Four demo scripts are included in `examples/`:

```bash
cd examples

# Quick start — NOAA stations, predictions, sea level trends (Providence, RI)
python quick_start.py

# Tidal currents — current stations, predictions, latest observations
python currents_demo.py

# Mersea Island — complete coastal flooding assessment (EA → harmonic → predictions → calendar)
python mersea_island_scenario.py

# Capabilities demo — offline tool listing and status (no network)
python capabilities_demo.py
```

The Mersea Island scenario demonstrates the full analysis pipeline using only
free EA data: station discovery, live observations with tide state inference,
harmonic analysis (29 constituents from 30 days of observations), offline
predictions from stored constituents, and a full-year flooding calendar for
the Strood causeway.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `UKHO_API_KEY` | For UKHO | — | UKHO Admiralty API key |
| `CHUK_ARTIFACTS_PROVIDER` | No | `memory` | Storage backend |
| `TIDES_DEFAULT_PROVIDER` | No | `noaa` | Default provider |
| `TIDES_CACHE_TTL_SECONDS` | No | `3600` | API response cache TTL |
| `CHUK_ARTIFACTS_PATH` | No | — | Filesystem artifact storage path |

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
make test

# Run tests with coverage
make test-cov

# Lint and format
make lint
make format

# All checks
make check
```

## Cross-Server Workflows

chuk-mcp-tides integrates with the broader chuk MCP ecosystem:

- **Tides + DEM** — Inundation mapping (flood threshold heights + terrain elevation)
- **Tides + STAC** — Satellite validation (water levels at time of satellite pass)
- **Tides + Weather** — Storm surge attribution (residual + meteorological conditions)
- **Tides + Maritime** — Historical context (reconstruct tidal conditions for historical dates)

## License

Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
