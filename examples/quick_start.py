#!/usr/bin/env python3
"""
Quick Start — NOAA Tide Stations (No API Key Required)

Demonstrates the core workflow:
  1. Find stations near a location
  2. Get tide predictions
  3. Get the latest reading with tide state
  4. Get sea level trend
  5. Get historical extreme levels
"""

import asyncio
import json
import sys

sys.path.insert(0, ".")
from tool_runner import create_runner


def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}\n")


async def main() -> None:
    runner = create_runner()

    print("=" * 60)
    print("  chuk-mcp-tides — Quick Start Demo")
    print("  NOAA CO-OPS Provider (no API key required)")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Find stations near Providence, Rhode Island
    # ------------------------------------------------------------------
    section("1. Find Nearest Stations to Providence, RI")

    result = await runner.run(
        "tides_find_nearest",
        lat=41.8,
        lon=-71.4,
        provider="noaa",
        max_results=3,
        output_mode="text",
    )
    print(result)

    # Also get the JSON to extract station_id
    result_json = await runner.run(
        "tides_find_nearest",
        lat=41.8,
        lon=-71.4,
        provider="noaa",
        max_results=1,
    )
    nearest = json.loads(result_json)
    station_id = nearest["stations"][0]["station_id"]
    station_name = nearest["stations"][0]["name"]
    print(f"\n  Using station: {station_id} ({station_name})")

    # ------------------------------------------------------------------
    # 2. Get station detail
    # ------------------------------------------------------------------
    section("2. Station Detail")

    result = await runner.run(
        "tides_describe_station",
        station_id=station_id,
        provider="noaa",
        output_mode="text",
    )
    print(result)

    # ------------------------------------------------------------------
    # 3. Get tide predictions for the next 7 days
    # ------------------------------------------------------------------
    section("3. Tide Predictions (Hi/Lo, Next 7 Days)")

    result = await runner.run(
        "tides_predict",
        station_id=station_id,
        provider="noaa",
        start_date="today",
        interval="hilo",
        output_mode="text",
    )
    print(result)

    # ------------------------------------------------------------------
    # 4. Get the latest reading
    # ------------------------------------------------------------------
    section("4. Latest Water Level")

    result = await runner.run(
        "tides_latest",
        station_id=station_id,
        provider="noaa",
        output_mode="text",
    )
    print(result)

    # ------------------------------------------------------------------
    # 5. Sea level trend
    # ------------------------------------------------------------------
    section("5. Sea Level Trend")

    result = await runner.run(
        "tides_sea_level_trend",
        station_id=station_id,
        provider="noaa",
        output_mode="text",
    )
    print(result)

    # ------------------------------------------------------------------
    # 6. Historical extreme levels
    # ------------------------------------------------------------------
    section("6. Historical Extreme Water Levels")

    result = await runner.run(
        "tides_extreme_levels",
        station_id=station_id,
        provider="noaa",
        output_mode="text",
    )
    print(result)

    print(f"\n{'=' * 60}")
    print("  Demo complete!")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
