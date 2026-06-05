"""Tests for the pure tidal-stage classifier behind tides_classify_stage."""

import datetime as dt
import math

from chuk_mcp_tides.tools.analysis.api import _classify_stages


def _day_series(day: str):
    """Synthetic semidiurnal-ish day at 15-min steps."""
    base = dt.datetime.fromisoformat(day + "T00:00:00+00:00")
    out = []
    for i in range(96):
        t = base + dt.timedelta(minutes=15 * i)
        h = 5.0 + 2.0 * math.sin(2 * math.pi * (i * 15) / (12.42 * 60))
        out.append((t, h))
    return out


def test_low_and_high_stage():
    day = "2023-07-07"
    sbd = {day: _day_series(day)}
    heights = [h for _, h in sbd[day]]
    lo_t = sbd[day][heights.index(min(heights))][0].isoformat()
    hi_t = sbd[day][heights.index(max(heights))][0].isoformat()
    recs = {r["datetime"]: r for r in _classify_stages(sbd, [lo_t, hi_t], 0.33, 0.66)}
    assert recs[lo_t]["stage"] == "low"
    assert recs[hi_t]["stage"] == "high"
    assert recs[lo_t]["height"] < recs[hi_t]["height"]
    assert recs[lo_t]["stage_norm"] == 0.0
    assert recs[hi_t]["stage_norm"] == 1.0


def test_missing_day_is_unknown():
    recs = _classify_stages({}, ["2023-01-01T11:00:00Z"], 0.33, 0.66)
    assert recs[0]["stage"] == "unknown"
    assert recs[0]["height"] is None
