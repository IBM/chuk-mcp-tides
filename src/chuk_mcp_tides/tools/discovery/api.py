"""
Discovery tools for chuk-mcp-tides.

Tools: tides_status, tides_capabilities
"""

import logging
import os

from ...constants import (
    PROVIDER_INFO,
    EnvVar,
    ServerConfig,
    StorageProvider,
    TideProvider,
)
from ...core.tide_manager import TideManager
from ...models.responses import (
    ErrorResponse,
    ProviderStatus,
    StatusResponse,
    format_response,
)

logger = logging.getLogger(__name__)


def register_discovery_tools(mcp: object, manager: TideManager) -> None:
    """Register discovery tools with the MCP server."""

    @mcp.tool  # type: ignore[union-attr]
    async def tides_status(
        output_mode: str = "json",
    ) -> str:
        """Get server status and configuration."""
        try:
            storage = os.environ.get(
                EnvVar.ARTIFACTS_PROVIDER, StorageProvider.MEMORY.value
            )
            ukho_key = os.environ.get(EnvVar.UKHO_API_KEY)

            providers = []
            for tp in TideProvider:
                info = PROVIDER_INFO[tp]
                auth_configured = True
                if tp == TideProvider.UKHO:
                    auth_configured = bool(ukho_key)
                providers.append(
                    ProviderStatus(
                        name=info["name"],
                        available=True,
                        station_count=info["station_count"],
                        auth_configured=auth_configured,
                    )
                )

            response = StatusResponse(
                server=ServerConfig.NAME.value,
                version=ServerConfig.VERSION.value,
                storage_provider=storage,
                providers=providers,
                harmonic_engine="utide (not yet installed)",
                stored_constituents=0,
            )
            return format_response(response, output_mode)
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)

    @mcp.tool  # type: ignore[union-attr]
    async def tides_capabilities(
        output_mode: str = "json",
    ) -> str:
        """List full server capabilities for LLM workflow planning."""
        try:
            return format_response(
                ErrorResponse(error="Capabilities not yet implemented"),
                output_mode,
            )
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)
