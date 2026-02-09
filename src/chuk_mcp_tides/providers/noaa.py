"""
NOAA CO-OPS tide data provider.

Implements the BaseTideProvider interface for the NOAA
Tides & Currents API (tidesandcurrents.noaa.gov).

Endpoints used:
  - Metadata API (mdapi):  stations list, station detail
  - Data API (datagetter): predictions, water levels, high/low, monthly mean
  - Derived Products API (dpapi): sea-level trends, high-tide flooding
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import httpx

from ..core.http_client import ResilientClient
from ..core.utils import haversine_km
from .base import BaseTideProvider

logger = logging.getLogger(__name__)

# ─── API base URLs ────────────────────────────────────────────────────────────

_METADATA_BASE = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi"
_DATA_BASE = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
_DERIVED_BASE = "https://api.tidesandcurrents.noaa.gov/dpapi/prod/webapi"

# ─── Mapping tables ──────────────────────────────────────────────────────────

_INTERVAL_MAP: dict[str, str] = {
    "hilo": "hilo",
    "hourly": "h",
    "6min": "6",
    "1min": "1",
}

_UNITS_MAP: dict[str, str] = {
    "metric": "metric",
    "english": "english",
}

_EVENT_TYPE_MAP: dict[str, str] = {
    "H": "high",
    "L": "low",
    "HH": "higher_high",
    "HL": "high",      # alias used in some edge cases
    "LL": "lower_low",
    "LH": "low",       # alias used in some edge cases
}

_TIMEOUT = 30.0


class NOAAProvider(BaseTideProvider):
    """NOAA CO-OPS API client.

    Uses a shared ``ResilientClient`` for connection pooling, retry
    with exponential backoff, and rate limiting.
    """

    def __init__(self) -> None:
        self._http = ResilientClient(timeout=_TIMEOUT, rate_limit=5.0)

    # ─── Error handling ───────────────────────────────────────────────────

    @staticmethod
    def _check_error(data: dict[str, Any]) -> None:
        """Raise ``ValueError`` if the NOAA response carries an error payload."""
        if "error" in data:
            err = data["error"]
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            raise ValueError(f"NOAA API error: {msg}")

    # ─── Internal helpers ─────────────────────────────────────────────────

    @staticmethod
    def _resolve_interval(interval: str | None) -> str:
        """Map a user-facing interval name to the NOAA query-string value."""
        if interval is None:
            return "hilo"
        return _INTERVAL_MAP.get(interval, interval)

    @staticmethod
    def _resolve_units(units: str | None) -> str:
        """Map a user-facing units name to the NOAA query-string value."""
        if units is None:
            return "metric"
        return _UNITS_MAP.get(units, units)

    @staticmethod
    def _normalize_station(raw: dict[str, Any]) -> dict[str, Any]:
        """Convert a raw NOAA station record to a normalized dict."""
        return {
            "station_id": str(raw.get("id", raw.get("stationId", ""))),
            "name": raw.get("name", ""),
            "lat": float(raw.get("lat", 0.0)),
            "lon": float(raw.get("lng", raw.get("lon", 0.0))),
            "state": raw.get("state", None),
            "station_type": raw.get("type", raw.get("stationType", None)),
            "provider": "noaa",
        }

    @staticmethod
    def _date_str(d: date) -> str:
        """Format a ``date`` as YYYYMMDD for the NOAA API."""
        return d.strftime("%Y%m%d")

    @staticmethod
    def _default_dates(
        start_date: str | None,
        end_date: str | None,
        default_days: int = 7,
    ) -> tuple[str, str]:
        """Return (begin_date, end_date) in YYYYMMDD, applying defaults."""
        today = date.today()
        if start_date is None:
            begin = today
        else:
            begin = date(int(start_date[:4]), int(start_date[4:6]), int(start_date[6:8]))
        if end_date is None:
            end = begin + timedelta(days=default_days)
        else:
            end = date(int(end_date[:4]), int(end_date[4:6]), int(end_date[6:8]))
        return begin.strftime("%Y%m%d"), end.strftime("%Y%m%d")

    # ─── BaseTideProvider: list_stations ──────────────────────────────────

    async def list_stations(self, **kwargs: object) -> list[dict[str, object]]:
        """List NOAA tide prediction stations.

        Supported kwargs
        ----------------
        lat, lon, radius_km : proximity filter
        region              : US state abbreviation (e.g. "NY")
        station_type        : filter by station type string
        max_results         : cap the number of returned stations
        """
        url = f"{_METADATA_BASE}/stations.json"
        params: dict[str, str] = {"type": "tidepredictions"}

        resp = await self._http.get(url, params=params)
        data = resp.json()

        self._check_error(data)

        raw_stations: list[dict[str, Any]] = data.get("stations", [])
        stations = [self._normalize_station(s) for s in raw_stations]

        # ── Filters ──────────────────────────────────────────────────────

        region = kwargs.get("region")
        if region:
            region_upper = str(region).upper()
            stations = [
                s for s in stations
                if (s.get("state") or "").upper() == region_upper
            ]

        station_type = kwargs.get("station_type")
        if station_type:
            st_lower = str(station_type).lower()
            stations = [
                s for s in stations
                if (s.get("station_type") or "").lower() == st_lower
            ]

        lat = kwargs.get("lat")
        lon = kwargs.get("lon")
        radius_km = kwargs.get("radius_km")
        if lat is not None and lon is not None:
            lat_f = float(str(lat))
            lon_f = float(str(lon))
            r_km = float(str(radius_km)) if radius_km is not None else 50.0
            filtered: list[dict[str, Any]] = []
            for s in stations:
                dist = haversine_km(lat_f, lon_f, s["lat"], s["lon"])
                if dist <= r_km:
                    s["distance_km"] = round(dist, 2)
                    filtered.append(s)
            stations = sorted(filtered, key=lambda s: s.get("distance_km", 0.0))

        max_results = kwargs.get("max_results")
        if max_results is not None:
            stations = stations[: int(str(max_results))]

        return stations  # type: ignore[return-value]

    # ─── BaseTideProvider: get_station_detail ─────────────────────────────

    async def get_station_detail(self, station_id: str) -> dict[str, object]:
        """Get expanded metadata for a single station."""
        url = f"{_METADATA_BASE}/stations/{station_id}.json"
        params = {
            "expand": "details,datums,harcon,floodlevels,sensors,products",
        }

        resp = await self._http.get(url, params=params)
        data = resp.json()

        self._check_error(data)

        # The detail endpoint wraps the station in a "stations" list of one.
        raw_list = data.get("stations", [data])
        raw: dict[str, Any] = raw_list[0] if raw_list else data

        detail: dict[str, Any] = self._normalize_station(raw)

        # Tidal type
        detail["tidal_type"] = raw.get("tidal_type", raw.get("tidalType", None))

        # Data date range
        details_block = raw.get("details", {})
        if isinstance(details_block, dict):
            dr_start = details_block.get("date_established") or details_block.get("self")
            dr_end = details_block.get("date_removed")
            if dr_start:
                detail["data_range"] = [str(dr_start), str(dr_end) if dr_end else "present"]

        # ── Datums ────────────────────────────────────────────────────────
        datums_block = raw.get("datums", {})
        datum_list: list[dict[str, Any]] = []
        if isinstance(datums_block, dict):
            datum_list = datums_block.get("datums", [])
        elif isinstance(datums_block, list):
            datum_list = datums_block

        detail["datums"] = [
            {
                "name": d.get("name", d.get("n", "")),
                "value": float(d.get("value", d.get("v", 0.0))),
            }
            for d in datum_list
        ]

        # ── Harmonic constituents ─────────────────────────────────────────
        harcon_block = raw.get("harmonicConstituents", raw.get("harcon", {}))
        hc_list: list[dict[str, Any]] = []
        if isinstance(harcon_block, dict):
            hc_list = harcon_block.get("HarmonicConstituents", [])
        elif isinstance(harcon_block, list):
            hc_list = harcon_block

        if hc_list:
            detail["harmonic_constituents"] = [
                {
                    "name": c.get("name", ""),
                    "amplitude": float(c.get("amplitude", 0.0)),
                    "phase": float(c.get("phase_GMT", c.get("phase", 0.0))),
                    "speed": float(c.get("speed", 0.0)),
                }
                for c in hc_list
            ]
        else:
            detail["harmonic_constituents"] = None

        # ── Flood thresholds ──────────────────────────────────────────────
        flood_block = raw.get("floodlevels", raw.get("flood_levels", {}))
        fl_list: list[dict[str, Any]] = []
        if isinstance(flood_block, dict):
            fl_list = flood_block.get("floodlevels", [])
        elif isinstance(flood_block, list):
            fl_list = flood_block

        if fl_list:
            fl = fl_list[0]
            detail["flood_thresholds"] = {
                "minor": _safe_float(fl.get("minor")),
                "moderate": _safe_float(fl.get("moderate")),
                "major": _safe_float(fl.get("major")),
            }
        else:
            detail["flood_thresholds"] = None

        # ── Sensors ───────────────────────────────────────────────────────
        sensors_block = raw.get("sensors", {})
        sensor_list: list[dict[str, Any]] = []
        if isinstance(sensors_block, dict):
            sensor_list = sensors_block.get("sensors", [])
        elif isinstance(sensors_block, list):
            sensor_list = sensors_block

        detail["sensors"] = [
            str(s.get("name", s.get("sensorName", "")))
            for s in sensor_list
        ]

        # ── Products ──────────────────────────────────────────────────────
        products_block = raw.get("products", {})
        product_list: list[dict[str, Any]] = []
        if isinstance(products_block, dict):
            product_list = products_block.get("products", [])
        elif isinstance(products_block, list):
            product_list = products_block

        detail["products"] = [
            str(p.get("name", p.get("productName", "")))
            for p in product_list
        ]

        detail["provider"] = "noaa"
        return detail  # type: ignore[return-value]

    # ─── BaseTideProvider: get_predictions ────────────────────────────────

    async def get_predictions(
        self, station_id: str, **kwargs: object
    ) -> list[dict[str, object]]:
        """Get tidal predictions for a station.

        Supported kwargs
        ----------------
        start_date  : YYYYMMDD  (default: today)
        end_date    : YYYYMMDD  (default: start + 7 days)
        datum       : e.g. "MLLW" (default: "MLLW")
        units       : "metric" | "english" (default: "metric")
        interval    : "hilo" | "hourly" | "6min" | "1min" (default: "hilo")
        """
        begin_date, end_date = self._default_dates(
            kwargs.get("start_date"),  # type: ignore[arg-type]
            kwargs.get("end_date"),    # type: ignore[arg-type]
        )

        datum = str(kwargs.get("datum", "MLLW"))
        units = self._resolve_units(kwargs.get("units"))  # type: ignore[arg-type]
        interval = self._resolve_interval(kwargs.get("interval"))  # type: ignore[arg-type]

        params: dict[str, str] = {
            "product": "predictions",
            "station": station_id,
            "begin_date": begin_date,
            "end_date": end_date,
            "datum": datum,
            "units": units,
            "time_zone": "gmt",
            "format": "json",
            "interval": interval,
        }

        resp = await self._http.get(_DATA_BASE, params=params)
        data = resp.json()

        self._check_error(data)

        raw_preds: list[dict[str, Any]] = data.get("predictions", [])
        predictions: list[dict[str, Any]] = []
        for p in raw_preds:
            event: dict[str, Any] = {
                "datetime": p.get("t", ""),
                "height": float(p.get("v", 0.0)),
            }
            # "type" is present for hilo predictions (H/L)
            raw_type = p.get("type")
            if raw_type:
                event["event_type"] = _EVENT_TYPE_MAP.get(raw_type, raw_type)
            else:
                event["event_type"] = None
            predictions.append(event)

        return predictions  # type: ignore[return-value]

    # ─── BaseTideProvider: get_observations ───────────────────────────────

    async def get_observations(
        self, station_id: str, **kwargs: object
    ) -> list[dict[str, object]]:
        """Get observed water levels.

        Supported kwargs
        ----------------
        start_date  : YYYYMMDD
        end_date    : YYYYMMDD
        datum       : default "MLLW"
        units       : default "metric"
        product     : "water_level" | "hourly_height" | "high_low" |
                      "monthly_mean" (default: "water_level")
        """
        begin_date, end_date = self._default_dates(
            kwargs.get("start_date"),  # type: ignore[arg-type]
            kwargs.get("end_date"),    # type: ignore[arg-type]
            default_days=1,
        )

        datum = str(kwargs.get("datum", "MLLW"))
        units = self._resolve_units(kwargs.get("units"))  # type: ignore[arg-type]
        product = str(kwargs.get("product", "water_level"))

        params: dict[str, str] = {
            "product": product,
            "station": station_id,
            "begin_date": begin_date,
            "end_date": end_date,
            "datum": datum,
            "units": units,
            "time_zone": "gmt",
            "format": "json",
        }

        resp = await self._http.get(_DATA_BASE, params=params)
        data = resp.json()

        self._check_error(data)

        # Route to the correct parser based on product.
        if product == "high_low":
            return self._parse_high_low(data)
        if product == "monthly_mean":
            return self._parse_monthly_mean(data)
        return self._parse_water_level(data)

    def _parse_water_level(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse standard water_level / hourly_height responses."""
        readings: list[dict[str, Any]] = []
        for r in data.get("data", []):
            value = r.get("v")
            if value is None or value == "":
                continue
            readings.append({
                "datetime": r.get("t", ""),
                "value": float(value),
                "quality": r.get("q", None),
                "flags": r.get("f", None),
                "sigma": _safe_float(r.get("s")),
            })
        return readings

    def _parse_high_low(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse high_low product responses."""
        readings: list[dict[str, Any]] = []
        for r in data.get("data", []):
            value = r.get("v")
            if value is None or value == "":
                continue
            raw_type = r.get("ty", r.get("type", ""))
            readings.append({
                "datetime": r.get("t", ""),
                "value": float(value),
                "event_type": _EVENT_TYPE_MAP.get(raw_type, raw_type),
                "quality": r.get("q", None),
            })
        return readings

    def _parse_monthly_mean(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse monthly_mean product responses."""
        readings: list[dict[str, Any]] = []
        for r in data.get("data", []):
            readings.append({
                "year": int(r.get("year", 0)),
                "month": int(r.get("month", 0)),
                "highest": _safe_float(r.get("highest")),
                "msl": _safe_float(r.get("MSL")),
                "mhw": _safe_float(r.get("MHW")),
                "mhhw": _safe_float(r.get("MHHW")),
                "mlw": _safe_float(r.get("MLW")),
                "mllw": _safe_float(r.get("MLLW")),
                "lowest": _safe_float(r.get("lowest")),
                "dtl": _safe_float(r.get("DTL")),
                "mtl": _safe_float(r.get("MTL")),
            })
        return readings

    # ─── BaseTideProvider: get_latest ─────────────────────────────────────

    async def get_latest(self, station_id: str, **kwargs: object) -> dict[str, object]:
        """Get the most recent water level reading for a station.

        Supported kwargs
        ----------------
        datum : default "MLLW"
        units : default "metric"
        """
        datum = str(kwargs.get("datum", "MLLW"))
        units = self._resolve_units(kwargs.get("units"))  # type: ignore[arg-type]

        # The NOAA API supports a "date=latest" parameter for the most recent
        # 6-minute observation.
        params: dict[str, str] = {
            "product": "water_level",
            "station": station_id,
            "date": "latest",
            "datum": datum,
            "units": units,
            "time_zone": "gmt",
            "format": "json",
        }

        resp = await self._http.get(_DATA_BASE, params=params)
        data = resp.json()

        self._check_error(data)

        raw_list = data.get("data", [])
        if not raw_list:
            raise ValueError(
                f"No recent observations available for station {station_id}"
            )

        latest = raw_list[-1]
        value = latest.get("v")
        if value is None or value == "":
            raise ValueError(
                f"Latest observation for station {station_id} has no value"
            )

        return {
            "station_id": station_id,
            "datetime": latest.get("t", ""),
            "value": float(value),
            "sigma": _safe_float(latest.get("s")),
            "flags": latest.get("f", None),
            "quality": latest.get("q", None),
            "datum": datum,
            "units": units,
        }

    # ─── Extended: get_extremes ───────────────────────────────────────────

    async def get_extremes(
        self,
        station_id: str,
        datum: str = "MLLW",
    ) -> dict[str, object]:
        """Get the top-ten highest/lowest water levels from NOAA.

        Uses the ``toptenwaterlevels`` derived product which returns
        named storm events and their peak water levels.
        """
        url = f"{_DERIVED_BASE}/product.json"
        params: dict[str, str] = {
            "name": "toptenwaterlevels",
            "station": station_id,
            "units": "metric",
        }

        resp = await self._http.get(url, params=params)
        data = resp.json()

        self._check_error(data)

        highs: list[dict[str, Any]] = []
        for e in data.get("topTenWaterLevels", []):
            highs.append({
                "date": e.get("peakDate", ""),
                "height": float(e.get("height", 0.0)),
                "event_name": e.get("event"),
            })

        # The top-ten endpoint only returns highs; sort descending.
        highs.sort(key=lambda x: x["height"], reverse=True)

        return {
            "station_id": station_id,
            "top_ten_high": highs[:10],
            "top_ten_low": [],
            "datum": data.get("topTenWaterLevels", [{}])[0].get("datum", datum) if highs else datum,
        }

    # ─── Extended: get_sea_level_trend ────────────────────────────────────

    async def get_sea_level_trend(self, station_id: str) -> dict[str, object]:
        """Get the sea-level trend for a station from NOAA's derived products.

        Hits the ``sealvltrends`` endpoint and extracts the record for the
        requested station.  The NOAA API returns trends in inches/decade;
        we convert to mm/year.
        """
        url = f"{_DERIVED_BASE}/product/sealvltrends.json"
        params: dict[str, str] = {"station": station_id}

        resp = await self._http.get(url, params=params)
        data = resp.json()

        self._check_error(data)

        trends: list[dict[str, Any]] = data.get("SeaLvlTrends", data.get("sltrends", []))

        # Find the matching station.
        match: dict[str, Any] | None = None
        for t in trends:
            if str(t.get("stationId", t.get("id", ""))) == str(station_id):
                match = t
                break

        if match is None:
            raise ValueError(
                f"No sea-level trend data found for station {station_id}"
            )

        # Convert inches/decade → mm/year: multiply by 2.54
        trend_in_dec = float(match.get("trend", 0.0))
        error_in_dec = float(match.get("trendError", match.get("trend_95ci", 0.0)))
        trend_mm_yr = round(trend_in_dec * 2.54, 2)
        error_mm_yr = round(error_in_dec * 2.54, 2)

        # Parse dates: "07/15/1938" → year
        start_date = match.get("startDate", "")
        end_date = match.get("endDate", "")
        first_year = int(start_date.split("/")[-1]) if "/" in start_date else int(match.get("firstYear", 0))
        last_year = int(end_date.split("/")[-1]) if "/" in end_date else int(match.get("lastYear", 0))

        return {
            "station_id": station_id,
            "station_name": match.get("stationName", match.get("name", "")),
            "trend_mm_per_year": trend_mm_yr,
            "trend_uncertainty": error_mm_yr,
            "first_year": first_year,
            "last_year": last_year,
            "record_length_years": last_year - first_year + 1 if first_year else 0,
            "data_source": "NOAA CO-OPS sea level trends",
        }

    # ─── Extended: get_flood_outlook ──────────────────────────────────────

    async def get_flood_outlook(
        self,
        station_id: str,
        product: str = "htf_annual",
        threshold: str = "minor",
    ) -> dict[str, object]:
        """Get high-tide flooding data from NOAA's derived products API.

        Parameters
        ----------
        station_id : str
            NOAA station identifier.
        product : str
            Derived product name, e.g. ``"htf_annual"`` (annual flood
            counts) or ``"htf_outlook"`` (seasonal outlook).
        threshold : str
            Flood threshold: ``"minor"``, ``"moderate"``, or ``"major"``.
        """
        url = f"{_DERIVED_BASE}/htf/{product}.json"
        params: dict[str, str] = {
            "station": station_id,
        }

        resp = await self._http.get(url, params=params)
        data = resp.json()

        self._check_error(data)

        # ── Determine the flood level in metres ──────────────────────────
        flood_level_m = 0.0
        # The response may include the threshold level; try several keys.
        flood_level_m = _safe_float(
            data.get("floodLevel")
            or data.get("thresholdValue")
            or data.get("threshold_value")
        ) or 0.0

        # ── Parse annual counts ──────────────────────────────────────────
        # Real htf_annual response: {"AnnualFloodCount": [{"year":..., "minCount":..., "modCount":..., "majCount":...}]}
        # Map threshold to the correct count key in the response.
        _threshold_key = {
            "minor": "minCount",
            "moderate": "modCount",
            "major": "majCount",
        }
        count_key = _threshold_key.get(threshold, "minCount")

        counts: list[dict[str, Any]] = []
        raw_counts: list[dict[str, Any]] = (
            data.get("AnnualFloodCount")
            or data.get("data")
            or data.get("htfAnnual")
            or []
        )
        if isinstance(raw_counts, list):
            for entry in raw_counts:
                year = entry.get("year", entry.get("period", ""))
                # Try threshold-specific key first, then generic fallbacks
                count = entry.get(count_key, entry.get("count", entry.get("value", 0)))
                counts.append({
                    "period": str(year),
                    "count": int(float(str(count))) if count is not None else 0,
                })

        # ── Parse projection if present (htf_outlook) ────────────────────
        projection: dict[str, Any] | None = None
        proj_block = data.get("projection", data.get("outlook", None))
        if proj_block and isinstance(proj_block, dict):
            projection = {
                "year": int(proj_block.get("year", 0)),
                "expected": int(proj_block.get("expected", proj_block.get("median", 0))),
                "low": int(proj_block.get("low", proj_block.get("min", 0))),
                "high": int(proj_block.get("high", proj_block.get("max", 0))),
            }

        return {
            "station_id": station_id,
            "product": product,
            "flood_threshold": threshold,
            "flood_level_m": flood_level_m,
            "counts": counts,
            "projection": projection,
        }


# ─── Module-level helpers ─────────────────────────────────────────────────────


def _safe_float(val: Any) -> float | None:
    """Convert *val* to float, returning ``None`` for empty / unparseable values."""
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
