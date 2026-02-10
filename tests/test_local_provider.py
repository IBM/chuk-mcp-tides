"""Tests for LocalProvider (local harmonic engine)."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from chuk_mcp_tides.providers.local import (
    LocalProvider,
    _classify_tide,
    _coef_to_storage_dict,
    _compute_form_number,
    _extract_highs_lows,
    _require_utide,
    _storage_dict_to_coef,
    _to_json_safe,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_storage():
    """Mock ConstituentStorage."""
    storage = MagicMock()
    storage.list_stations = AsyncMock(return_value=[])
    storage.load = AsyncMock(return_value={})
    storage.save = AsyncMock(return_value=True)
    return storage


@pytest.fixture
def provider(mock_storage):
    """LocalProvider with mocked storage."""
    return LocalProvider(constituent_storage=mock_storage)


def _make_bunch(**kwargs):
    """Create a utide Bunch-like object (dict subclass with attribute access)."""
    from utide.utilities import Bunch

    return Bunch(**kwargs)


# ── _require_utide ────────────────────────────────────────────────────────


def test_require_utide_when_available():
    """Should not raise when utide is installed."""
    _require_utide()  # utide IS installed in test env


def test_require_utide_not_installed():
    """Should raise ImportError when _HAS_UTIDE is False."""
    with patch("chuk_mcp_tides.providers.local._HAS_UTIDE", False):
        with pytest.raises(ImportError, match="utide is required"):
            _require_utide()


# ── _classify_tide ────────────────────────────────────────────────────────


def test_classify_tide_semidiurnal():
    assert _classify_tide(0.1) == "semidiurnal"


def test_classify_tide_mixed():
    assert _classify_tide(1.0) == "mixed"


def test_classify_tide_diurnal():
    assert _classify_tide(5.0) == "diurnal"


# ── _compute_form_number ─────────────────────────────────────────────────


def test_form_number_semidiurnal():
    """Dominant M2+S2 → small form number."""
    coef = _make_bunch(
        name=np.array(["M2", "S2", "K1", "O1"]),
        A=np.array([2.0, 0.5, 0.1, 0.05]),
    )
    fn = _compute_form_number(coef)
    assert fn < 0.25  # semidiurnal


def test_form_number_diurnal():
    """Dominant K1+O1 → large form number."""
    coef = _make_bunch(
        name=np.array(["M2", "S2", "K1", "O1"]),
        A=np.array([0.1, 0.05, 2.0, 1.5]),
    )
    fn = _compute_form_number(coef)
    assert fn > 3.0  # diurnal


def test_form_number_zero_denominator_with_diurnal():
    """M2=0, S2=0, but K1+O1>0 → inf."""
    coef = _make_bunch(
        name=np.array(["M2", "S2", "K1", "O1"]),
        A=np.array([0.0, 0.0, 1.0, 0.5]),
    )
    fn = _compute_form_number(coef)
    assert fn == float("inf")


def test_form_number_all_zero():
    """All amplitudes zero → 0.0."""
    coef = _make_bunch(
        name=np.array(["M2", "S2", "K1", "O1"]),
        A=np.array([0.0, 0.0, 0.0, 0.0]),
    )
    fn = _compute_form_number(coef)
    assert fn == 0.0


def test_form_number_missing_constituent():
    """Only M2 present → 0.0 (no K1/O1)."""
    coef = _make_bunch(
        name=np.array(["M2"]),
        A=np.array([2.0]),
    )
    fn = _compute_form_number(coef)
    assert fn == 0.0


# ── _to_json_safe ────────────────────────────────────────────────────────


def test_to_json_safe_ndarray():
    assert _to_json_safe(np.array([1, 2, 3])) == [1, 2, 3]


def test_to_json_safe_numpy_int():
    assert _to_json_safe(np.int64(42)) == 42
    assert isinstance(_to_json_safe(np.int64(42)), int)


def test_to_json_safe_numpy_float():
    assert _to_json_safe(np.float64(3.14)) == pytest.approx(3.14)
    assert isinstance(_to_json_safe(np.float64(3.14)), float)


def test_to_json_safe_numpy_bool():
    assert _to_json_safe(np.bool_(True)) is True


def test_to_json_safe_nested_dict():
    result = _to_json_safe({"a": np.array([1]), "b": {"c": np.int64(5)}})
    assert result == {"a": [1], "b": {"c": 5}}


def test_to_json_safe_list():
    result = _to_json_safe([np.float64(1.0), np.int64(2)])
    assert result == [1.0, 2]


def test_to_json_safe_plain_value():
    assert _to_json_safe("hello") == "hello"
    assert _to_json_safe(42) == 42


# ── _extract_highs_lows ──────────────────────────────────────────────────


def test_extract_highs_lows_sine_wave():
    """Detect peaks and troughs in a simple sine wave."""
    n = 100
    times = [datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i) for i in range(n)]
    times_arr = np.array(times, dtype=object)
    signal = np.sin(np.linspace(0, 4 * np.pi, n))  # ~2 full cycles

    result = _extract_highs_lows(times_arr, signal)
    highs = [r for r in result if r["type"] == "high"]
    lows = [r for r in result if r["type"] == "low"]
    assert len(highs) >= 1
    assert len(lows) >= 1
    # Highs should be positive, lows should be negative
    for h in highs:
        assert h["height"] > 0
    for lo in lows:
        assert lo["height"] < 0


def test_extract_highs_lows_string_times():
    """Handle times that are strings (no isoformat method)."""
    n = 50
    times = np.array([f"2025-01-01T{i:02d}:00:00" for i in range(n)])
    signal = np.sin(np.linspace(0, 2 * np.pi, n))

    result = _extract_highs_lows(times, signal)
    assert len(result) >= 1  # at least one peak or trough


# ── _coef_to_storage_dict ────────────────────────────────────────────────


def test_coef_to_storage_dict():
    """Serialize a utide Bunch to storage format."""
    coef = _make_bunch(
        name=np.array(["M2", "S2"]),
        A=np.array([1.5, 0.3]),
        g=np.array([120.0, 60.0]),
        mean=np.float64(0.5),
        aux=_make_bunch(freq=np.array([0.081, 0.083])),
    )
    result = _coef_to_storage_dict(coef, "TEST01", 51.0, 0.1, "semidiurnal", 0.5)

    assert result["station_id"] == "TEST01"
    assert result["lat"] == 51.0
    assert result["tidal_type"] == "semidiurnal"
    assert result["mean_level"] == 0.5
    assert "coef" in result
    # coef should be JSON-safe (no numpy types)
    assert isinstance(result["coef"]["name"], list)
    assert isinstance(result["coef"]["A"], list)


def test_coef_to_storage_dict_none_station():
    """station_id=None → "unknown"."""
    coef = _make_bunch(name=np.array(["M2"]), A=np.array([1.0]))
    result = _coef_to_storage_dict(coef, None, 0.0, 0.0, "semidiurnal", 0.0)
    assert result["station_id"] == "unknown"


# ── _storage_dict_to_coef ────────────────────────────────────────────────


def test_storage_dict_to_coef_new_format():
    """Reconstruct coef from new 'coef' key format."""
    data = {
        "coef": {
            "name": ["M2", "S2"],
            "A": [1.5, 0.3],
            "g": [120.0, 60.0],
            "mean": 0.5,
            "aux": {
                "freq": [0.081, 0.083],
                "opt": {"twodim": False},
            },
        }
    }
    coef = _storage_dict_to_coef(data)
    assert list(coef.name) == ["M2", "S2"]
    assert coef.A[0] == pytest.approx(1.5)
    # Subscript access works (needed by utide.reconstruct)
    assert coef["aux"]["opt"]["twodim"] is False


def test_storage_dict_to_coef_legacy_format():
    """Reconstruct coef from old 'constituents' key format."""
    data = {
        "constituents": {
            "name": ["M2", "S2"],
            "A": [1.5, 0.3],
            "g": [120.0, 60.0],
            "aux": {"freq": [0.081, 0.083]},
        },
        "mean_level": 0.5,
    }
    coef = _storage_dict_to_coef(data)
    assert list(coef.name) == ["M2", "S2"]
    assert coef.mean == 0.5
    assert len(coef.aux.freq) == 2


# ── LocalProvider BaseTideProvider interface ─────────────────────────────


async def test_list_stations(provider, mock_storage):
    """list_stations delegates to storage."""
    mock_storage.list_stations.return_value = [{"station_id": "TEST01", "name": "Test Station"}]
    result = await provider.list_stations()
    assert len(result) == 1
    assert result[0]["station_id"] == "TEST01"


async def test_get_station_detail_with_constituents(provider, mock_storage):
    """get_station_detail unpacks constituent data from storage."""
    mock_storage.load.return_value = {
        "station_id": "TEST01",
        "lat": 51.0,
        "mean_level": 0.5,
        "form_number": 0.12,
        "tidal_type": "semidiurnal",
        "fitted_date": "2025-01-01T00:00:00Z",
        "constituents": {
            "name": ["M2", "S2"],
            "A": [1.5, 0.3],
            "g": [120.0, 60.0],
            "aux": {"freq": [0.081, 0.083]},
        },
    }
    result = await provider.get_station_detail("TEST01")
    assert result["station_id"] == "TEST01"
    assert result["constituent_count"] == 2
    assert len(result["constituents"]) == 2
    assert result["constituents"][0]["name"] == "M2"
    assert result["constituents"][0]["amplitude"] == 1.5
    assert result["constituents"][0]["phase"] == 120.0
    assert result["constituents"][0]["frequency"] == 0.081


async def test_get_station_detail_empty_storage(provider, mock_storage):
    """get_station_detail handles empty storage gracefully."""
    mock_storage.load.return_value = {}
    result = await provider.get_station_detail("MISSING")
    assert result["constituent_count"] == 0
    assert result["constituents"] == []


async def test_get_predictions_delegates(provider, mock_storage):
    """get_predictions delegates to predict_from_constituents."""
    mock_storage.load.return_value = {
        "coef": {
            "name": ["M2"],
            "A": [1.0],
            "g": [0.0],
            "mean": 0.0,
            "aux": {
                "freq": [0.081],
                "opt": {"twodim": False},
                "reftime": "2025-01-01",
                "lind": [0],
            },
        },
        "lat": 51.0,
    }
    # This will actually call utide.reconstruct with the mock data
    # Use a mock instead to keep the test fast
    with patch.object(provider, "predict_from_constituents", new_callable=AsyncMock) as mock_pfc:
        mock_pfc.return_value = {"predictions": [{"datetime": "2025-01-01", "height": 1.0}]}
        result = await provider.get_predictions("TEST01", start_date="2025-01-01")
        assert len(result) == 1


async def test_get_observations_raises(provider):
    """get_observations raises NotImplementedError."""
    with pytest.raises(NotImplementedError, match="does not support observations"):
        await provider.get_observations("TEST01")


async def test_get_latest_raises(provider):
    """get_latest raises NotImplementedError."""
    with pytest.raises(NotImplementedError, match="does not support observations"):
        await provider.get_latest("TEST01")


# ── analyze_harmonics ────────────────────────────────────────────────────


async def test_analyze_harmonics(provider, mock_storage):
    """Full analysis flow with mocked utide.solve/reconstruct."""
    n = 720  # 30 days of hourly data
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    times = [t0 + timedelta(hours=i) for i in range(n)]
    heights = [1.0 + np.sin(i * 0.5) for i in range(n)]

    mock_coef = _make_bunch(
        name=np.array(["M2", "S2"]),
        A=np.array([1.4, 0.3]),
        g=np.array([120.0, 60.0]),
        mean=np.float64(1.0),
        aux=_make_bunch(freq=np.array([0.081, 0.083])),
        diagn=_make_bunch(SNR=np.array([100.0, 25.0])),
    )
    mock_recon = MagicMock()
    mock_recon.h = np.array(heights)  # perfect fit → 0 residual

    with (
        patch("chuk_mcp_tides.providers.local.utide.solve", return_value=mock_coef),
        patch("chuk_mcp_tides.providers.local.utide.reconstruct", return_value=mock_recon),
    ):
        result = await provider.analyze_harmonics(
            times, heights, lat=51.0, station_id="TEST01", store=True
        )

    assert result["mean_level"] == 1.0
    assert len(result["constituents"]) == 2
    assert result["constituents"][0]["name"] == "M2"
    assert result["constituents"][0]["snr"] == 100.0
    assert result["tidal_type"] in ("semidiurnal", "mixed", "diurnal")
    assert result["stored"] is True
    assert result["observation_days"] >= 29
    mock_storage.save.assert_called_once()


async def test_analyze_harmonics_no_store(provider, mock_storage):
    """analyze_harmonics with store=False does not persist."""
    n = 720
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    times = [t0 + timedelta(hours=i) for i in range(n)]
    heights = [1.0] * n

    mock_coef = _make_bunch(
        name=np.array(["M2"]),
        A=np.array([1.0]),
        g=np.array([0.0]),
        mean=np.float64(1.0),
    )
    mock_recon = MagicMock()
    mock_recon.h = np.array(heights)

    with (
        patch("chuk_mcp_tides.providers.local.utide.solve", return_value=mock_coef),
        patch("chuk_mcp_tides.providers.local.utide.reconstruct", return_value=mock_recon),
    ):
        result = await provider.analyze_harmonics(times, heights, lat=51.0, store=False)

    assert result["stored"] is False
    mock_storage.save.assert_not_called()


# ── predict_from_constituents ────────────────────────────────────────────


async def test_predict_from_constituents_with_station_id(provider, mock_storage):
    """Load constituents from storage by station_id."""
    mock_storage.load.return_value = {
        "coef": {
            "name": ["M2"],
            "A": [1.0],
            "g": [0.0],
            "mean": 0.0,
            "aux": {
                "freq": [0.081],
                "opt": {"twodim": False},
                "reftime": "2025-01-01",
                "lind": [0],
            },
        },
        "lat": 51.0,
        "constituents": {"name": ["M2"]},
    }

    mock_recon = MagicMock()
    mock_recon.h = np.zeros(169)  # 7 days hourly + 1

    with patch("chuk_mcp_tides.providers.local.utide.reconstruct", return_value=mock_recon):
        result = await provider.predict_from_constituents(
            station_id="TEST01",
            start_date="2025-01-01",
            end_date="2025-01-08",
        )

    assert "predictions" in result
    assert "highs_lows" in result
    assert len(result["predictions"]) == 169  # 7 days * 24 + 1


async def test_predict_from_constituents_with_dict(provider, mock_storage):
    """Provide constituents directly (no station_id)."""
    data = {
        "coef": {
            "name": ["M2"],
            "A": [1.0],
            "g": [0.0],
            "mean": 0.0,
            "aux": {"freq": [0.081], "opt": {"twodim": False}},
        },
        "lat": 51.0,
        "constituents": {"name": ["M2"]},
    }

    mock_recon = MagicMock()
    mock_recon.h = np.zeros(169)

    with patch("chuk_mcp_tides.providers.local.utide.reconstruct", return_value=mock_recon):
        result = await provider.predict_from_constituents(
            constituents=data,
            start_date="2025-01-01",
            end_date="2025-01-08",
            lat=51.0,
        )

    assert len(result["predictions"]) == 169
    mock_storage.load.assert_not_called()


async def test_predict_no_station_or_constituents(provider):
    """Raise ValueError when neither station_id nor constituents provided."""
    with pytest.raises(ValueError, match="Either station_id or constituents"):
        await provider.predict_from_constituents()


async def test_predict_no_lat(provider, mock_storage):
    """Raise ValueError when lat is missing."""
    mock_storage.load.return_value = {
        "coef": {"name": ["M2"], "A": [1.0], "g": [0.0]},
        # no 'lat' key
    }
    with pytest.raises(ValueError, match="Latitude is required"):
        await provider.predict_from_constituents(station_id="TEST01")


async def test_predict_date_variants(provider, mock_storage):
    """Various date input types should all work."""
    data = {
        "coef": {
            "name": ["M2"],
            "A": [1.0],
            "g": [0.0],
            "mean": 0.0,
            "aux": {"freq": [0.081], "opt": {"twodim": False}},
        },
        "lat": 51.0,
        "constituents": {"name": ["M2"]},
    }
    mock_storage.load.return_value = data

    mock_recon = MagicMock()
    mock_recon.h = np.zeros(25)  # 1 day hourly + 1

    with patch("chuk_mcp_tides.providers.local.utide.reconstruct", return_value=mock_recon):
        # date objects
        result = await provider.predict_from_constituents(
            station_id="TEST01",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 2),
        )
        assert len(result["predictions"]) == 25

        # datetime with tz
        result = await provider.predict_from_constituents(
            station_id="TEST01",
            start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 1, 2, tzinfo=timezone.utc),
        )
        assert len(result["predictions"]) == 25

        # naive datetime
        result = await provider.predict_from_constituents(
            station_id="TEST01",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 2),
        )
        assert len(result["predictions"]) == 25


async def test_predict_default_dates(provider, mock_storage):
    """Omitting dates should default to today + 7 days."""
    data = {
        "coef": {
            "name": ["M2"],
            "A": [1.0],
            "g": [0.0],
            "mean": 0.0,
            "aux": {"freq": [0.081], "opt": {"twodim": False}},
        },
        "lat": 51.0,
        "constituents": {"name": ["M2"]},
    }
    mock_storage.load.return_value = data

    mock_recon = MagicMock()
    mock_recon.h = np.zeros(169)

    with patch("chuk_mcp_tides.providers.local.utide.reconstruct", return_value=mock_recon):
        result = await provider.predict_from_constituents(station_id="TEST01")
        assert len(result["predictions"]) == 169  # 7 * 24 + 1


# ── Default storage initialization ───────────────────────────────────────


def test_default_storage_initialization():
    """LocalProvider() without storage creates default ConstituentStorage."""
    provider = LocalProvider()
    assert provider.storage is not None
