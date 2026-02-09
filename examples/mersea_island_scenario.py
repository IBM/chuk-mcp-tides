#!/usr/bin/env python3
"""
Scenario: Mersea Island Coastal Flooding Assessment

Mersea Island is a low-lying tidal island off the Essex coast in England
(51.78 N, 0.93 E). The only road access (the Strood causeway) floods on
high spring tides, regularly cutting the island off from the mainland.

This scenario demonstrates a complete tidal analysis workflow:

  1. Discover nearby tide gauge stations (EA)
  2. Get the latest water level (with tide state inference)
  3. Get recent observations from the EA gauge
  4. Run harmonic analysis to extract tidal constituents
  5. Generate local predictions from constituents (offline)
  6. Build a flooding calendar for the Strood causeway
  7. Show available capabilities for further analysis

Requires: No API keys (uses EA free API). utide for harmonic analysis.
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")
from tool_runner import create_runner


MERSEA_LAT = 51.78
MERSEA_LON = 0.93

# The Strood causeway floods at roughly 1.5m above Ordnance Datum.
STROOD_FLOOD_THRESHOLD = 1.5


def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}\n")


def narrative(text: str) -> None:
    """Print scenario narrative."""
    for line in text.strip().split("\n"):
        print(f"  {line.strip()}")
    print()


async def main() -> None:
    runner = create_runner()

    print("=" * 60)
    print("  Mersea Island Coastal Flooding Assessment")
    print(f"  Location: {MERSEA_LAT:.2f}N, {MERSEA_LON:.2f}E")
    print("=" * 60)

    narrative("""
        Mersea Island sits just above sea level in the Blackwater
        Estuary, Essex. The Strood causeway connecting it to the
        mainland floods multiple times per month on spring tides.

        Let's assess the tidal conditions using live data.
    """)

    # ------------------------------------------------------------------
    # 1. Find nearby stations across all providers
    # ------------------------------------------------------------------
    section("1. Discover Nearby Tide Gauges")

    narrative("""
        First, search for tide stations near Mersea Island.
        The EA (Environment Agency) network provides free real-time
        observations from UK coastal gauges.
    """)

    print("  EA (UK Environment Agency) stations:")
    result = await runner.run(
        "tides_list_stations",
        provider="ea",
        lat=MERSEA_LAT,
        lon=MERSEA_LON,
        radius_km=50,
        max_results=5,
        output_mode="text",
    )
    print(result)

    # Get the nearest EA station ID
    ea_json = await runner.run(
        "tides_list_stations",
        provider="ea",
        lat=MERSEA_LAT,
        lon=MERSEA_LON,
        radius_km=100,
        max_results=1,
    )
    ea_data = json.loads(ea_json)
    if ea_data.get("stations") and len(ea_data["stations"]) > 0:
        ea_station = ea_data["stations"][0]
        ea_station_id = ea_station["station_id"]
        ea_station_name = ea_station["name"]
    else:
        # Fallback: try broader search
        ea_json = await runner.run(
            "tides_list_stations",
            provider="ea",
            max_results=5,
        )
        ea_data = json.loads(ea_json)
        ea_station = ea_data["stations"][0] if ea_data["stations"] else None
        if ea_station:
            ea_station_id = ea_station["station_id"]
            ea_station_name = ea_station["name"]
        else:
            print("  No EA stations found. Exiting.")
            return

    print(f"\n  Nearest EA station: {ea_station_id} ({ea_station_name})")

    # ------------------------------------------------------------------
    # 2. Station detail
    # ------------------------------------------------------------------
    section("2. Station Detail (EA)")

    result = await runner.run(
        "tides_describe_station",
        station_id=ea_station_id,
        provider="ea",
        output_mode="text",
    )
    print(result)

    # ------------------------------------------------------------------
    # 3. Latest water level
    # ------------------------------------------------------------------
    section("3. Latest Water Level")

    narrative("""
        What is the current water level at the nearest gauge?
        This tells us whether the Strood is currently passable.
        (The EA doesn't publish predictions, so the tide state is
        inferred from the direction of recent observations.)
    """)

    result = await runner.run(
        "tides_latest",
        station_id=ea_station_id,
        provider="ea",
        output_mode="text",
    )
    print(result)

    # ------------------------------------------------------------------
    # 4. Recent observations
    # ------------------------------------------------------------------
    section("4. Recent Observations (Last 24h)")

    narrative("""
        Pull the last 24 hours of water level readings to see
        the tidal pattern and identify peak levels.
    """)

    result = await runner.run(
        "tides_observations",
        station_id=ea_station_id,
        provider="ea",
        start_date="today",
        output_mode="text",
    )
    print(result)

    # ------------------------------------------------------------------
    # 5. Harmonic analysis — extract tidal constituents
    # ------------------------------------------------------------------
    section("5. Harmonic Analysis — Extract Tidal Signature")

    narrative("""
        The EA doesn't publish tidal predictions, but we can
        extract them from observations. 30 days of water level
        data is enough for utide to fit the harmonic constituents
        (M2, S2, K1, O1...) that drive the tide at this location.
    """)

    # Calculate date range: 35 days back to give margin
    now = datetime.now(timezone.utc)
    ha_start = (now - timedelta(days=35)).strftime("%Y-%m-%d")
    ha_end = now.strftime("%Y-%m-%d")

    harmonic_ok = False
    try:
        result = await runner.run(
            "tides_harmonic_analysis",
            station_id=ea_station_id,
            start_date=ha_start,
            end_date=ha_end,
            provider="ea",
            store_constituents=True,
            output_mode="text",
        )
        print(result)

        # Check if it worked (not an error)
        result_json = await runner.run(
            "tides_harmonic_analysis",
            station_id=ea_station_id,
            start_date=ha_start,
            end_date=ha_end,
            provider="ea",
            store_constituents=True,
        )
        parsed = json.loads(result_json)
        if "error" not in parsed:
            harmonic_ok = True
            print(f"\n  Constituents stored for {ea_station_id} — ready for local predictions.")
        else:
            print(f"\n  Harmonic analysis failed: {parsed['error']}")
    except Exception as e:
        print("  Harmonic analysis requires utide: pip install utide")
        print(f"  ({e})")

    # ------------------------------------------------------------------
    # 6. Local predictions from constituents
    # ------------------------------------------------------------------
    if harmonic_ok:
        section("6. Local Predictions — Synthesised from Constituents")

        narrative("""
            With constituents stored, we can predict tides offline.
            No network needed — pure harmonic reconstruction using
            the tidal signature we just extracted.
        """)

        pred_start = now.strftime("%Y-%m-%d")
        pred_end = (now + timedelta(days=7)).strftime("%Y-%m-%d")

        result = await runner.run(
            "tides_predict_local",
            station_id=ea_station_id,
            start_date=pred_start,
            end_date=pred_end,
            interval_minutes=60,
            output_mode="text",
        )
        print(result)

    # ------------------------------------------------------------------
    # 7. Flooding calendar for the Strood
    # ------------------------------------------------------------------
    if harmonic_ok:
        section("7. Strood Flooding Calendar — 2026")

        narrative(f"""
            The Strood causeway floods when the tide exceeds
            ~{STROOD_FLOOD_THRESHOLD}m AOD. Using our local predictions for all
            of 2026, we can count how many days the island gets
            cut off from the mainland.
        """)

        result = await runner.run(
            "tides_flooding_calendar",
            station_id=ea_station_id,
            threshold=STROOD_FLOOD_THRESHOLD,
            year=2026,
            provider="local",
            output_mode="text",
        )
        print(result)

    # ------------------------------------------------------------------
    # 8. Server capabilities
    # ------------------------------------------------------------------
    section("8. Available Analysis Capabilities")

    narrative("""
        The server provides 20 tools across 7 categories.
        Here's what an LLM could use to continue this analysis:
    """)

    result = await runner.run("tides_capabilities", output_mode="text")
    print(result)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    section("Scenario Summary")

    if harmonic_ok:
        narrative("""
            This scenario demonstrated a complete coastal flood
            assessment workflow — entirely self-contained for Essex:

            1. Station discovery — found EA gauges near Mersea
            2. Live observations — current water level + tide state
            3. Harmonic analysis — extracted tidal constituents
            4. Local predictions — synthesised forecasts offline
            5. Flooding calendar — counted Strood flood days

            An LLM agent would continue by:
            - Projecting future flooding under SLR scenarios
            - Cross-referencing with satellite imagery (chuk-mcp-stac)
            - Overlaying with terrain data (chuk-mcp-dem)
            - Comparing with NOAA long-term trends at similar stations
        """)
    else:
        narrative("""
            This scenario demonstrated a coastal observation
            workflow using the EA free API:

            1. Station discovery — found EA gauges near Mersea
            2. Live observations — current water level + tide state
            3. Recent observations — 24h tidal pattern

            Install utide to unlock the full workflow:
            - Harmonic analysis → local predictions → flooding calendar
        """)

    print(f"{'=' * 60}")
    print("  Scenario complete!")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
