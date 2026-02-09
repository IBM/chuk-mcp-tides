"""
Local harmonic engine provider.

Implements offline tidal predictions from harmonic constituents
via utide.  No network required -- all analysis and prediction
happens locally using stored (or freshly computed) harmonic
coefficients.

utide is an OPTIONAL dependency.  If it is not installed, every
method that needs it will raise ``ImportError`` with a clear
install hint.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from ..constants import (
    FORM_NUMBER_SEMIDIURNAL,
    FORM_NUMBER_MIXED_MAX,
)
from ..core.constituent_storage import ConstituentStorage
from .base import BaseTideProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency guard
# ---------------------------------------------------------------------------

try:
    import utide  # type: ignore[import-untyped]
    import numpy as np

    _HAS_UTIDE = True
except ImportError:
    _HAS_UTIDE = False

_UTIDE_INSTALL_MSG = (
    "utide is required for local harmonic analysis/prediction.  Install it with:  pip install utide"
)


def _require_utide() -> None:
    """Raise ``ImportError`` if utide is not available."""
    if not _HAS_UTIDE:
        raise ImportError(_UTIDE_INSTALL_MSG)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _classify_tide(form_number: float) -> str:
    """Classify a tide by its form number F = (K1+O1)/(M2+S2)."""
    if form_number < FORM_NUMBER_SEMIDIURNAL:
        return "semidiurnal"
    if form_number <= FORM_NUMBER_MIXED_MAX:
        return "mixed"
    return "diurnal"


def _compute_form_number(coef: Any) -> float:
    """Compute form number from utide coefficient object.

    F = (K1 + O1) / (M2 + S2).  Returns 0.0 if the required
    constituents are absent.
    """
    name_list = list(coef.name)

    def _amp(cname: str) -> float:
        try:
            idx = name_list.index(cname)
            return float(coef.A[idx])
        except (ValueError, IndexError):
            return 0.0

    diurnal = _amp("K1") + _amp("O1")
    semidiurnal = _amp("M2") + _amp("S2")
    if semidiurnal == 0.0:
        return float("inf") if diurnal > 0.0 else 0.0
    return diurnal / semidiurnal


def _extract_highs_lows(times: Any, signal: Any) -> list[dict[str, Any]]:
    """Find local maxima (highs) and minima (lows) in a continuous signal.

    Parameters
    ----------
    times : ndarray of datetime-like
        Timestamps corresponding to each sample in *signal*.
    signal : ndarray of float
        Predicted tidal heights.

    Returns
    -------
    list[dict]
        Each dict has keys ``datetime``, ``height``, and ``type``
        (``"high"`` or ``"low"``), sorted chronologically.
    """
    _require_utide()  # numpy must be available

    highs = (signal[1:-1] > signal[:-2]) & (signal[1:-1] > signal[2:])
    lows = (signal[1:-1] < signal[:-2]) & (signal[1:-1] < signal[2:])

    results: list[dict[str, Any]] = []

    high_indices = np.where(highs)[0] + 1  # offset by 1 for the slice
    for idx in high_indices:
        results.append(
            {
                "datetime": times[idx].isoformat()
                if hasattr(times[idx], "isoformat")
                else str(times[idx]),
                "height": round(float(signal[idx]), 4),
                "type": "high",
            }
        )

    low_indices = np.where(lows)[0] + 1
    for idx in low_indices:
        results.append(
            {
                "datetime": times[idx].isoformat()
                if hasattr(times[idx], "isoformat")
                else str(times[idx]),
                "height": round(float(signal[idx]), 4),
                "type": "low",
            }
        )

    results.sort(key=lambda r: r["datetime"])
    return results


def _to_json_safe(obj: Any) -> Any:
    """Recursively convert numpy types to JSON-safe Python types."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json_safe(v) for v in obj]
    return obj


