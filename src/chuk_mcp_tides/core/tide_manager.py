"""
TideManager — central orchestrator for chuk-mcp-tides.

Dispatches requests to the appropriate provider, manages caching,
and handles artifact storage for time series data.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import OrderedDict
from datetime import date, datetime, timezone
from typing import Any

import numpy as np

from ..constants import (
    DEFAULT_CACHE_TTL_SECONDS,
    DEFAULT_CURRENT_PREDICTION_DAYS,
    DEFAULT_OBSERVATION_DAYS,
    DEFAULT_PREDICTION_DAYS,
    DEFAULT_PROJECTION_SCENARIOS,
    DEFAULT_PROJECTION_YEARS,
    DEFAULT_SEARCH_RADIUS_KM,
    PROVIDER_DEFAULT_DATUMS,
    REFERENCE_CACHE_TTL,
    SLR_BASELINE_YEAR,
    SLR_SCENARIOS,
    SURGE_THRESHOLD_M,
    Datum,
    EnvVar,
    TideProvider,
)
from ..providers.base import BaseTideProvider
from .reference_cache import ReferenceCache
from .utils import (
    add_days,
    format_date_iso,
    format_date_noaa,
    haversine_km,
    parse_date,
)

logger = logging.getLogger(__name__)

# Max cache entries
_MAX_CACHE = 500


class TideManager:
    """Central orchestrator for tide data operations."""

    def __init__(
        self,
        default_provider: TideProvider | None = None,
        artifact_store: Any | None = None,
    ) -> None:
        provider_env = os.environ.get(EnvVar.DEFAULT_PROVIDER)
        if default_provider is not None:
            self._default_provider = default_provider
        elif provider_env:
            try:
                self._default_provider = TideProvider(provider_env.lower())
            except ValueError:
                self._default_provider = TideProvider.NOAA
        else:
            self._default_provider = TideProvider.NOAA

        # Ensure we always have an artifact store (default: in-memory)
        if artifact_store is not None:
            self._artifact_store = artifact_store
        else:
            from chuk_artifacts import ArtifactStore

            self._artifact_store = ArtifactStore()
        self._cache: OrderedDict[str, tuple[object, float]] = OrderedDict()
        self._cache_lock = threading.Lock()
        self._cache_ttl = int(os.environ.get(EnvVar.CACHE_TTL, str(DEFAULT_CACHE_TTL_SECONDS)))
        self._ref_cache = ReferenceCache(artifact_store=self._artifact_store)
        self._providers: dict[TideProvider, BaseTideProvider] = {}

    # ── Provider Management ─────────────────────────────────────────────────

    @property
    def default_provider(self) -> TideProvider:
        return self._default_provider

    def resolve_provider(self, provider: str | None) -> TideProvider:
        """Resolve a provider name string to a TideProvider enum."""
        if provider is None:
            return self._default_provider
        if provider == "all":
            return self._default_provider  # caller handles cross-provider
        try:
            return TideProvider(provider.lower())
        except ValueError:
            logger.warning(f"Unknown provider '{provider}', falling back to default")
            return self._default_provider

    def _get_provider(self, tp: TideProvider) -> BaseTideProvider:
        """Lazy-load and cache a provider instance."""
        if tp not in self._providers:
            if tp == TideProvider.NOAA:
                from ..providers.noaa import NOAAProvider

                self._providers[tp] = NOAAProvider()
            elif tp == TideProvider.EA:
                from ..providers.ea import EAProvider

                self._providers[tp] = EAProvider()
            elif tp == TideProvider.UKHO:
                from ..providers.ukho import UKHOProvider

                self._providers[tp] = UKHOProvider()
            elif tp == TideProvider.LOCAL:
                from ..providers.local import LocalProvider
                from .constituent_storage import ConstituentStorage

                storage = ConstituentStorage(artifact_store=self._artifact_store)
                self._providers[tp] = LocalProvider(constituent_storage=storage)
        return self._providers[tp]

    def default_datum(self, tp: TideProvider) -> str:
        """Get the default datum for a provider."""
        return PROVIDER_DEFAULT_DATUMS.get(tp, Datum.MSL).value

    async def warm_cache(self) -> int:
        """Pre-load the reference data index from the artifact store.

        Call once at startup.  Returns the number of cached artifacts found.
        Non-blocking, non-fatal if the artifact store is unavailable.
        """
        return await self._ref_cache.warm()

    # ── Caching ─────────────────────────────────────────────────────────────

    def _cache_key(self, *parts: str) -> str:
        return "|".join(str(p) for p in parts)

    def get_cached(self, key: str) -> object | None:
        with self._cache_lock:
            if key in self._cache:
                value, ts = self._cache[key]
                if time.time() - ts < self._cache_ttl:
                    self._cache.move_to_end(key)
                    return value
                del self._cache[key]
        return None

    def set_cached(self, key: str, value: object) -> None:
        with self._cache_lock:
            self._cache[key] = (value, time.time())
            if len(self._cache) > _MAX_CACHE:
                self._cache.popitem(last=False)

    # ── Station Operations ──────────────────────────────────────────────────

    async def list_stations(
        self,
        provider: TideProvider,
        lat: float | None = None,
        lon: float | None = None,
        radius_km: float = DEFAULT_SEARCH_RADIUS_KM,
        region: str | None = None,
        station_type: str | None = None,
        max_results: int = 20,
    ) -> list[dict]:
        cache_key = self._cache_key(
            "stations",
            provider.value,
            str(lat),
            str(lon),
            str(radius_km),
            str(region),
            str(station_type),
            str(max_results),
        )
        cached = self.get_cached(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        ref_ttl = REFERENCE_CACHE_TTL["stations"]
        ref_cached = await self._ref_cache.get(cache_key, ref_ttl)
        if ref_cached is not None:
            self.set_cached(cache_key, ref_cached)
            return ref_cached

        p = self._get_provider(provider)
        stations = await p.list_stations(
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            region=region,
            station_type=station_type,
            max_results=max_results,
        )
        self.set_cached(cache_key, stations)
        await self._ref_cache.put(cache_key, stations, ref_ttl)
        return stations

    async def get_station_detail(
        self,
        station_id: str,
        provider: TideProvider,
    ) -> dict:
        cache_key = self._cache_key("detail", provider.value, station_id)
        cached = self.get_cached(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        ref_ttl = REFERENCE_CACHE_TTL["detail"]
        ref_cached = await self._ref_cache.get(cache_key, ref_ttl)
        if ref_cached is not None:
            self.set_cached(cache_key, ref_cached)
            return ref_cached

        p = self._get_provider(provider)
        detail = await p.get_station_detail(station_id)
        self.set_cached(cache_key, detail)
        await self._ref_cache.put(cache_key, detail, ref_ttl)
        return detail

    async def find_nearest(
        self,
        lat: float,
        lon: float,
        providers: list[TideProvider] | None = None,
        max_results: int = 5,
    ) -> list[dict]:
        if providers is None:
            providers = [TideProvider.NOAA, TideProvider.EA, TideProvider.UKHO]

        all_stations: list[dict] = []
        for tp in providers:
            try:
                p = self._get_provider(tp)
                stations = await p.list_stations(
                    lat=lat,
                    lon=lon,
                    radius_km=500,
                    max_results=100,
                )
                for s in stations:
                    s["provider"] = tp.value
                    s["distance_km"] = haversine_km(lat, lon, s["lat"], s["lon"])
                all_stations.extend(stations)
            except Exception as e:
                logger.warning(f"Failed to query {tp.value}: {e}")

        all_stations.sort(key=lambda s: s["distance_km"])
        return all_stations[:max_results]

    # ── Predictions ─────────────────────────────────────────────────────────

    async def get_predictions(
        self,
        station_id: str,
        provider: TideProvider,
        start_date: str = "today",
        end_date: str | None = None,
        interval: str = "hilo",
        datum: str | None = None,
        units: str = "metric",
    ) -> dict:
        start = parse_date(start_date)
        end = parse_date(end_date) if end_date else add_days(start, DEFAULT_PREDICTION_DAYS)
        d = datum or self.default_datum(provider)

        cache_key = self._cache_key(
            "pred",
            provider.value,
            station_id,
            format_date_iso(start),
            format_date_iso(end),
            interval,
            d,
            units,
        )
        cached = self.get_cached(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        p = self._get_provider(provider)
        result = await p.get_predictions(
            station_id,
            start_date=format_date_noaa(start),
            end_date=format_date_noaa(end),
            datum=d,
            units=units,
            interval=interval,
        )

        out = {
            "station_id": station_id,
            "provider": provider.value,
            "datum": d,
            "units": units,
            "start_date": format_date_iso(start),
            "end_date": format_date_iso(end),
            "interval": interval,
            "predictions": result,
        }
        self.set_cached(cache_key, out)
        return out

    async def predict_local(
        self,
        start_date: str,
        end_date: str,
        station_id: str | None = None,
        constituents: dict | None = None,
        interval_minutes: int = 60,
        datum_offset: float = 0.0,
    ) -> dict:
        p = self._get_provider(TideProvider.LOCAL)
        return await p.predict_from_constituents(  # type: ignore[attr-defined]
            station_id=station_id,
            constituents=constituents,
            start_date=start_date,
            end_date=end_date,
            interval_minutes=interval_minutes,
            datum_offset=datum_offset,
        )

    # ── Observations ────────────────────────────────────────────────────────

    async def get_observations(
        self,
        station_id: str,
        provider: TideProvider,
        start_date: str = "today",
        end_date: str | None = None,
        product: str = "water_level",
        datum: str | None = None,
        units: str = "metric",
    ) -> dict:
        start = parse_date(start_date)
        end = parse_date(end_date) if end_date else add_days(start, DEFAULT_OBSERVATION_DAYS)
        d = datum or self.default_datum(provider)

        cache_key = self._cache_key(
            "obs",
            provider.value,
            station_id,
            format_date_iso(start),
            format_date_iso(end),
            product,
            d,
            units,
        )
        cached = self.get_cached(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        p = self._get_provider(provider)
        result = await p.get_observations(
            station_id,
            start_date=format_date_noaa(start),
            end_date=format_date_noaa(end),
            datum=d,
            units=units,
            product=product,
        )

        out = {
            "station_id": station_id,
            "provider": provider.value,
            "datum": d,
            "units": units,
            "product": product,
            "start_date": format_date_iso(start),
            "end_date": format_date_iso(end),
            "readings": result,
        }
        self.set_cached(cache_key, out)
        return out

    async def get_latest(
        self,
        station_id: str,
        provider: TideProvider,
        datum: str | None = None,
    ) -> dict:
        d = datum or self.default_datum(provider)
        p = self._get_provider(provider)
        return await p.get_latest(
            station_id,
            datum=d,
        )

    # ── Analysis: Threshold Exceedance ──────────────────────────────────────

    async def threshold_exceedance(
        self,
        station_id: str,
        threshold: float,
        start_date: str,
        end_date: str,
        provider: TideProvider,
        source: str = "predictions",
        datum: str | None = None,
        group_by: str = "year",
    ) -> dict:
        d = datum or self.default_datum(provider)
        start = parse_date(start_date)
        end = parse_date(end_date)

        # Fetch data in yearly chunks
        all_events: list[dict] = []
        current = start
        while current <= end:
            chunk_end = min(
                date(current.year, 12, 31),
                end,
            )
            if source == "predictions":
                data = await self.get_predictions(
                    station_id,
                    provider,
                    start_date=format_date_iso(current),
                    end_date=format_date_iso(chunk_end),
                    interval="6min",
                    datum=d,
                    units="metric",
                )
                all_events.extend(data["predictions"])
            else:
                data = await self.get_observations(
                    station_id,
                    provider,
                    start_date=format_date_iso(current),
                    end_date=format_date_iso(chunk_end),
                    datum=d,
                    units="metric",
                )
                all_events.extend(data["readings"])
            current = date(current.year + 1, 1, 1)

        return self._compute_exceedance(
            all_events,
            threshold,
            d,
            source,
            group_by,
            format_date_iso(start),
            format_date_iso(end),
        )

    def _compute_exceedance(
        self,
        events: list[dict],
        threshold: float,
        datum: str,
        source: str,
        group_by: str,
        start_date: str,
        end_date: str,
    ) -> dict:
        """Compute threshold exceedance from a list of events/readings."""
        groups: dict[str, dict] = {}
        total_count = 0
        total_hours = 0.0

        # Determine time step from source
        step_hours = 0.1  # 6-min for predictions

        for ev in events:
            height = ev.get("height", ev.get("value", 0.0))
            dt_str = ev.get("datetime", ev.get("t", ""))
            if height is None or height <= threshold:
                continue

            total_count += 1
            total_hours += step_hours

            # Group key
            if group_by == "year" and len(dt_str) >= 4:
                key = dt_str[:4]
            elif group_by == "month" and len(dt_str) >= 7:
                key = dt_str[:7]
            elif group_by == "season" and len(dt_str) >= 7:
                month = int(dt_str[5:7])
                if month in (12, 1, 2):
                    key = f"Winter {dt_str[:4]}"
                elif month in (3, 4, 5):
                    key = f"Spring {dt_str[:4]}"
                elif month in (6, 7, 8):
                    key = f"Summer {dt_str[:4]}"
                else:
                    key = f"Autumn {dt_str[:4]}"
            else:
                key = "all"

            if key not in groups:
                groups[key] = {"count": 0, "max_height": 0.0, "total_hours": 0.0}
            groups[key]["count"] += 1
            groups[key]["max_height"] = max(groups[key]["max_height"], height)
            groups[key]["total_hours"] += step_hours

        group_list = [
            {
                "period": k,
                "count": v["count"],
                "max_height": round(v["max_height"], 4),
                "total_hours": round(v["total_hours"], 2),
            }
            for k, v in sorted(groups.items())
        ]

        # Compute trend if enough groups
        trend = None
        if len(group_list) > 2 and group_by == "year":
            try:
                years = np.array([int(g["period"]) for g in group_list], dtype=float)
                counts = np.array([g["count"] for g in group_list], dtype=float)
                if len(years) > 1:
                    coeffs = np.polyfit(years, counts, 1)
                    predicted = np.polyval(coeffs, years)
                    ss_res = np.sum((counts - predicted) ** 2)
                    ss_tot = np.sum((counts - np.mean(counts)) ** 2)
                    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
                    trend = {
                        "slope": round(float(coeffs[0]), 4),
                        "intercept": round(float(coeffs[1]), 4),
                        "r_squared": round(float(r2), 4),
                    }
            except Exception:
                pass

        return {
            "threshold": threshold,
            "datum": datum,
            "source": source,
            "total_exceedances": total_count,
            "total_hours_above": round(total_hours, 2),
            "groups": group_list,
            "trend": trend,
        }

    # ── Analysis: Flood Projection ──────────────────────────────────────────

    async def project_flooding(
        self,
        station_id: str,
        threshold: float,
        provider: TideProvider,
        years: list[int] | None = None,
        scenarios: list[str] | None = None,
        datum: str | None = None,
    ) -> dict:
        d = datum or self.default_datum(provider)
        proj_years = years or DEFAULT_PROJECTION_YEARS
        proj_scenarios = scenarios or DEFAULT_PROJECTION_SCENARIOS

        # Get baseline: most recent full year of predictions
        now = datetime.now(timezone.utc)
        baseline_year = now.year - 1
        baseline_start = format_date_iso(date(baseline_year, 1, 1))
        baseline_end = format_date_iso(date(baseline_year, 12, 31))

        baseline = await self.threshold_exceedance(
            station_id,
            threshold,
            baseline_start,
            baseline_end,
            provider,
            source="predictions",
            datum=d,
            group_by="none",
        )
        baseline_count = baseline["total_exceedances"]

        # Get station detail for name and SLR trend
        station_name = station_id
        try:
            detail = await self.get_station_detail(station_id, provider)
            station_name = detail.get("name", station_id)
        except Exception:
            pass

        # For each scenario+year, compute effective threshold lowered by SLR
        projections = []
        for scenario in proj_scenarios:
            if scenario not in SLR_SCENARIOS:
                continue
            rate = SLR_SCENARIOS[scenario]["rate_mm_yr"]
            for yr in proj_years:
                slr_mm = rate * (yr - SLR_BASELINE_YEAR)
                effective_threshold = threshold - (slr_mm / 1000.0)
                # Count baseline predictions that exceed the lower threshold
                count = self._count_above(baseline.get("_raw_events", []), effective_threshold)
                # If no raw events cached, estimate from baseline proportionally
                if count == 0 and baseline_count > 0:
                    base_slr_mm = rate * (baseline_year - SLR_BASELINE_YEAR)
                    additional_slr_m = (slr_mm - base_slr_mm) / 1000.0
                    # Simple linear scaling approximation
                    scale = max(1.0, 1.0 + additional_slr_m * 20)
                    count = int(baseline_count * scale)

                projections.append(
                    {
                        "year": yr,
                        "scenario": scenario,
                        "slr_mm": round(slr_mm, 1),
                        "projected_exceedances": count,
                        "projected_hours": round(count * 0.1, 2),
                        "delta_from_baseline": count - baseline_count,
                    }
                )

        # Tipping points
        tipping_points = []
        for scenario in proj_scenarios:
            if scenario not in SLR_SCENARIOS:
                continue
            scenario_projs = [p for p in projections if p["scenario"] == scenario]
            tp: dict[str, str | int | None] = {
                "scenario": scenario,
                "double_year": None,
                "tenfold_year": None,
                "daily_year": None,
            }
            for p in scenario_projs:
                if tp["double_year"] is None and p["projected_exceedances"] >= baseline_count * 2:
                    tp["double_year"] = p["year"]
                if tp["tenfold_year"] is None and p["projected_exceedances"] >= baseline_count * 10:
                    tp["tenfold_year"] = p["year"]
                if tp["daily_year"] is None and p["projected_exceedances"] >= 365:
                    tp["daily_year"] = p["year"]
            tipping_points.append(tp)

        return {
            "station_id": station_id,
            "station_name": station_name,
            "threshold": threshold,
            "datum": d,
            "baseline_year": baseline_year,
            "baseline_exceedances": baseline_count,
            "projections": projections,
            "tipping_points": tipping_points,
        }

    def _count_above(self, events: list[dict], threshold: float) -> int:
        count = 0
        for ev in events:
            h = ev.get("height", ev.get("value", 0.0))
            if h is not None and h > threshold:
                count += 1
        return count

    # ── Analysis: Harmonic ──────────────────────────────────────────────────

    async def harmonic_analysis(
        self,
        station_id: str,
        start_date: str,
        end_date: str,
        provider: TideProvider,
        store_constituents: bool = True,
    ) -> dict:
        # Fetch observations
        obs = await self.get_observations(
            station_id,
            provider,
            start_date=start_date,
            end_date=end_date,
            product="water_level",
        )

        readings = obs["readings"]
        if len(readings) < 30 * 24:  # roughly 30 days of hourly data
            raise ValueError(
                f"Harmonic analysis requires ≥30 days of observations. "
                f"Got {len(readings)} readings."
            )

        # Get station lat for utide
        detail = await self.get_station_detail(station_id, provider)
        lat = detail.get("lat", 0.0)

        # Delegate to local provider
        # EA returns "time" key, NOAA returns "datetime" — handle both.
        # analyze_harmonics expects datetime objects sorted ascending.
        local = self._get_provider(TideProvider.LOCAL)

        # Parse timestamps and pair with heights
        pairs = []
        for r in readings:
            raw_t = r.get("datetime", r.get("time", ""))
            t = (
                datetime.fromisoformat(raw_t.replace("Z", "+00:00"))
                if isinstance(raw_t, str)
                else raw_t
            )
            pairs.append((t, float(r["value"])))

        # Sort ascending by time (EA returns descending)
        pairs.sort(key=lambda p: p[0])
        times = [p[0] for p in pairs]
        heights = [p[1] for p in pairs]

        return await local.analyze_harmonics(  # type: ignore[attr-defined]
            times,
            heights,
            lat,
            station_id=station_id,
            store=store_constituents,
        )

    # ── Analysis: Residual ──────────────────────────────────────────────────

    async def compute_residual(
        self,
        station_id: str,
        start_date: str,
        end_date: str,
        provider: TideProvider,
        datum: str | None = None,
    ) -> dict:
        d = datum or self.default_datum(provider)

        # Fetch both observations and predictions
        obs_data = await self.get_observations(
            station_id,
            provider,
            start_date=start_date,
            end_date=end_date,
            datum=d,
            product="water_level",
        )
        pred_data = await self.get_predictions(
            station_id,
            provider,
            start_date=start_date,
            end_date=end_date,
            interval="6min",
            datum=d,
        )

        # Build prediction lookup by datetime
        pred_lookup: dict[str, float] = {}
        for p in pred_data["predictions"]:
            pred_lookup[p["datetime"]] = p["height"]

        residuals = []
        max_pos = {"peak_datetime": "", "peak_residual": -999.0}
        max_neg = {"peak_datetime": "", "peak_residual": 999.0}
        surge_events: list[dict] = []
        current_surge: dict | None = None

        for r in obs_data["readings"]:
            dt = r["datetime"]
            obs_val = r["value"]
            # Find closest prediction
            pred_val = pred_lookup.get(dt)
            if pred_val is None:
                # Try matching by truncating to 6-min
                continue

            residual = obs_val - pred_val
            residuals.append(
                {
                    "datetime": dt,
                    "observed": obs_val,
                    "predicted": pred_val,
                    "residual": round(residual, 4),
                }
            )

            if residual > max_pos["peak_residual"]:
                max_pos = {"peak_datetime": dt, "peak_residual": round(residual, 4)}
            if residual < max_neg["peak_residual"]:
                max_neg = {"peak_datetime": dt, "peak_residual": round(residual, 4)}

            # Track surge events
            if abs(residual) > SURGE_THRESHOLD_M:
                if current_surge is None:
                    current_surge = {
                        "start": dt,
                        "peak_datetime": dt,
                        "peak_residual": residual,
                    }
                elif abs(residual) > abs(current_surge["peak_residual"]):
                    current_surge["peak_datetime"] = dt
                    current_surge["peak_residual"] = residual
            elif current_surge is not None:
                current_surge["end"] = dt
                current_surge["peak_residual"] = round(current_surge["peak_residual"], 4)
                surge_events.append(current_surge)
                current_surge = None

        if current_surge is not None:
            current_surge["peak_residual"] = round(current_surge["peak_residual"], 4)
            surge_events.append(current_surge)

        residual_values = [r["residual"] for r in residuals]
        mean_res = float(np.mean(residual_values)) if residual_values else 0.0
        std_res = float(np.std(residual_values)) if residual_values else 0.0

        return {
            "station_id": station_id,
            "reading_count": len(residuals),
            "max_positive_surge": max_pos,
            "max_negative_surge": max_neg,
            "mean_residual": round(mean_res, 4),
            "std_residual": round(std_res, 4),
            "surge_events": surge_events,
            "residuals": residuals,
        }

    # ── Analysis: Sea Level Trend ───────────────────────────────────────────

    async def get_sea_level_trend(
        self,
        station_id: str,
        provider: TideProvider,
    ) -> dict:
        ref_key = self._cache_key("trend", station_id)
        ref_ttl = REFERENCE_CACHE_TTL["trend"]
        cached = await self._ref_cache.get(ref_key, ref_ttl)
        if cached is not None:
            return cached

        p = self._get_provider(provider)
        if hasattr(p, "get_sea_level_trend"):
            result = await p.get_sea_level_trend(station_id)  # type: ignore[attr-defined]
            await self._ref_cache.put(ref_key, result, ref_ttl)
            return result
        raise NotImplementedError(f"Sea level trends not available from {provider.value}")

    # ── Analysis: Extreme Levels ────────────────────────────────────────────

    async def get_extreme_levels(
        self,
        station_id: str,
        provider: TideProvider,
        datum: str | None = None,
    ) -> dict:
        d = datum or self.default_datum(provider)
        ref_key = self._cache_key("extremes", station_id, d)
        ref_ttl = REFERENCE_CACHE_TTL["extremes"]
        cached = await self._ref_cache.get(ref_key, ref_ttl)
        if cached is not None:
            return cached

        p = self._get_provider(provider)
        if hasattr(p, "get_extremes"):
            result = await p.get_extremes(station_id, datum=d)  # type: ignore[attr-defined]
            await self._ref_cache.put(ref_key, result, ref_ttl)
            return result
        raise NotImplementedError(f"Extreme levels not available from {provider.value}")

    # ── Flood: Outlook ──────────────────────────────────────────────────────

    async def get_flood_outlook(
        self,
        station_id: str,
        product: str = "annual",
        threshold: str = "minor",
    ) -> dict:
        ref_key = self._cache_key("flood", station_id, product, threshold)
        ref_ttl = REFERENCE_CACHE_TTL["flood"]
        cached = await self._ref_cache.get(ref_key, ref_ttl)
        if cached is not None:
            return cached

        p = self._get_provider(TideProvider.NOAA)
        if hasattr(p, "get_flood_outlook"):
            result = await p.get_flood_outlook(  # type: ignore[attr-defined]
                station_id,
                product=product,
                threshold=threshold,
            )
            await self._ref_cache.put(ref_key, result, ref_ttl)
            return result
        raise NotImplementedError("Flood outlook is NOAA-only")

    # ── Flood: Calendar ─────────────────────────────────────────────────────

    async def flooding_calendar(
        self,
        station_id: str,
        threshold: float,
        provider: TideProvider,
        year: int | None = None,
        slr_offset_mm: float = 0.0,
        datum: str | None = None,
    ) -> dict:
        d = datum or self.default_datum(provider)
        yr = year or datetime.now(timezone.utc).year
        effective_threshold = threshold - (slr_offset_mm / 1000.0)

        # Fetch full year of hi/lo predictions
        start = format_date_iso(date(yr, 1, 1))
        end = format_date_iso(date(yr, 12, 31))

        pred_data = await self.get_predictions(
            station_id,
            provider,
            start_date=start,
            end_date=end,
            interval="hilo",
            datum=d,
        )

        # Process predictions into flood days
        flood_days: dict[str, dict] = {}
        monthly: dict[int, dict] = {
            m: {"flood_days": set(), "max_height": 0.0, "total_hours": 0.0} for m in range(1, 13)
        }

        for ev in pred_data["predictions"]:
            height = ev["height"]
            if height <= effective_threshold:
                continue

            dt_str = ev["datetime"]
            day = dt_str[:10]
            month = int(dt_str[5:7])

            if day not in flood_days:
                flood_days[day] = {
                    "date": day,
                    "peak_height": height,
                    "duration_hours": 2.0,  # approximate half-tide duration
                    "tides_above": 0,
                }
            fd = flood_days[day]
            fd["tides_above"] += 1
            fd["peak_height"] = max(fd["peak_height"], height)
            fd["duration_hours"] += 2.0

            monthly[month]["flood_days"].add(day)
            monthly[month]["max_height"] = max(monthly[month]["max_height"], height)
            monthly[month]["total_hours"] += 2.0

        flood_day_list = sorted(flood_days.values(), key=lambda d: d["date"])
        total_hours = sum(d["duration_hours"] for d in flood_day_list)

        monthly_summary = []
        for m in range(1, 13):
            monthly_summary.append(
                {
                    "month": m,
                    "flood_days": len(monthly[m]["flood_days"]),
                    "max_height": round(monthly[m]["max_height"], 4),
                    "total_hours": round(monthly[m]["total_hours"], 2),
                }
            )

        return {
            "station_id": station_id,
            "year": yr,
            "threshold": threshold,
            "slr_offset_mm": slr_offset_mm,
            "datum": d,
            "total_flood_days": len(flood_days),
            "total_flood_hours": round(total_hours, 2),
            "monthly_summary": monthly_summary,
            "flood_days": flood_day_list,
        }

    # ── Currents ─────────────────────────────────────────────────────────────

    async def list_current_stations(
        self,
        lat: float | None = None,
        lon: float | None = None,
        radius_km: float = DEFAULT_SEARCH_RADIUS_KM,
        region: str | None = None,
        max_results: int = 20,
    ) -> list[dict]:
        """List NOAA tidal current prediction stations."""
        cache_key = self._cache_key(
            "current_stations",
            str(lat),
            str(lon),
            str(radius_km),
            str(region),
            str(max_results),
        )
        cached = self.get_cached(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        ref_ttl = REFERENCE_CACHE_TTL.get("current_stations", 86_400)
        ref_cached = await self._ref_cache.get(cache_key, ref_ttl)
        if ref_cached is not None:
            self.set_cached(cache_key, ref_cached)
            return ref_cached

        p = self._get_provider(TideProvider.NOAA)
        if not hasattr(p, "list_current_stations"):
            raise NotImplementedError("Current stations are NOAA-only")
        stations = await p.list_current_stations(  # type: ignore[attr-defined]
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            region=region,
            max_results=max_results,
        )
        self.set_cached(cache_key, stations)
        await self._ref_cache.put(cache_key, stations, ref_ttl)
        return stations

    async def get_current_predictions(
        self,
        station_id: str,
        start_date: str = "today",
        end_date: str | None = None,
        interval: str = "MAX_SLACK",
        units: str = "metric",
        bin: str = "1",
    ) -> dict:
        """Get tidal current predictions for a station (NOAA only)."""
        start = parse_date(start_date)
        end = parse_date(end_date) if end_date else add_days(start, DEFAULT_CURRENT_PREDICTION_DAYS)

        cache_key = self._cache_key(
            "curr_pred",
            station_id,
            format_date_iso(start),
            format_date_iso(end),
            interval,
            units,
            bin,
        )
        cached = self.get_cached(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        p = self._get_provider(TideProvider.NOAA)
        if not hasattr(p, "get_current_predictions"):
            raise NotImplementedError("Current predictions are NOAA-only")
        result = await p.get_current_predictions(  # type: ignore[attr-defined]
            station_id,
            start_date=format_date_noaa(start),
            end_date=format_date_noaa(end),
            units=units,
            interval=interval,
            bin=bin,
        )

        out = {
            "station_id": station_id,
            "provider": "noaa",
            "units": "cm/s",
            "start_date": format_date_iso(start),
            "end_date": format_date_iso(end),
            "interval": interval,
            "predictions": result,
        }
        self.set_cached(cache_key, out)
        return out

    async def get_current_latest(
        self,
        station_id: str,
        bin: str = "1",
    ) -> dict:
        """Get the most recent current observation (NOAA only)."""
        p = self._get_provider(TideProvider.NOAA)
        if not hasattr(p, "get_current_latest"):
            raise NotImplementedError("Current observations are NOAA-only")
        return await p.get_current_latest(  # type: ignore[attr-defined]
            station_id,
            bin=bin,
        )

    # ── Tide State ──────────────────────────────────────────────────────────

    def determine_tide_state(
        self,
        current_value: float,
        predictions: list[dict],
        current_time: str,
    ) -> tuple[str, dict | None, dict | None]:
        """Determine tide state (rising/falling) and next high/low."""
        next_high = None
        next_low = None

        for p in predictions:
            if p["datetime"] <= current_time:
                continue
            etype = p.get("event_type", "")
            if "high" in etype.lower() and next_high is None:
                next_high = p
            elif "low" in etype.lower() and next_low is None:
                next_low = p
            if next_high and next_low:
                break

        # Determine state
        if next_high and next_low:
            if next_high["datetime"] < next_low["datetime"]:
                state = "rising"
            else:
                state = "falling"
        elif next_high:
            state = "rising"
        elif next_low:
            state = "falling"
        else:
            state = "unknown"

        return state, next_high, next_low
