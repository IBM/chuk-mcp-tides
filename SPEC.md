# chuk-mcp-tides Specification

Version 0.4.0

## Overview

chuk-mcp-tides is an MCP (Model Context Protocol) server that provides tidal
predictions, observed water levels, harmonic analysis, and coastal flooding
assessments from multiple national tide gauge networks.

- **17 tools** for station discovery, predictions, observations, analysis, and flood risk
- **Dual output mode** — all tools return JSON (default) or human-readable text via `output_mode` parameter
- **Async-first** — tool entry points are async; sync I/O runs in thread pools
- **Pluggable storage** — time series data stored via chuk-artifacts (memory, filesystem, S3)
- **Multi-provider** — NOAA CO-OPS, UK Environment Agency, UKHO Admiralty from a single interface
- **Local harmonic engine** — offline tidal predictions from harmonic constituents via utide

## Supported Providers

| Name | URL | Coverage | Auth | Notes |
|------|-----|----------|------|-------|
| `noaa` (default) | `https://api.tidesandcurrents.noaa.gov/api/prod/` | US coastline, Great Lakes, Pacific Islands | None | Free, no key. 3,000+ stations. Predictions up to 10 years (hi/lo). |
| `ea` | `https://environment.data.gov.uk/flood-monitoring/` | England, Wales, N. Ireland | None | Free, no key. 86 tide gauges. Real-time 15-min observations (mAOD). |
| `ukho` | `https://admiraltyapi.azure-api.net/uktidalapi/api/V1/` | UK coastline | API key | Free Discovery tier: 607 stations, today + 6 days. Premium: 1 year history, £300/yr. |
| `local` | N/A (offline) | Any location with constituents | None | Harmonic prediction from stored/fitted constituents via utide. No network required. |

The `provider` parameter on station/prediction tools accepts a short name. When
omitted, the server selects the best provider based on station location or falls
back to `noaa`.

## Datums

Tidal measurements are referenced to vertical datums. The server normalises
datum handling across providers.

### Supported Datums

| Datum | Full Name | Notes |
|-------|-----------|-------|
| `MLLW` | Mean Lower Low Water | US standard chart datum (NOAA default) |
| `MLW` | Mean Low Water | |
| `MSL` | Mean Sea Level | Cross-provider comparable |
| `MHW` | Mean High Water | |
| `MHHW` | Mean Higher High Water | US flood threshold reference |
| `MTL` | Mean Tide Level | |
| `NAVD` | North American Vertical Datum 1988 | US geodetic reference |
| `STND` | Station Datum | Raw sensor reference |
| `LAT` | Lowest Astronomical Tide | UK/international chart datum |
| `HAT` | Highest Astronomical Tide | |
| `AOD` | Above Ordnance Datum (Newlyn) | UK standard. EA default. |
| `CD` | Chart Datum | UKHO default |

**Provider defaults:** NOAA → `MLLW`, EA → `AOD`, UKHO → `CD`, local → `MSL`.

Not all datums are available at all stations. Requesting an unsupported datum
returns an error with available options listed.

---

## Tools

### Common Parameter

All tools accept the following optional parameter:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `output_mode` | `str` | `json` | Response format: `json` (structured) or `text` (human-readable) |

---

### Station Discovery Tools

#### `tides_list_stations`

List tide gauge stations, optionally filtered by location or region.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `provider` | `str?` | `noaa` | Provider name |
| `lat` | `float?` | `None` | Latitude for proximity search |
| `lon` | `float?` | `None` | Longitude for proximity search |
| `radius_km` | `float?` | `50` | Search radius in kilometres |
| `region` | `str?` | `None` | Region filter (provider-specific: US state, EA region name) |
| `station_type` | `str?` | `None` | Filter: `tidal`, `meteorological`, `current` (NOAA only) |
| `max_results` | `int?` | `20` | Maximum stations returned |

**Response:** `StationListResponse`

