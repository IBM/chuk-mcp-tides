"""
MCP tool modules for chuk-mcp-tides.
"""

from .analysis import register_analysis_tools
from .currents import register_currents_tools
from .discovery import register_discovery_tools
from .flood import register_flood_tools
from .observations import register_observation_tools
from .predictions import register_prediction_tools
from .stations import register_station_tools

__all__ = [
    "register_station_tools",
    "register_prediction_tools",
    "register_observation_tools",
    "register_analysis_tools",
    "register_flood_tools",
    "register_currents_tools",
    "register_discovery_tools",
]
