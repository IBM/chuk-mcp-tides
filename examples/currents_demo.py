#!/usr/bin/env python3
"""
Tidal Currents Demo — NOAA Current Stations (No API Key Required)

Demonstrates the tidal currents workflow:
  1. Find current stations near a location
  2. Get current predictions (slack, flood, ebb events)
  3. Get the latest current observation
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
    print("  chuk-mcp-tides — Tidal Currents Demo")
    print("  NOAA CO-OPS Current Stations (no API key required)")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Find current stations near Puget Sound, Washington
    # ------------------------------------------------------------------
    section("1. Find Current Stations near Puget Sound, WA")

    result = await runner.run(
        "tides_currents_stations",
        lat=48.23,
        lon=-122.73,
        radius_km=50,
        max_results=5,
        output_mode="text",
    )
    print(result)

    # Get the JSON to extract a station_id and bin_number
    result_json = await runner.run(
        "tides_currents_stations",
        lat=48.23,
        lon=-122.73,
        radius_km=50,
        max_results=1,
    )
    nearest = json.loads(result_json)
    if not nearest.get("stations"):
        print("\n  No current stations found in this area. Trying wider search...")
        result_json = await runner.run(
            "tides_currents_stations",
            lat=48.23,
            lon=-122.73,
            radius_km=200,
            max_results=1,
        )
        nearest = json.loads(result_json)

    if nearest.get("stations"):
        station_id = nearest["stations"][0]["station_id"]
        station_name = nearest["stations"][0]["name"]
        bin_number = nearest["stations"][0].get("bin_number")
        print(f"\n  Using station: {station_id} ({station_name}), bin={bin_number}")
    else:
        print("\n  No current stations found. Exiting.")
        return

    # Build bin kwarg — pass bin only if we have one from metadata
    bin_kwargs = {"bin": str(bin_number)} if bin_number else {}

    # ------------------------------------------------------------------
    # 2. Get current predictions (MAX_SLACK — slack, max flood, max ebb)
    # ------------------------------------------------------------------
    section("2. Current Predictions (MAX_SLACK, Next 2 Days)")

    result = await runner.run(
        "tides_currents_predictions",
        station_id=station_id,
        start_date="today",
        interval="MAX_SLACK",
        output_mode="text",
        **bin_kwargs,
    )
    print(result)

    # ------------------------------------------------------------------
    # 3. Get current predictions (6-minute interval for detail)
    # ------------------------------------------------------------------
    section("3. Current Predictions (6-Minute Interval, First 20)")

    result = await runner.run(
        "tides_currents_predictions",
        station_id=station_id,
        start_date="today",
        interval="6",
        output_mode="text",
        **bin_kwargs,
    )
    print(result)

    # ------------------------------------------------------------------
    # 4. Show JSON output for programmatic use
    # ------------------------------------------------------------------
    section("4. JSON Output (First 3 Events)")

    result_json = await runner.run(
        "tides_currents_predictions",
        station_id=station_id,
        start_date="today",
        interval="MAX_SLACK",
        **bin_kwargs,
    )
    parsed = json.loads(result_json)
    if "error" in parsed:
        print(f"  Error: {parsed['error']}")
    else:
        summary = {
            "station_id": parsed["station_id"],
            "station_name": parsed["station_name"],
            "interval": parsed["interval"],
            "units": parsed["units"],
            "total_events": parsed["event_count"],
            "first_3_predictions": parsed["predictions"][:3],
        }
        print(json.dumps(summary, indent=2))

    print(f"\n{'=' * 60}")
    print("  Demo complete!")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
