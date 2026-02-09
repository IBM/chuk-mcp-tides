#!/usr/bin/env python3
"""
Tool Runner for chuk-mcp-tides

Utility for running MCP tools standalone without a full MCP runtime.
Captures tools registered via @mcp.tool decorators and provides
a simple interface for testing and demos.

18 tools across 6 categories.
"""

import asyncio
import json
import sys


class ToolRunner:
    """Captures MCP tool registrations and runs them standalone."""

    def __init__(self) -> None:
        self._tools: dict[str, object] = {}

    def tool(self, fn: object) -> object:
        self._tools[fn.__name__] = fn
        return fn

    async def run(self, name: str, **kwargs: object) -> str:
        if name not in self._tools:
            available = ", ".join(sorted(self._tools.keys()))
            raise ValueError(f"Unknown tool '{name}'. Available: {available}")
        result = await self._tools[name](**kwargs)
        return result

    def list_tools(self) -> list[str]:
        return sorted(self._tools.keys())


def create_runner() -> ToolRunner:
    """Create a ToolRunner with all chuk-mcp-tides tools registered."""
    runner = ToolRunner()

    from chuk_mcp_tides.core.tide_manager import TideManager

    manager = TideManager()

    from chuk_mcp_tides.tools.analysis import register_analysis_tools
    from chuk_mcp_tides.tools.discovery import register_discovery_tools
    from chuk_mcp_tides.tools.flood import register_flood_tools
    from chuk_mcp_tides.tools.observations import register_observation_tools
    from chuk_mcp_tides.tools.predictions import register_prediction_tools
    from chuk_mcp_tides.tools.stations import register_station_tools

    register_station_tools(runner, manager)
    register_prediction_tools(runner, manager)
    register_observation_tools(runner, manager)
    register_analysis_tools(runner, manager)
    register_flood_tools(runner, manager)
    register_discovery_tools(runner, manager)

    return runner


async def main() -> None:
    runner = create_runner()

    if len(sys.argv) < 2:
        print("Available tools:")
        for name in runner.list_tools():
            print(f"  {name}")
        return

    tool_name = sys.argv[1]
    result = await runner.run(tool_name)
    parsed = json.loads(result)
    print(json.dumps(parsed, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
