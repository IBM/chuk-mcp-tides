"""
Discovery tools for chuk-mcp-tides.

Tools: tides_status, tides_capabilities
"""

import logging
import os

from ...constants import (
    DATUM_NAMES,
    PROVIDER_INFO,
    PROVIDER_URLS,
    SLR_SCENARIOS,
    Datum,
    EnvVar,
    ServerConfig,
    StorageProvider,
    TideProvider,
)
from ...core.tide_manager import TideManager
from ...models.responses import (
    CapabilitiesResponse,
    DatumInfoCapability,
    ErrorResponse,
    ProviderInfo,
    ProviderStatus,
    ScenarioInfo,
    StatusResponse,
    WorkflowInfo,
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
            # Determine storage provider name
            try:
                local_prov = manager._get_provider(TideProvider.LOCAL)
                storage = local_prov.storage.storage_provider
            except Exception:
                storage = os.environ.get(
                    EnvVar.ARTIFACTS_PROVIDER, StorageProvider.MEMORY.value
                )
            ukho_key = os.environ.get(EnvVar.UKHO_API_KEY)

            # Detect utide availability
            try:
                import utide  # noqa: F401
                harmonic_engine = "utide"
            except ImportError:
                harmonic_engine = "utide (not installed)"

            # Count stored constituents via storage abstraction
            stored = 0
            try:
                local_prov = manager._get_provider(TideProvider.LOCAL)
                stored = local_prov.storage.stored_count()
            except Exception:
                pass

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
                harmonic_engine=harmonic_engine,
                stored_constituents=stored,
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
            # Build provider info
            providers = []
            for tp in TideProvider:
                info = PROVIDER_INFO[tp]
                providers.append(ProviderInfo(
                    name=info["name"],
                    short_name=tp.value,
                    coverage=info["coverage"],
                    auth_required=info["auth"],
                    station_count=info["station_count"],
                    url=PROVIDER_URLS.get(tp),
                ))

            # Build datum info
            datums = [
                DatumInfoCapability(
                    name=d.value,
                    full_name=DATUM_NAMES[d],
                )
                for d in Datum
            ]

            # Build SLR scenario info
            scenarios = [
                ScenarioInfo(
                    name=name,
                    rate_mm_yr=info["rate_mm_yr"],
                    source=info["source"],
                )
                for name, info in SLR_SCENARIOS.items()
            ]

            # Cross-server workflows
            workflows = [
                WorkflowInfo(
                    name="Historical voyage + tide analysis",
                    description=(
                        "Use maritime-archives to find a voyage, "
                        "then analyze tidal conditions at ports of call"
                    ),
                    servers=["chuk-mcp-maritime-archives", "chuk-mcp-tides"],
                ),
                WorkflowInfo(
                    name="Coastal asset risk assessment",
                    description=(
                        "Use STAC to find coastal imagery, "
                        "then assess flood risk with tide projections"
                    ),
                    servers=["chuk-mcp-stac", "chuk-mcp-tides"],
                ),
            ]

            response = CapabilitiesResponse(
                server=ServerConfig.NAME.value,
                version=ServerConfig.VERSION.value,
                providers=providers,
                datums=datums,
                scenarios=scenarios,
                tool_count=17,
                cross_server_workflows=workflows,
            )
            return format_response(response, output_mode)
        except Exception as e:
            return format_response(ErrorResponse(error=str(e)), output_mode)