def _coef_to_storage_dict(
    coef: Any,
    station_id: str | None,
    lat: float,
    form_number: float,
    tidal_type: str,
    mean_level: float,
) -> dict[str, Any]:
    """Serialize a utide coefficient object into a JSON-safe dict.

    Stores the complete coefficient structure so that
    ``utide.reconstruct`` can use it directly after loading.
    """
    # coef is a utide Bunch (dict subclass) — serialize all of it
    coef_dict = _to_json_safe(dict(coef))

    return {
        "station_id": station_id or "unknown",
        "lat": lat,
        "coef": coef_dict,
        "mean_level": round(mean_level, 4),
        "form_number": round(form_number, 4),
        "tidal_type": tidal_type,
        "fitted_date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _storage_dict_to_coef(data: dict[str, Any]) -> Any:
    """Reconstruct a utide-compatible Bunch from stored JSON."""
    _require_utide()
    from utide.utilities import Bunch  # type: ignore[import-untyped]

    def _to_bunch(d: Any) -> Any:
        """Recursively convert dicts to Bunch, lists to np.array where appropriate."""
        if isinstance(d, dict):
            return Bunch(**{k: _to_bunch(v) for k, v in d.items()})
        if isinstance(d, list):
            # Convert numeric/string lists to numpy arrays
            if d and isinstance(d[0], (int, float)):
                return np.array(d)
            if d and isinstance(d[0], str):
                return np.array(d)
            return d
        return d

    if "coef" in data:
        # New storage format — full coefficient structure
        return _to_bunch(data["coef"])

    # Legacy fallback for old storage format
    cdict = data["constituents"]
    mean_level = data.get("mean_level", 0.0)
    freq = np.array(cdict.get("aux", {}).get("freq", []), dtype=float)
    return Bunch(
        name=np.array(cdict["name"]),
        A=np.array(cdict["A"], dtype=float),
        g=np.array(cdict["g"], dtype=float),
        mean=mean_level,
        aux=Bunch(frq=freq, freq=freq),
    )


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class LocalProvider(BaseTideProvider):
    """Local harmonic engine using utide.

    Supports offline tidal analysis (fitting constituents to
    observed data) and prediction (reconstructing a tidal signal
    from stored constituents).  No network access is required.

    Parameters
    ----------
    constituent_storage : ConstituentStorage, optional
        Storage backend for harmonic constituents.  When *None*, a
        default filesystem-only storage is created.
    """

    def __init__(self, constituent_storage: ConstituentStorage | None = None) -> None:
        self._storage = constituent_storage or ConstituentStorage()

    @property
    def storage(self) -> ConstituentStorage:
        """The constituent storage backend."""
        return self._storage

    # ── BaseTideProvider interface ────────────────────────────────────────

    async def list_stations(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Return stations that have stored constituents."""
        return await self._storage.list_stations()

    async def get_station_detail(self, station_id: str) -> dict[str, Any]:
        """Load stored constituent metadata for *station_id*."""
        data = await self._storage.load(station_id)
        constituents = data.get("constituents", {})
        names = constituents.get("name", [])
        amplitudes = constituents.get("A", [])
        phases = constituents.get("g", [])
        freqs = constituents.get("aux", {}).get("freq", [])

        constituent_list: list[dict[str, Any]] = []
        for i, name in enumerate(names):
            entry: dict[str, Any] = {"name": name}
            if i < len(amplitudes):
                entry["amplitude"] = amplitudes[i]
            if i < len(phases):
                entry["phase"] = phases[i]
            if i < len(freqs):
                entry["frequency"] = freqs[i]
            constituent_list.append(entry)

        return {
            "station_id": data.get("station_id", station_id),
            "lat": data.get("lat"),
            "mean_level": data.get("mean_level"),
            "form_number": data.get("form_number"),
            "tidal_type": data.get("tidal_type"),
            "fitted_date": data.get("fitted_date"),
            "constituent_count": len(names),
            "constituents": constituent_list,
        }

    async def get_predictions(self, station_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Generate predictions from stored constituents.

        Keyword arguments are forwarded to
        :meth:`predict_from_constituents`.
        """
        result = await self.predict_from_constituents(
            station_id=station_id,
            **kwargs,  # type: ignore[arg-type]
        )
        return result["predictions"]

    async def get_observations(self, station_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Not supported -- local provider has no observation feed."""
        raise NotImplementedError(
            "Local provider does not support observations - use a network provider"
        )

    async def get_latest(self, station_id: str, **kwargs: Any) -> dict[str, Any]:
        """Not supported -- local provider has no observation feed."""
        raise NotImplementedError(
            "Local provider does not support observations - use a network provider"
        )

    # ── Extended API ──────────────────────────────────────────────────────

    async def analyze_harmonics(
        self,
        times: Any,
        heights: Any,
        lat: float,
        station_id: str | None = None,
        store: bool = True,
    ) -> dict[str, Any]:
        """Fit harmonic constituents to an observed time series.

        Parameters
        ----------
        times : array-like of datetime
            Observation timestamps (UTC).
        heights : array-like of float
            Observed water levels (metres).
        lat : float
            Latitude of the observation station.
        station_id : str, optional
            Identifier used when storing constituents.
        store : bool
            If *True* (default), persist the fitted constituents
            to the artifact store.

        Returns
        -------
        dict
            Keys: ``constituents``, ``mean_level``, ``form_number``,
            ``tidal_type``, ``residual_std``, ``stored``.
        """
        _require_utide()

        # Convert datetimes to numpy datetime64 for utide
        # Strip tzinfo first — np.datetime64 doesn't track timezones
        naive_times = [
            t.replace(tzinfo=None) if hasattr(t, "tzinfo") and t.tzinfo else t for t in times
        ]
        time_arr = np.array(naive_times, dtype="datetime64[s]")
        heights_arr = np.asarray(heights, dtype=float)

        # utide.solve is CPU-bound -- run in a thread
        coef = await asyncio.to_thread(
            utide.solve,
            t=time_arr,
            u=heights_arr,
            lat=lat,
            method="ols",
            conf_int="linear",
        )

        # Compute summary statistics
        form_number = _compute_form_number(coef)
        tidal_type = _classify_tide(form_number)
        mean_level = float(coef.mean) if hasattr(coef, "mean") else 0.0

        # Residual standard deviation
        reconstructed = await asyncio.to_thread(utide.reconstruct, t=time_arr, coef=coef)
        residuals = heights_arr - reconstructed.h
        residual_std = float(np.std(residuals))

        # Build per-constituent detail list
        name_list = list(coef.name)
        freq_list: list[float] = []
        if hasattr(coef, "aux") and hasattr(coef.aux, "freq"):
            freq_list = [float(f) for f in coef.aux.freq]

        snr_list: list[float] = []
        if hasattr(coef, "diagn") and hasattr(coef.diagn, "SNR"):
            snr_list = [float(s) for s in coef.diagn.SNR]

        constituents: list[dict[str, Any]] = []
        for i, name in enumerate(name_list):
            entry: dict[str, Any] = {
                "name": str(name),
                "amplitude": round(float(coef.A[i]), 6),
                "phase": round(float(coef.g[i]), 4),
            }
            if i < len(freq_list):
                entry["frequency"] = round(freq_list[i], 8)
            if i < len(snr_list):
                entry["snr"] = round(snr_list[i], 4)
            constituents.append(entry)

        # Persist constituents
        stored = False
        if store and station_id is not None:
            storage_dict = _coef_to_storage_dict(
                coef, station_id, lat, form_number, tidal_type, mean_level
            )
            stored = await self._storage.save(station_id, storage_dict)

        # Compute observation span
        observation_days = 0
        if len(times) >= 2:
            span = times[-1] - times[0]
            observation_days = max(0, span.days)

        return {
            "constituents": constituents,
            "observation_days": observation_days,
            "mean_level": round(mean_level, 4),
            "form_number": round(form_number, 4),
            "tidal_type": tidal_type,
            "residual_std": round(residual_std, 4),
            "stored": stored,
        }

    async def predict_from_constituents(
        self,
        station_id: str | None = None,
        constituents: dict[str, Any] | None = None,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
        interval_minutes: int = 60,
        lat: float | None = None,
        datum_offset: float = 0.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Predict tidal heights from harmonic constituents.

        Either provide *station_id* (to load stored constituents from
        the artifact store) or *constituents* (a dict matching the
        storage format).  At least one must be specified.

        Parameters
        ----------
        station_id : str, optional
            Load stored constituents for this station.
        constituents : dict, optional
            Constituent data in storage format (overrides *station_id*).
        start_date : str or date, optional
            Start of the prediction window (default: today UTC).
        end_date : str or date, optional
            End of the prediction window (default: 7 days from start).
        interval_minutes : int
            Sampling interval in minutes (default 60).
        lat : float, optional
            Latitude (required if using raw *constituents* without a
            stored ``lat`` field).
        datum_offset : float
            Constant offset added to every predicted height (metres).

        Returns
        -------
        dict
            Keys: ``predictions``, ``highs_lows``, ``constituent_count``.
        """
        _require_utide()

        # Resolve coefficient source
        if constituents is not None:
            data = constituents
        elif station_id is not None:
            data = await self._storage.load(station_id)
        else:
            raise ValueError("Either station_id or constituents must be provided")

        coef = _storage_dict_to_coef(data)

        # Resolve latitude
        effective_lat = lat if lat is not None else data.get("lat")
        if effective_lat is None:
            raise ValueError(
                "Latitude is required for tidal reconstruction.  "
                "Provide lat= or ensure it is stored in the constituent file."
            )

        # Resolve date window
        if start_date is None:
            dt_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        elif isinstance(start_date, str):
            dt_start = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
        elif isinstance(start_date, date) and not isinstance(start_date, datetime):
            dt_start = datetime(
                start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc
            )
        else:
            dt_start = start_date if start_date.tzinfo else start_date.replace(tzinfo=timezone.utc)

        if end_date is None:
            dt_end = dt_start + timedelta(days=7)
        elif isinstance(end_date, str):
            dt_end = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
        elif isinstance(end_date, date) and not isinstance(end_date, datetime):
            dt_end = datetime(end_date.year, end_date.month, end_date.day, tzinfo=timezone.utc)
        else:
            dt_end = end_date if end_date.tzinfo else end_date.replace(tzinfo=timezone.utc)

        # Build time array
        total_minutes = int((dt_end - dt_start).total_seconds() / 60)
        n_steps = max(total_minutes // interval_minutes, 1) + 1
        time_deltas = [dt_start + timedelta(minutes=i * interval_minutes) for i in range(n_steps)]
        # Strip tzinfo — np.datetime64 doesn't track timezones
        naive_deltas = [t.replace(tzinfo=None) for t in time_deltas]
        time_arr = np.array(naive_deltas, dtype="datetime64[s]")

        # Reconstruct -- CPU-bound (lat is only used in solve, not reconstruct)
        result = await asyncio.to_thread(utide.reconstruct, t=time_arr, coef=coef)
        signal = result.h + datum_offset

        # Build predictions list
        predictions: list[dict[str, Any]] = []
        for i, t in enumerate(time_deltas):
            predictions.append(
                {
                    "datetime": t.isoformat(),
                    "height": round(float(signal[i]), 4),
                }
            )

        # Extract highs and lows
        highs_lows = await asyncio.to_thread(
            _extract_highs_lows,
            np.array(time_deltas, dtype=object),
            signal,
        )

        constituent_count = len(data.get("constituents", {}).get("name", []))

        return {
            "predictions": predictions,
            "highs_lows": highs_lows,
            "constituent_count": constituent_count,
        }
