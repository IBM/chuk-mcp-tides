"""
Pydantic v2 response models for chuk-mcp-tides.

All models use extra="forbid" and provide a to_text() method
for dual output mode (JSON + human-readable text).
"""

from pydantic import BaseModel, ConfigDict


def format_response(model: "BaseModel", output_mode: str = "json") -> str:
    """Format a response model as JSON or text."""
    if output_mode == "text" and hasattr(model, "to_text"):
        return model.to_text()  # type: ignore[union-attr]
    return model.model_dump_json(indent=2)


class ErrorResponse(BaseModel):
    """Standard error response."""

    model_config = ConfigDict(extra="forbid")

    error: str

    def to_text(self) -> str:
        return f"Error: {self.error}"


class SuccessResponse(BaseModel):
    """Generic success response."""

    model_config = ConfigDict(extra="forbid")

    message: str

    def to_text(self) -> str:
        return self.message


class ProviderStatus(BaseModel):
    """Status of a single provider."""

    model_config = ConfigDict(extra="forbid")

    name: str
    available: bool
    station_count: int
    auth_configured: bool


class StatusResponse(BaseModel):
    """Server status response."""

    model_config = ConfigDict(extra="forbid")

    server: str
    version: str
    storage_provider: str
    providers: list[ProviderStatus]
    harmonic_engine: str
    stored_constituents: int

    def to_text(self) -> str:
        lines = [
            f"{self.server} v{self.version}",
            f"Storage: {self.storage_provider}",
            f"Harmonic engine: {self.harmonic_engine}",
            f"Stored constituents: {self.stored_constituents}",
            "",
            "Providers:",
        ]
        for p in self.providers:
            status = "available" if p.available else "unavailable"
            auth = " (auth configured)" if p.auth_configured else ""
            lines.append(f"  {p.name}: {status}, {p.station_count} stations{auth}")
        return "\n".join(lines)
