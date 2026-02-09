# chuk-mcp-tides Roadmap

## v0.1.0 — Foundation (Complete)

Ship-ready scaffold with core infrastructure.

- [x] Project scaffold (pyproject.toml, Makefile, CI/CD, pre-commit)
- [x] Constants module (providers, datums, scenarios, error messages)
- [x] Pydantic v2 response models with dual output (JSON + text)
- [x] TideManager orchestrator with provider dispatch
- [x] NOAA CO-OPS provider (stations, predictions, observations)
- [x] Discovery tools (tides_status, tides_capabilities)
- [x] Station discovery tools (list, describe, find_nearest)
- [x] Prediction tools (tides_predict)
- [x] Observation tools (tides_observations, tides_latest)
- [x] Test suite (203 tests)
- [x] README, ARCHITECTURE, SPEC documentation

## v0.2.0 — Analysis & Flood Risk (Complete)

Core analysis and flood risk assessment capabilities.

- [x] Threshold exceedance analysis (tides_threshold_exceedance)
- [x] Flood projection with SLR scenarios (tides_project_flooding)
- [x] Flooding calendar generation (tides_flooding_calendar)
- [x] NOAA flood outlook integration (tides_flood_outlook)
- [x] Extreme levels lookup (tides_extreme_levels)
- [x] Sea level trend analysis (tides_sea_level_trend)

## v0.3.0 — Harmonic Engine & UK Providers (Complete)

Local harmonic predictions, UK data sources, artifact storage.

- [x] utide integration for harmonic analysis (tides_harmonic_analysis)
- [x] Local prediction engine (tides_predict_local)
- [x] Constituent storage via chuk-artifacts (pluggable: memory, filesystem, S3)
- [x] Residual computation (tides_residual)
- [x] UK Environment Agency provider (86 tide gauges)
- [x] UKHO Admiralty provider (Discovery tier)
- [x] Cross-provider station search (find_nearest across all providers)
- [x] Example scripts (quick_start, mersea_island_scenario, capabilities_demo)
- [x] NOAA Derived Products API fixes (sea level trends, extremes, HTF)

## v0.4.0 — Production Hardening (Complete)

Performance, reliability, deployment, and harmonic engine fixes.

- [x] ResilientClient with connection pooling, retry, and exponential backoff
- [x] Per-provider rate limiting (configurable requests/second)
- [x] All providers migrated to shared HTTP client (NOAA, EA, UKHO)
- [x] Response caching with configurable TTL (TideManager, 500-entry LRU)
- [x] Two-tier reference cache (memory + chuk-artifacts SANDBOX scope)
  - Station lists (24h), details (24h), trends (48h), extremes (48h), flood outlook (12h)
  - New servers warm index from S3 — no redundant API downloads
- [x] Sea level trends, extreme levels, flood outlook now cached (previously uncached)
- [x] Dockerfile and docker-compose for containerised deployment
- [x] Tidal current predictions (NOAA current stations, ~4,400 stations)
  - tides_currents_stations — station discovery with location filtering
  - tides_currents_predictions — velocity predictions (slack/flood/ebb, direction)
  - tides_currents_latest — most recent current observation
  - Auto-detect bin number from station metadata (bin numbers are station-specific)
- [x] EA provider: start_date handling (YYYYMMDD → ISO since), auto-scaling limit for long date ranges
- [x] Observation-based tide state inference for EA stations (rising/falling from recent readings)
- [x] Harmonic engine fixes:
  - utide time arrays now use np.datetime64 (date2num caused 0 constituents — periodogram dt=0)
  - Coefficient storage serializes full utide Bunch (reconstruct needs subscript access to aux.opt)
  - utide.reconstruct() no longer passed invalid lat parameter
  - EA observations sorted ascending before harmonic analysis (EA returns descending)
- [x] Mersea Island demo: self-contained EA workflow (discovery → observations → harmonic analysis → local predictions → flooding calendar)
- [x] 245 tests across 17 test modules, 20 tools across 7 categories

## v0.5.0 — Extended Capabilities

Future enhancements beyond the core 20 tools.

- [ ] Datum conversions (tides_convert_datum — convert heights between datums at a station)
- [ ] Return period analysis (tides_return_periods — GEV/GPD extreme value analysis)
- [ ] Safe passage windows (tides_safe_passage — time windows above draft threshold)
- [ ] Surge probability (extreme value analysis, return periods)
- [ ] Multi-station interpolation (co-tidal charts)