| Field | Type | Description |
|-------|------|-------------|
| `provider` | `str` | Provider queried |
| `station_count` | `int` | Number of stations returned |
| `stations` | `StationSummary[]` | Station ID, name, lat, lon, type, date range |
| `search_location` | `float[2]?` | Search centre `[lat, lon]` if proximity search |
| `search_radius_km` | `float?` | Radius used |
| `message` | `str` | Result message |

---

#### `tides_describe_station`

Get detailed metadata for a specific station including available datums,
sensors, and data products.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `station_id` | `str` | *required* | Station identifier |
| `provider` | `str?` | auto-detect | Provider name |

**Response:** `StationDetailResponse`

| Field | Type | Description |
|-------|------|-------------|
| `station_id` | `str` | Station identifier |
| `name` | `str` | Station name |
| `provider` | `str` | Provider |
| `lat` | `float` | Latitude |
| `lon` | `float` | Longitude |
| `datums` | `DatumInfo[]` | Available datums with values relative to STND |
| `sensors` | `str[]` | Available sensor types |
| `data_range` | `str[2]?` | Earliest and latest data dates |
| `tidal_type` | `str?` | `semidiurnal`, `diurnal`, or `mixed` |
| `harmonic_constituents` | `ConstituentInfo[]?` | Major constituents if available |
| `flood_thresholds` | `FloodThresholdInfo?` | Minor/moderate/major thresholds (NOAA) |
| `mean_sea_level_trend` | `float?` | mm/year relative sea level trend |
| `linked_station` | `str?` | Paired station ID (EA: local/AOD pairs) |
| `message` | `str` | Result message |

---

#### `tides_find_nearest`

