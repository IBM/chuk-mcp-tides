#!/usr/bin/env python3
"""
Capabilities Demo — No Network Required

Shows server status and registered tool information.
Runs entirely offline using the discovery tools.
"""

import asyncio
import json

from tool_runner import create_runner


async def main() -> None:
    runner = create_runner()

    print("=" * 60)
    print("chuk-mcp-tides — Capabilities Demo")
    print("=" * 60)
    print()

    # List all registered tools
    tools = runner.list_tools()
    print(f"Registered tools ({len(tools)}):")
    for name in tools:
        print(f"  - {name}")
    print()

    # Get server status
    print("Server Status:")
    print("-" * 40)
    result = await runner.run("tides_status", output_mode="text")
    print(result)
    print()

    # JSON format
    print("Status (JSON):")
    print("-" * 40)
    result = await runner.run("tides_status", output_mode="json")
    parsed = json.loads(result)
    print(json.dumps(parsed, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
