#!/usr/bin/env python3
"""
Async Tides MCP Server using chuk-mcp-server

Tidal data discovery and analysis via multiple tide gauge networks.
Predictions, observations, harmonic analysis, and flood risk assessment
from NOAA CO-OPS, EA, UKHO, and a local harmonic engine.

Storage is managed through chuk-mcp-server's built-in artifact store context.
"""

import logging

from chuk_mcp_server import ChukMCPServer

from .core.tide_manager import TideManager
from .tools.analysis import register_analysis_tools
from .tools.discovery import register_discovery_tools
from .tools.flood import register_flood_tools
from .tools.observations import register_observation_tools
from .tools.predictions import register_prediction_tools
from .tools.stations import register_station_tools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the MCP server instance
mcp = ChukMCPServer("chuk-mcp-tides")

# Create tide manager instance
manager = TideManager()

# Register all tool modules
register_station_tools(mcp, manager)
register_prediction_tools(mcp, manager)
register_observation_tools(mcp, manager)
register_analysis_tools(mcp, manager)
register_flood_tools(mcp, manager)
register_discovery_tools(mcp, manager)

# Run the server
if __name__ == "__main__":
    logger.info("Starting Tides MCP Server...")
    logger.info("Storage: Using chuk-mcp-server artifact store context")
    mcp.run(stdio=True)