Find the nearest tide station to a coordinate, with optional cross-provider search.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lat` | `float` | *required* | Latitude |
| `lon` | `float` | *required* | Longitude |
| `provider` | `str?` | `all` | Provider or `all` for cross-provider search |
| `max_results` | `int?` | `5` | Maximum stations |

**Response:** `NearestStationResponse`

| Field | Type | Description |
|-------|------|-------------|
| `search_location` | `float[2]` | `[lat, lon]` searched |
| `stations` | `NearestStation[]` | Stations sorted by distance with provider, distance_km |
| `message` | `str` | Result message |

---

### Prediction Tools

#### `tides_predict`

Get tidal height predictions for a station over a date range.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `station_id` | `str` | *required* | Station identifier |
| `start_date` | `str` | `today` | Start date `YYYY-MM-DD` or `today` |
| `end_date` | `str?` | `None` | End date `YYYY-MM-DD`. Default: start + 7 days |
| `interval` | `str` | `hilo` | `hilo` (highs/lows only), `hourly`, `6min`, `1min` |
| `datum` | `str?` | provider default | Vertical datum |
| `provider` | `str?` | auto-detect | Provider name |
| `units` | `str?` | `metric` | `metric` (metres) or `english` (feet) |

**Response:** `PredictionResponse`

| Field | Type | Description |
|-------|------|-------------|
| `station_id` | `str` | Station |
| `station_name` | `str` | Station name |
| `provider` | `str` | Provider used |
| `datum` | `str` | Datum used |
| `units` | `str` | Units |
| `start_date` | `str` | Range start |
| `end_date` | `str` | Range end |
| `interval` | `str` | Interval used |
| `event_count` | `int` | Number of prediction points |
| `predictions` | `TidalEvent[]` | Datetime, height, event_type (high/low/intermediate) |
| `artifact_ref` | `str?` | Artifact reference for time series data |
| `message` | `str` | Result message |

**Data length limits (NOAA):** hi/lo predictions up to 10 years; all other
intervals up to 1 year. UKHO Discovery: today + 6 days. UKHO Premium: 1 year.

---

#### `tides_predict_local`

Compute tidal predictions offline using harmonic constituents. No network
required. Supports arbitrary date ranges including decades into the future.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `station_id` | `str?` | `None` | Station ID to load stored constituents |
| `constituents` | `dict?` | `None` | Manual constituents `{name: {amplitude, phase}}` |
| `start_date` | `str` | *required* | Start date `YYYY-MM-DD` |
| `end_date` | `str` | *required* | End date `YYYY-MM-DD` |
| `interval_minutes` | `int` | `60` | Prediction interval in minutes |
| `datum_offset` | `float` | `0.0` | Offset to add to predictions (e.g., MSL above datum) |

**Response:** `LocalPredictionResponse`

| Field | Type | Description |
|-------|------|-------------|
| `station_id` | `str?` | Station if used |
| `constituent_count` | `int` | Number of constituents used |
| `start_date` | `str` | Range start |
| `end_date` | `str` | Range end |
| `interval_minutes` | `int` | Interval |
| `event_count` | `int` | Number of prediction points |
| `predictions` | `TidalEvent[]` | Datetime, height |
| `highs_lows` | `TidalEvent[]` | Extracted high/low events |
| `artifact_ref` | `str?` | Artifact reference |
| `message` | `str` | Result message |

---

### Observation Tools

#### `tides_observations`

Get observed (measured) water levels from a gauge station.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `station_id` | `str` | *required* | Station identifier |
| `start_date` | `str` | `today` | Start date `YYYY-MM-DD` |
| `end_date` | `str?` | `None` | End date. Default: start + 1 day |
| `product` | `str` | `water_level` | `water_level`, `hourly_height`, `high_low`, `monthly_mean` |
| `datum` | `str?` | provider default | Vertical datum |
| `provider` | `str?` | auto-detect | Provider name |
| `units` | `str?` | `metric` | `metric` or `english` |

**Response:** `ObservationResponse`

| Field | Type | Description |
|-------|------|-------------|
| `station_id` | `str` | Station |
| `station_name` | `str` | Station name |
| `provider` | `str` | Provider used |
| `datum` | `str` | Datum |
| `units` | `str` | Units |
| `product` | `str` | Product type |
| `reading_count` | `int` | Number of readings |
| `readings` | `WaterLevelReading[]` | Datetime, value, quality flag, anomaly |
| `artifact_ref` | `str?` | Artifact reference |
| `message` | `str` | Result message |

---

#### `tides_latest`

Get the most recent water level reading from a station.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `station_id` | `str` | *required* | Station identifier |
| `datum` | `str?` | provider default | Vertical datum |
| `provider` | `str?` | auto-detect | Provider name |

**Response:** `LatestReadingResponse`

| Field | Type | Description |
|-------|------|-------------|
| `station_id` | `str` | Station |
| `station_name` | `str` | Station name |
| `datetime` | `str` | Reading timestamp (UTC) |
| `value` | `float` | Water level |
| `datum` | `str` | Datum |
| `units` | `str` | Units |
| `next_high` | `TidalEvent?` | Next predicted high water |
| `next_low` | `TidalEvent?` | Next predicted low water |
| `tide_state` | `str` | `rising`, `falling`, `high_slack`, `low_slack` |
| `message` | `str` | Result message |

---

### Analysis Tools

#### `tides_threshold_exceedance`

Count how many times water levels exceed a threshold over a period. The core
tool for Strood-type flooding frequency analysis.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `station_id` | `str` | *required* | Station identifier |
| `threshold` | `float` | *required* | Height threshold in station datum units |
| `start_date` | `str` | *required* | Start date `YYYY-MM-DD` |
| `end_date` | `str` | *required* | End date `YYYY-MM-DD` |
| `source` | `str` | `predictions` | `predictions` or `observations` |
| `datum` | `str?` | provider default | Vertical datum |
| `provider` | `str?` | auto-detect | Provider name |
| `group_by` | `str` | `year` | `year`, `month`, `season`, `none` |

**Response:** `ThresholdExceedanceResponse`

| Field | Type | Description |
|-------|------|-------------|
| `station_id` | `str` | Station |
| `threshold` | `float` | Threshold value |
| `datum` | `str` | Datum |
| `source` | `str` | Data source used |
| `total_exceedances` | `int` | Total count |
| `total_hours_above` | `float` | Cumulative duration above threshold |
| `groups` | `ExceedanceGroup[]` | Per-group counts with period label, count, max_height, total_hours |
| `trend` | `TrendInfo?` | Linear trend in exceedances/year if >2 groups |
| `artifact_ref` | `str?` | Artifact reference |
| `message` | `str` | Result message |

---

#### `tides_project_flooding`

Project future flooding frequency by combining tidal predictions with sea level
rise scenarios. The compound analysis tool for coastal viability assessment.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `station_id` | `str` | *required* | Station identifier |
| `threshold` | `float` | *required* | Current flooding threshold in datum units |
| `years` | `int[]` | `[2030, 2040, 2050, 2060, 2080, 2100]` | Projection years |
| `scenarios` | `str[]` | `["low", "intermediate", "high"]` | SLR scenarios |
| `datum` | `str?` | provider default | Vertical datum |
| `provider` | `str?` | auto-detect | Provider name |

**Scenario definitions (mm/year relative to 2000 baseline):**

| Scenario | Rate | Source |
|----------|------|--------|
| `low` | 3.0 mm/yr | IPCC SSP1-2.6 / UKCP18 low |
| `intermediate_low` | 5.0 mm/yr | IPCC SSP2-4.5 |
| `intermediate` | 8.0 mm/yr | NOAA Intermediate |
| `intermediate_high` | 12.0 mm/yr | IPCC SSP5-8.5 |
| `high` | 16.0 mm/yr | NOAA High |
| `extreme` | 25.0 mm/yr | NOAA Extreme (ice sheet collapse) |

If the station has a measured sea level trend (`mean_sea_level_trend` from
`tides_describe_station`), the server uses the observed rate for the `observed`
scenario automatically included in results.

**Response:** `FloodProjectionResponse`

| Field | Type | Description |
|-------|------|-------------|
| `station_id` | `str` | Station |
| `station_name` | `str` | Station name |
| `threshold` | `float` | Current threshold |
| `datum` | `str` | Datum |
| `baseline_year` | `int` | Year used as baseline (latest full year) |
| `baseline_exceedances` | `int` | Exceedance count in baseline year |
| `projections` | `FloodProjection[]` | Per-year, per-scenario: year, scenario, slr_mm, projected_exceedances, projected_hours, delta_from_baseline |
| `tipping_points` | `TippingPoint[]` | Per-scenario: year when exceedances double, 10x, become daily |
| `artifact_ref` | `str?` | Artifact reference |
| `message` | `str` | Result message |

---

#### `tides_harmonic_analysis`

Fit harmonic constituents to an observed water level time series. Enables
local predictions for any station with sufficient observation history.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `station_id` | `str` | *required* | Station identifier |
| `start_date` | `str` | *required* | Observation period start `YYYY-MM-DD` |
| `end_date` | `str` | *required* | Observation period end (minimum 30 days recommended) |
| `provider` | `str?` | auto-detect | Provider name |
| `store_constituents` | `bool` | `true` | Store fitted constituents for `tides_predict_local` |

**Response:** `HarmonicAnalysisResponse`

| Field | Type | Description |
|-------|------|-------------|
| `station_id` | `str` | Station |
| `observation_days` | `int` | Days of data analysed |
| `constituent_count` | `int` | Number of constituents resolved |
| `constituents` | `ConstituentResult[]` | Name, amplitude, phase, frequency, SNR |
| `mean_level` | `float` | Mean water level (Z0) |
| `form_number` | `float` | (K1+O1)/(M2+S2) — tidal classification |
| `tidal_type` | `str` | `semidiurnal` (<0.25), `mixed` (0.25-3.0), `diurnal` (>3.0) |
| `residual_std` | `float` | Standard deviation of residual (non-tidal) signal |
| `stored` | `bool` | Whether constituents were stored |
| `message` | `str` | Result message |

**Minimum data requirements:**
- 30 days resolves major constituents (M2, S2, K1, O1)
- 180 days resolves most named constituents
- 365 days recommended for full analysis (37+ constituents)

---

#### `tides_residual`

Compute the non-tidal residual (observed minus predicted). The residual
captures storm surge, wind setup, atmospheric pressure effects, and river
discharge — the dangerous component that causes flooding beyond normal tides.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `station_id` | `str` | *required* | Station identifier |
| `start_date` | `str` | *required* | Start date `YYYY-MM-DD` |
| `end_date` | `str` | *required* | End date `YYYY-MM-DD` |
| `datum` | `str?` | provider default | Vertical datum |
| `provider` | `str?` | auto-detect | Provider name |

**Response:** `ResidualResponse`

| Field | Type | Description |
|-------|------|-------------|
| `station_id` | `str` | Station |
| `reading_count` | `int` | Number of residual points |
| `max_positive_surge` | `SurgeEvent` | Largest positive residual with datetime |
| `max_negative_surge` | `SurgeEvent` | Largest negative residual with datetime |
| `mean_residual` | `float` | Mean residual (non-zero indicates datum drift or SLR) |
| `std_residual` | `float` | Standard deviation |
| `surge_events` | `SurgeEvent[]` | Events where residual exceeds ±0.3m, with start/end/peak |
| `residuals` | `ResidualPoint[]` | Full time series: datetime, observed, predicted, residual |
| `artifact_ref` | `str?` | Artifact reference |
| `message` | `str` | Result message |

---

#### `tides_sea_level_trend`

Get the long-term sea level rise rate at a station from historical observations.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `station_id` | `str` | *required* | Station identifier |
| `provider` | `str?` | auto-detect | Provider name |

**Response:** `SeaLevelTrendResponse`

| Field | Type | Description |
|-------|------|-------------|
| `station_id` | `str` | Station |
| `station_name` | `str` | Station name |
| `trend_mm_per_year` | `float` | Linear trend in mm/year |
| `trend_uncertainty` | `float` | 95% confidence interval (±mm/year) |
| `first_year` | `int` | Earliest year in record |
| `last_year` | `int` | Latest year in record |
| `record_length_years` | `int` | Duration of record |
| `monthly_means` | `MonthlyMean[]?` | Monthly MSL values (NOAA only) |
| `data_source` | `str` | Source description |
| `message` | `str` | Result message |

---

#### `tides_extreme_levels`

Get historical extreme water level events at a station.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `station_id` | `str` | *required* | Station identifier |
| `datum` | `str?` | provider default | Vertical datum |
| `provider` | `str?` | auto-detect | Provider name |

**Response:** `ExtremeLevelsResponse`

| Field | Type | Description |
|-------|------|-------------|
| `station_id` | `str` | Station |
| `top_ten_high` | `ExtremeEvent[]` | Top 10 highest observed levels with date, height, event name |
| `top_ten_low` | `ExtremeEvent[]` | Top 10 lowest observed levels |
| `datum` | `str` | Datum |
| `message` | `str` | Result message |

---

### Flood Risk Tools

#### `tides_flood_outlook`

Get high-tide flooding outlook (NOAA Derived Product API). Annual and decadal
projections of flood days by threshold.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `station_id` | `str` | *required* | NOAA station identifier |
| `product` | `str` | `annual` | `annual`, `monthly`, `seasonal`, `decadal`, `next_year` |
| `flood_threshold` | `str?` | `minor` | `minor`, `moderate`, `major` |
| `year` | `int?` | `None` | Specific year (annual/monthly/seasonal) |
| `decade` | `int?` | `None` | Decade start year (decadal) |

**Response:** `FloodOutlookResponse`

| Field | Type | Description |
|-------|------|-------------|
| `station_id` | `str` | Station |
| `product` | `str` | Product type |
| `flood_threshold` | `str` | Threshold used |
| `flood_level_m` | `float` | Threshold height in metres |
| `counts` | `FloodCount[]` | Period, count of flood events/days |
| `projection` | `FloodProjectionNOAA?` | Next year projection with confidence interval |
| `message` | `str` | Result message |

**Note:** NOAA-only. Returns `ErrorResponse` for other providers with guidance
to use `tides_threshold_exceedance` + `tides_project_flooding` instead.

---

#### `tides_flooding_calendar`

Generate a day-by-day flooding calendar for a location, showing which dates
a threshold will be exceeded by predicted tides plus optional sea level rise.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `station_id` | `str` | *required* | Station identifier |
| `threshold` | `float` | *required* | Flooding threshold in datum units |
| `year` | `int` | current year | Calendar year to generate |
| `slr_offset_mm` | `float` | `0.0` | Sea level rise offset to add (mm) |
| `datum` | `str?` | provider default | Vertical datum |
| `provider` | `str?` | auto-detect | Provider name |

**Response:** `FloodingCalendarResponse`

| Field | Type | Description |
|-------|------|-------------|
| `station_id` | `str` | Station |
| `year` | `int` | Calendar year |
| `threshold` | `float` | Threshold |
| `slr_offset_mm` | `float` | SLR offset applied |
| `datum` | `str` | Datum |
| `total_flood_days` | `int` | Days with at least one exceedance |
| `total_flood_hours` | `float` | Cumulative hours above threshold |
| `monthly_summary` | `MonthFloodSummary[]` | Per-month: flood_days, max_height, total_hours |
| `flood_days` | `FloodDay[]` | Each flooded day: date, peak_height, duration_hours, tides_above |
| `artifact_ref` | `str?` | Artifact reference |
| `message` | `str` | Result message |

---

### Discovery Tools

#### `tides_status`

Get server status and configuration.

**Parameters:** None

**Response:** `StatusResponse`

| Field | Type | Description |
|-------|------|-------------|
| `server` | `str` | Server name |
| `version` | `str` | Server version |
| `storage_provider` | `str` | Active storage backend |
| `providers` | `ProviderStatus[]` | Per-provider: name, available, station_count, auth_configured |
| `harmonic_engine` | `str` | utide version |
| `stored_constituents` | `int` | Number of stations with stored constituents |

---

#### `tides_capabilities`

List full server capabilities for LLM workflow planning.

**Parameters:** None

**Response:** `CapabilitiesResponse`

| Field | Type | Description |
|-------|------|-------------|
| `server` | `str` | Server name |
| `version` | `str` | Server version |
| `providers` | `ProviderInfo[]` | Provider details with coverage, auth, limits |
| `datums` | `DatumInfo[]` | All supported datums |
| `scenarios` | `ScenarioInfo[]` | SLR scenarios with rates |
| `tool_count` | `int` | Number of registered tools |
| `cross_server_workflows` | `WorkflowInfo[]` | Documented integrations with DEM, STAC, weather, maritime |

---

## Harmonic Constituents

The local harmonic engine uses utide for analysis and reconstruction. The
following major constituents are supported:

### Principal Constituents

| Name | Period (hours) | Description | Origin |
|------|---------------|-------------|--------|
| `M2` | 12.4206 | Principal lunar semidiurnal | Moon's gravitational pull |
| `S2` | 12.0000 | Principal solar semidiurnal | Sun's gravitational pull |
| `N2` | 12.6583 | Larger lunar elliptic | Moon's elliptical orbit |
| `K2` | 11.9672 | Lunisolar semidiurnal | Sun-moon declination |
| `K1` | 23.9345 | Lunisolar diurnal | Sun-moon declination |
| `O1` | 25.8193 | Principal lunar diurnal | Moon's declination |
| `P1` | 24.0659 | Principal solar diurnal | Sun's declination |
| `Q1` | 26.8684 | Larger lunar elliptic diurnal | Moon's elliptical orbit |
| `M4` | 6.2103 | Shallow water overtide of M2 | Non-linear (estuaries) |
| `MS4` | 6.1033 | Shallow water compound | M2 + S2 interaction |
| `M6` | 4.1402 | Shallow water overtide | Triple M2 frequency |

### Form Number Classification

| Form Number | Classification | Example Locations |
|-------------|---------------|-------------------|
| < 0.25 | Semidiurnal | North Sea, English Channel, US East Coast |
| 0.25 – 3.0 | Mixed | Gulf of Mexico, US West Coast, SE Asia |
| > 3.0 | Diurnal | Gulf of Thailand, Java Sea, parts of Caribbean |

Form number = (K1 + O1) / (M2 + S2). Determines the character of the local
tide and affects prediction accuracy requirements.

---

## Artifact Storage

Time series data are stored via chuk-artifacts with enriched metadata:

```json
{
  "type": "tidal_timeseries",
  "schema_version": "1.0",
  "station_id": "8518750",
  "station_name": "The Battery, NY",
  "provider": "noaa",
  "data_type": "predictions",
  "datum": "MLLW",
  "units": "metric",
  "start_date": "2026-01-01T00:00:00Z",
  "end_date": "2026-12-31T23:59:00Z",
  "interval": "hilo",
  "event_count": 1412,
  "lat": 40.7006,
  "lon": -74.0142
}
```

For harmonic analysis results:

```json
{
  "type": "harmonic_constituents",
  "schema_version": "1.0",
  "station_id": "8518750",
  "station_name": "The Battery, NY",
  "provider": "noaa",
  "constituent_count": 37,
  "observation_days": 365,
  "mean_level": 0.823,
  "form_number": 0.137,
  "tidal_type": "semidiurnal",
  "fitted_date": "2026-02-09"
}
```

### Storage Providers

| Provider | Env Variable | Value |
|----------|-------------|-------|
| Memory (default) | `CHUK_ARTIFACTS_PROVIDER` | `memory` |
| Filesystem | `CHUK_ARTIFACTS_PROVIDER` | `filesystem` |
| Amazon S3 | `CHUK_ARTIFACTS_PROVIDER` | `s3` |

Additional environment variables for S3: `BUCKET_NAME`, `AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL_S3`.

---

## Error Handling

All tools return `ErrorResponse` on failure:

```json
{
  "error": "Station '9999999' not found in NOAA database"
}
```

### Common Error Scenarios

| Scenario | Error Message |
|----------|---------------|
| Invalid station ID | "Station '{id}' not found in {provider} database" |
| Unsupported datum | "Datum '{datum}' not available at station {id}. Available: [...]" |
| Date range too large | "Date range exceeds {provider} limit of {limit}" |
| Provider unavailable | "Provider '{name}' is not responding. Try again or use alternative provider." |
| No API key configured | "UKHO provider requires API key. Set UKHO_API_KEY environment variable." |
| Insufficient data for analysis | "Harmonic analysis requires ≥30 days of observations. Got {n} days." |
| No artifact store | "No artifact store available. Configure CHUK_ARTIFACTS_PROVIDER..." |
| Threshold below datum | "Threshold {value} is below minimum datum level {min}" |

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `UKHO_API_KEY` | For UKHO | `None` | UKHO Admiralty API subscription key |
| `CHUK_ARTIFACTS_PROVIDER` | No | `memory` | Artifact storage backend |
| `TIDES_DEFAULT_PROVIDER` | No | `noaa` | Default provider when not specified |
| `TIDES_CACHE_TTL_SECONDS` | No | `3600` | Cache TTL for API responses |
| `TIDES_CONSTITUENTS_DIR` | No | `~/.chuk/tides/constituents` | Directory for stored harmonic constituents |

### Provider Rate Limits

| Provider | Rate Limit | Data Limit |
|----------|-----------|------------|
| NOAA | No formal limit (be reasonable) | Varies by product |
| EA | No formal limit | 15-min resolution |
| UKHO Discovery | 10 req/sec, 10,000 req/month | Today + 6 days |
| UKHO Premium | 100 req/sec, 100,000 req/month | ±1 year |

---

## Cross-Server Workflows

chuk-mcp-tides is designed to integrate with the broader MCP ecosystem:

### Tides + DEM: Inundation Mapping

1. `tides_predict` → get tidal heights for target dates
2. `tides_project_flooding` → project future flood frequency
3. `dem_contour` → extract elevation contours at flood threshold heights
4. `dem_elevation_profile` → cross-section of causeway/defence structure

**Use case:** Strood causeway. Tides server provides the threshold height and
exceedance frequency. DEM server shows exactly which areas flood at that height.

### Tides + STAC: Satellite Validation

1. `tides_observations` → get observed water level at time of satellite pass
2. `stac_search` → find scene at matching date
3. `stac_compute_index` → compute NDWI for water extent
4. `tides_threshold_exceedance` → compare observed flooding frequency with satellite-detected flooding extent

**Use case:** Validating EA flood models. Satellite shows where water actually
went; tide gauge shows how high it was. Combined, they validate or contradict
the model.

### Tides + Weather: Storm Surge Analysis

1. `tides_residual` → extract non-tidal component (surge)
2. `get_historical_weather` → match surge events with meteorological conditions
3. `tides_predict` → get astronomical tide for storm date
4. Combine: total level = tide + surge. Attribute causation.

**Use case:** Post-event analysis. "The flooding in Mersea on [date] was caused
by a [X]m storm surge coinciding with a [Y]m spring tide, producing a total
level of [Z]m — [W]m above the Strood threshold."

### Tides + Maritime: Historical Context

1. `tides_sea_level_trend` → long-term rate at nearest station
2. `maritime_voyage_route` → historical shipping route
3. `tides_predict_local` → reconstruct tidal conditions for historical date

**Use case:** VOC wreck hunting. "When the Batavia struck Morning Reef in 1629,
the tide at the nearest modern gauge location would have been approximately
[X]m. Current low water would expose reef to [Y]m. Best survey window:
[dates] at spring low tide."

---

## Performance

### Response Cache

API responses are cached in-memory with configurable TTL (default 1 hour).
Identical requests within the TTL return cached results without network calls.
Cache keys include provider, station, date range, datum, and product.

### Constituent Store

Fitted harmonic constituents are persisted to disk at `TIDES_CONSTITUENTS_DIR`.
Once stored, `tides_predict_local` requires no network access and can generate
predictions for arbitrary future date ranges in milliseconds.

### Batch Predictions

`tides_flooding_calendar` and `tides_project_flooding` compute full-year
predictions internally. For NOAA hi/lo data this means ~1,400 events per year.
For minute-interval local predictions, the harmonic engine produces ~525,600
points per year in under 2 seconds.

---

## Roadmap

### Planned Additions

- **Tidal current predictions** — NOAA current stations, slack/max predictions
- **Global tide models** — FES2014 / TPXO integration for locations without gauges
- **Surge probability** — extreme value analysis (return periods) from residual history
- **Multi-station interpolation** — tidal predictions between gauges using co-tidal charts
- **InSAR integration** — ground subsidence rates from chuk-mcp-stac Sentinel-1 to refine relative SLR

### Note on Geocoding

Geocoding (place name → station lookup) is planned as a **separate MCP server**,
not part of chuk-mcp-tides. This server accepts station IDs and coordinates.
Use `tides_find_nearest` with lat/lon for discovery.
