#!/usr/bin/env python3
"""
Scenario: Mersea Island Coastal Flooding Assessment

Mersea Island is a low-lying tidal island off the Essex coast in England
(51.78 N, 0.93 E). The only road access (the Strood causeway) floods on
high spring tides, regularly cutting the island off from the mainland.

This scenario demonstrates a multi-step tidal analysis workflow:

  1. Discover nearby tide gauge stations (EA + NOAA)
  2. Get the latest water level from the EA gauge
  3. Get recent observations from the EA gauge
  4. Check server capabilities for planning further analysis
  5. Show how an LLM would continue the workflow

Requires: No API keys (uses NOAA + EA free APIs)
"""

import asyncio
import json
import sys

sys.path.insert(0, ".")
from tool_runner import create_runner


MERSEA_LAT = 51.78
MERSEA_LON = 0.93


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
        We'll check the EA network (free UK observations)
        and then NOAA (to confirm it returns no US stations
        near Essex!).
    """)

    # EA stations
    print("  EA (UK Environment Agency) stations:")
    result = await runner.run(
        "tides_list_stations",
        provider="ea",
        lat=MERSEA_LAT, lon=MERSEA_LON, radius_km=50,
        max_results=5, output_mode="text",
    )
    print(result)

    # Get the nearest EA station ID
    ea_json = await runner.run(
        "tides_list_stations",
        provider="ea",
        lat=MERSEA_LAT, lon=MERSEA_LON, radius_km=100,
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
            provider="ea", max_results=5,
        )
        ea_data = json.loads(ea_json)
        ea_station = ea_data["stations"][0] if ea_data["stations"] else None
        if ea_station:
            ea_station_id = ea_station["station_id"]
            ea_station_name = ea_station["name"]
        else:
            print("  No EA stations found. Continuing with NOAA demo only.")
            ea_station_id = None
            ea_station_name = None

    if ea_station_id:
        print(f"\n  Nearest EA station: {ea_station_id} ({ea_station_name})")

    # ------------------------------------------------------------------
    # 2. Station detail
    # ------------------------------------------------------------------
    if ea_station_id:
        section("2. Station Detail (EA)")

        result = await runner.run(
            "tides_describe_station",
            station_id=ea_station_id, provider="ea",
            output_mode="text",
        )
        print(result)

    # ------------------------------------------------------------------
    # 3. Latest water level
    # ------------------------------------------------------------------
    if ea_station_id:
        section("3. Latest Water Level")

        narrative("""
            What is the current water level at the nearest gauge?
            This tells us whether the Strood is currently passable.
        """)

        result = await runner.run(
            "tides_latest",
            station_id=ea_station_id, provider="ea",
            output_mode="text",
        )
        print(result)

    # ------------------------------------------------------------------
    # 4. Recent observations
    # ------------------------------------------------------------------
    if ea_station_id:
        section("4. Recent Observations (Last 24h)")

        narrative("""
            Pull the last 24 hours of water level readings to see
            the tidal pattern and identify peak levels.
        """)

        result = await runner.run(
            "tides_observations",
            station_id=ea_station_id, provider="ea",
            start_date="today",
            output_mode="text",
        )
        print(result)

    # ------------------------------------------------------------------
    # 5. Cross-reference with NOAA (global perspective)
    # ------------------------------------------------------------------
    section("5. Sea Level Context — The Battery, New York")

    narrative("""
        For context, let's compare with a well-studied US station.
        The Battery (NYC) has 160+ years of sea level data.
        This shows the kind of long-term analysis available.
    """)

    # The Battery, NYC
    battery_id = "8518750"

    result = await runner.run(
        "tides_sea_level_trend",
        station_id=battery_id, provider="noaa",
        output_mode="text",
    )
    print(result)

    # ------------------------------------------------------------------
    # 6. NOAA flood outlook for comparison
    # ------------------------------------------------------------------
    section("6. NOAA Flood Outlook — The Battery, NYC")

    narrative("""
        NOAA provides high-tide flooding outlooks for US stations.
        This shows how many flood events are expected per year.
    """)

    result = await runner.run(
        "tides_flood_outlook",
        station_id=battery_id, output_mode="text",
    )
    print(result)

    # ------------------------------------------------------------------
    # 7. Server capabilities
    # ------------------------------------------------------------------
    section("7. Available Analysis Capabilities")

    narrative("""
        The server provides 17 tools. Here's a summary of what
        an LLM could use to continue this analysis:
    """)

    result = await runner.run("tides_capabilities", output_mode="text")
    print(result)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    section("Scenario Summary")

    narrative("""
        This scenario demonstrated a real-world coastal flood
        assessment workflow:

        1. Station discovery — found gauges near Mersea Island
        2. Live observations — current and recent water levels
        3. Long-term context — sea level trends (NYC comparison)
        4. Flood risk — NOAA high-tide flooding outlook
        5. Planning — server capabilities for further analysis

        An LLM agent would continue by:
        - Getting UKHO predictions for UK tidal forecasts
        - Running threshold exceedance analysis
        - Projecting future flooding under SLR scenarios
        - Building a flooding calendar for the year
        - Cross-referencing with satellite imagery (chuk-mcp-stac)
        - Overlaying with terrain data (chuk-mcp-dem)
    """)

    print(f"{'=' * 60}")
    print("  Scenario complete!")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
