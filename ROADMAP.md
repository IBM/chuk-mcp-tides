# chuk-mcp-tides Roadmap

## v0.1.0 — Foundation (Current)

Ship-ready scaffold with core infrastructure.

- [ ] Project scaffold (pyproject.toml, Makefile, CI/CD, pre-commit)
- [ ] Constants module (providers, datums, scenarios, error messages)
- [ ] Pydantic v2 response models with dual output (JSON + text)
- [ ] TideManager orchestrator with provider dispatch
- [ ] NOAA CO-OPS provider (stations, predictions, observations)
- [ ] Discovery tools (tides_status, tides_capabilities)
- [ ] Station discovery tools (list, describe, find_nearest)
- [ ] Prediction tools (tides_predict)
- [ ] Observation tools (tides_observations, tides_latest)
- [ ] Test suite with 90%+ coverage
- [ ] README, ARCHITECTURE, SPEC documentation

## v0.2.0 — Analysis & Flood Risk

Core analysis and flood risk assessment capabilities.

- [ ] Threshold exceedance analysis (tides_threshold_exceedance)
- [ ] Flood projection with SLR scenarios (tides_project_flooding)
- [ ] Flooding calendar generation (tides_flooding_calendar)
- [ ] NOAA flood outlook integration (tides_flood_outlook)
- [ ] Extreme levels lookup (tides_extreme_levels)
- [ ] Sea level trend analysis (tides_sea_level_trend)
- [ ] Artifact storage for time series data

## v0.3.0 — Harmonic Engine & UK Providers

Local harmonic predictions and UK data sources.

- [ ] utide integration for harmonic analysis (tides_harmonic_analysis)
- [ ] Local prediction engine (tides_predict_local)
- [ ] Constituent storage and retrieval
- [ ] Residual computation (tides_residual)
- [ ] UK Environment Agency provider
- [ ] UKHO Admiralty provider (Discovery tier)
- [ ] Cross-provider station search

## v0.4.0 — Production Hardening

Performance, reliability, and deployment.

- [ ] Response caching with configurable TTL
- [ ] Rate limiting per provider
- [ ] Retry logic with exponential backoff
- [ ] Docker container and Fly.io deployment
- [ ] Example scripts and demos
- [ ] PyPI publication

## v0.5.0 — Extended Capabilities

Future enhancements beyond the core 18 tools.

- [ ] Tidal current predictions (NOAA current stations)
- [ ] Global tide models (FES2014 / TPXO)
- [ ] Surge probability (extreme value analysis, return periods)
- [ ] Multi-station interpolation (co-tidal charts)
- [ ] InSAR integration (ground subsidence from Sentinel-1)
