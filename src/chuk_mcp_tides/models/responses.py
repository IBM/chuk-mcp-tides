"""
Pydantic v2 response models for chuk-mcp-tides.

All models use extra="forbid" and provide a to_text() method
for dual output mode (JSON + human-readable text).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


def format_response(model: BaseModel, output_mode: str = "json") -> str:
    """Format a response model as JSON or text."""
    if output_mode == "text" and hasattr(model, "to_text"):
        return model.to_text()
    return model.model_dump_json(indent=2)


# ─── Common / Shared ────────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: str

    def to_text(self) -> str:
        return f"Error: {self.error}"


class SuccessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str

    def to_text(self) -> str:
        return self.message


# ─── Station Discovery ──────────────────────────────────────────────────────


class StationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    station_id: str
    name: str
    lat: float
    lon: float
    station_type: str | None = None
    provider: str | None = None
    date_range: list[str] | None = None


class StationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    station_count: int
    stations: list[StationSummary]
    search_location: list[float] | None = None
    search_radius_km: float | None = None
    message: str

    def to_text(self) -> str:
        lines = [self.message, ""]
        for s in self.stations:
            loc = f"({s.lat:.4f}, {s.lon:.4f})"
            lines.append(f"  {s.station_id}: {s.name} {loc}")
        return "\n".join(lines)


class DatumInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    value: float
    description: str | None = None


class ConstituentInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    amplitude: float
    phase: float
    speed: float | None = None


class FloodThresholdInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    minor: float | None = None
    moderate: float | None = None
    major: float | None = None


class StationDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    station_id: str
    name: str
    provider: str
    lat: float
    lon: float
    datums: list[DatumInfo] = []
    sensors: list[str] = []
    data_range: list[str] | None = None
    tidal_type: str | None = None
    harmonic_constituents: list[ConstituentInfo] | None = None
    flood_thresholds: FloodThresholdInfo | None = None
    mean_sea_level_trend: float | None = None
    linked_station: str | None = None
    message: str

    def to_text(self) -> str:
        lines = [
            f"{self.name} ({self.station_id})",
            f"Provider: {self.provider}",
            f"Location: ({self.lat:.4f}, {self.lon:.4f})",
        ]
        if self.tidal_type:
            lines.append(f"Tidal type: {self.tidal_type}")
        if self.data_range:
            lines.append(f"Data range: {self.data_range[0]} to {self.data_range[1]}")
        if self.datums:
            lines.append(f"Datums: {len(self.datums)} available")
        if self.flood_thresholds:
            ft = self.flood_thresholds
            parts = []
            if ft.minor is not None:
                parts.append(f"minor={ft.minor:.2f}m")
            if ft.moderate is not None:
                parts.append(f"moderate={ft.moderate:.2f}m")
            if ft.major is not None:
                parts.append(f"major={ft.major:.2f}m")
            if parts:
                lines.append(f"Flood thresholds: {', '.join(parts)}")
        if self.mean_sea_level_trend is not None:
            lines.append(f"Sea level trend: {self.mean_sea_level_trend:.2f} mm/yr")
        if self.harmonic_constituents:
            lines.append(f"Harmonic constituents: {len(self.harmonic_constituents)}")
        return "\n".join(lines)


class NearestStation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    station_id: str
    name: str
    lat: float
    lon: float
    provider: str
    distance_km: float


class NearestStationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    search_location: list[float]
    stations: list[NearestStation]
    message: str

    def to_text(self) -> str:
        lines = [self.message, ""]
        for s in self.stations:
            lines.append(f"  {s.distance_km:.1f} km: {s.name} ({s.station_id}) [{s.provider}]")
        return "\n".join(lines)


# ─── Predictions ─────────────────────────────────────────────────────────────


class TidalEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    datetime: str
    height: float
    event_type: str | None = None  # high, low, intermediate


class PredictionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    station_id: str
    station_name: str
    provider: str
    datum: str
    units: str
    start_date: str
    end_date: str
    interval: str
    event_count: int
    predictions: list[TidalEvent]
    artifact_ref: str | None = None
    message: str

    def to_text(self) -> str:
        lines = [
            self.message,
            f"Station: {self.station_name} ({self.station_id})",
            f"Period: {self.start_date} to {self.end_date}",
            f"Datum: {self.datum}, Units: {self.units}",
            f"Events: {self.event_count}",
            "",
        ]
        for ev in self.predictions[:20]:
            tag = f" [{ev.event_type}]" if ev.event_type else ""
            lines.append(f"  {ev.datetime}  {ev.height:+.3f}m{tag}")
        if self.event_count > 20:
            lines.append(f"  ... and {self.event_count - 20} more")
        return "\n".join(lines)


class LocalPredictionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    station_id: str | None = None
    constituent_count: int
    start_date: str
    end_date: str
    interval_minutes: int
    event_count: int
    predictions: list[TidalEvent]
    highs_lows: list[TidalEvent]
    artifact_ref: str | None = None
    message: str

    def to_text(self) -> str:
        lines = [
            self.message,
            f"Constituents: {self.constituent_count}",
            f"Period: {self.start_date} to {self.end_date}",
            f"Interval: {self.interval_minutes} min",
            f"Total points: {self.event_count}",
            f"Highs/Lows: {len(self.highs_lows)}",
            "",
        ]
        for ev in self.highs_lows[:20]:
            tag = f" [{ev.event_type}]" if ev.event_type else ""
            lines.append(f"  {ev.datetime}  {ev.height:+.3f}m{tag}")
        if len(self.highs_lows) > 20:
            lines.append(f"  ... and {len(self.highs_lows) - 20} more")
        return "\n".join(lines)


# ─── Observations ────────────────────────────────────────────────────────────


class WaterLevelReading(BaseModel):
    model_config = ConfigDict(extra="forbid")
    datetime: str
    value: float
    quality: str | None = None
    anomaly: float | None = None


class ObservationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    station_id: str
    station_name: str
    provider: str
    datum: str
    units: str
    product: str
    reading_count: int
    readings: list[WaterLevelReading]
    artifact_ref: str | None = None
    message: str

    def to_text(self) -> str:
        lines = [
            self.message,
            f"Station: {self.station_name} ({self.station_id})",
            f"Product: {self.product}",
            f"Datum: {self.datum}, Units: {self.units}",
            f"Readings: {self.reading_count}",
            "",
        ]
        for r in self.readings[:20]:
            q = f" [{r.quality}]" if r.quality else ""
            lines.append(f"  {r.datetime}  {r.value:+.3f}m{q}")
        if self.reading_count > 20:
            lines.append(f"  ... and {self.reading_count - 20} more")
        return "\n".join(lines)


class LatestReadingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    station_id: str
    station_name: str
    datetime: str
    value: float
    datum: str
    units: str
    next_high: TidalEvent | None = None
    next_low: TidalEvent | None = None
    tide_state: str  # rising, falling, high_slack, low_slack
    message: str

    def to_text(self) -> str:
        lines = [
            self.message,
            f"Station: {self.station_name} ({self.station_id})",
            f"Time: {self.datetime}",
            f"Level: {self.value:+.3f}m ({self.datum})",
            f"Tide: {self.tide_state}",
        ]
        if self.next_high:
            lines.append(f"Next high: {self.next_high.datetime} ({self.next_high.height:+.3f}m)")
        if self.next_low:
            lines.append(f"Next low: {self.next_low.datetime} ({self.next_low.height:+.3f}m)")
        return "\n".join(lines)


# ─── Analysis: Threshold Exceedance ──────────────────────────────────────────


class ExceedanceGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period: str
    count: int
    max_height: float
    total_hours: float


class TrendInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slope: float  # exceedances per year
    intercept: float
    r_squared: float


class ThresholdExceedanceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    station_id: str
    threshold: float
    datum: str
    source: str
    total_exceedances: int
    total_hours_above: float
    groups: list[ExceedanceGroup]
    trend: TrendInfo | None = None
    artifact_ref: str | None = None
    message: str

    def to_text(self) -> str:
        lines = [
            self.message,
            f"Threshold: {self.threshold:.2f}m ({self.datum})",
            f"Source: {self.source}",
            f"Total exceedances: {self.total_exceedances}",
            f"Total hours above: {self.total_hours_above:.1f}",
            "",
        ]
        for g in self.groups:
            lines.append(f"  {g.period}: {g.count} events, max {g.max_height:.3f}m, "
                         f"{g.total_hours:.1f}h above")
        if self.trend:
            lines.append(f"\nTrend: {self.trend.slope:+.2f} exceedances/year "
                         f"(R²={self.trend.r_squared:.3f})")
        return "\n".join(lines)


# ─── Analysis: Flood Projection ──────────────────────────────────────────────


class FloodProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    year: int
    scenario: str
    slr_mm: float
    projected_exceedances: int
    projected_hours: float
    delta_from_baseline: int


class TippingPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: str
    double_year: int | None = None
    tenfold_year: int | None = None
    daily_year: int | None = None


class FloodProjectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    station_id: str
    station_name: str
    threshold: float
    datum: str
    baseline_year: int
    baseline_exceedances: int
    projections: list[FloodProjection]
    tipping_points: list[TippingPoint]
    artifact_ref: str | None = None
    message: str

    def to_text(self) -> str:
        lines = [
            self.message,
            f"Threshold: {self.threshold:.2f}m ({self.datum})",
            f"Baseline ({self.baseline_year}): {self.baseline_exceedances} exceedances",
            "",
        ]
        current_scenario = None
        for p in self.projections:
            if p.scenario != current_scenario:
                current_scenario = p.scenario
                lines.append(f"  {p.scenario}:")
            lines.append(
                f"    {p.year}: {p.projected_exceedances} exceedances "
                f"(+{p.slr_mm:.0f}mm SLR, {p.delta_from_baseline:+d} from baseline)"
            )
        if self.tipping_points:
            lines.append("\nTipping points:")
            for tp in self.tipping_points:
                parts = []
                if tp.double_year:
                    parts.append(f"2x by {tp.double_year}")
                if tp.tenfold_year:
                    parts.append(f"10x by {tp.tenfold_year}")
                if tp.daily_year:
                    parts.append(f"daily by {tp.daily_year}")
                lines.append(f"  {tp.scenario}: {', '.join(parts)}")
        return "\n".join(lines)


# ─── Analysis: Harmonic ──────────────────────────────────────────────────────


class ConstituentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    amplitude: float
    phase: float
    frequency: float | None = None
    snr: float | None = None


class HarmonicAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    station_id: str
    observation_days: int
    constituent_count: int
    constituents: list[ConstituentResult]
    mean_level: float
    form_number: float
    tidal_type: str  # semidiurnal, mixed, diurnal
    residual_std: float
    stored: bool
    message: str

    def to_text(self) -> str:
        lines = [
            self.message,
            f"Station: {self.station_id}",
            f"Observation period: {self.observation_days} days",
            f"Constituents resolved: {self.constituent_count}",
            f"Mean level (Z0): {self.mean_level:.3f}m",
            f"Form number: {self.form_number:.3f} ({self.tidal_type})",
            f"Residual std: {self.residual_std:.3f}m",
            f"Stored: {self.stored}",
            "",
            "Major constituents:",
        ]
        for c in self.constituents[:10]:
            snr = f" SNR={c.snr:.1f}" if c.snr is not None else ""
            lines.append(f"  {c.name:>4s}: A={c.amplitude:.4f}m  φ={c.phase:.1f}°{snr}")
        return "\n".join(lines)


# ─── Analysis: Residual ──────────────────────────────────────────────────────


class SurgeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: str | None = None
    end: str | None = None
    peak_datetime: str
    peak_residual: float
    duration_hours: float | None = None


class ResidualPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    datetime: str
    observed: float
    predicted: float
    residual: float


class ResidualResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    station_id: str
    reading_count: int
    max_positive_surge: SurgeEvent
    max_negative_surge: SurgeEvent
    mean_residual: float
    std_residual: float
    surge_events: list[SurgeEvent]
    residuals: list[ResidualPoint]
    artifact_ref: str | None = None
    message: str

    def to_text(self) -> str:
        lines = [
            self.message,
            f"Station: {self.station_id}",
            f"Readings: {self.reading_count}",
            f"Max positive surge: {self.max_positive_surge.peak_residual:+.3f}m "
            f"at {self.max_positive_surge.peak_datetime}",
            f"Max negative surge: {self.max_negative_surge.peak_residual:+.3f}m "
            f"at {self.max_negative_surge.peak_datetime}",
            f"Mean residual: {self.mean_residual:+.4f}m",
            f"Std residual: {self.std_residual:.4f}m",
            f"Surge events (>{0.3}m): {len(self.surge_events)}",
        ]
        return "\n".join(lines)


# ─── Analysis: Sea Level Trend ───────────────────────────────────────────────


class MonthlyMean(BaseModel):
    model_config = ConfigDict(extra="forbid")
    year: int
    month: int
    value: float


class SeaLevelTrendResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    station_id: str
    station_name: str
    trend_mm_per_year: float
    trend_uncertainty: float
    first_year: int
    last_year: int
    record_length_years: int
    monthly_means: list[MonthlyMean] | None = None
    data_source: str
    message: str

    def to_text(self) -> str:
        return (
            f"{self.station_name} ({self.station_id})\n"
            f"Sea level trend: {self.trend_mm_per_year:+.2f} ± {self.trend_uncertainty:.2f} mm/yr\n"
            f"Record: {self.first_year}–{self.last_year} ({self.record_length_years} years)\n"
            f"Source: {self.data_source}"
        )


# ─── Analysis: Extreme Levels ───────────────────────────────────────────────


class ExtremeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: str
    height: float
    event_name: str | None = None


class ExtremeLevelsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    station_id: str
    top_ten_high: list[ExtremeEvent]
    top_ten_low: list[ExtremeEvent]
    datum: str
    message: str

    def to_text(self) -> str:
        lines = [self.message, "", "Highest levels:"]
        for i, e in enumerate(self.top_ten_high, 1):
            name = f" ({e.event_name})" if e.event_name else ""
            lines.append(f"  {i}. {e.date}: {e.height:+.3f}m{name}")
        lines.append("\nLowest levels:")
        for i, e in enumerate(self.top_ten_low, 1):
            name = f" ({e.event_name})" if e.event_name else ""
            lines.append(f"  {i}. {e.date}: {e.height:+.3f}m{name}")
        return "\n".join(lines)


# ─── Flood Risk: Outlook ─────────────────────────────────────────────────────


class FloodCount(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period: str
    count: int


class FloodProjectionNOAA(BaseModel):
    model_config = ConfigDict(extra="forbid")
    year: int
    expected: int
    low: int
    high: int


class FloodOutlookResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    station_id: str
    product: str
    flood_threshold: str
    flood_level_m: float
    counts: list[FloodCount]
    projection: FloodProjectionNOAA | None = None
    message: str

    def to_text(self) -> str:
        lines = [
            self.message,
            f"Threshold: {self.flood_threshold} ({self.flood_level_m:.2f}m)",
            "",
        ]
        for c in self.counts:
            lines.append(f"  {c.period}: {c.count} flood events")
        if self.projection:
            p = self.projection
            lines.append(f"\nProjection ({p.year}): {p.expected} events "
                         f"(range: {p.low}–{p.high})")
        return "\n".join(lines)


# ─── Flood Risk: Calendar ────────────────────────────────────────────────────


class MonthFloodSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    month: int
    flood_days: int
    max_height: float
    total_hours: float


class FloodDay(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: str
    peak_height: float
    duration_hours: float
    tides_above: int


class FloodingCalendarResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    station_id: str
    year: int
    threshold: float
    slr_offset_mm: float
    datum: str
    total_flood_days: int
    total_flood_hours: float
    monthly_summary: list[MonthFloodSummary]
    flood_days: list[FloodDay]
    artifact_ref: str | None = None
    message: str

    def to_text(self) -> str:
        lines = [
            self.message,
            f"Year: {self.year}",
            f"Threshold: {self.threshold:.2f}m ({self.datum})",
        ]
        if self.slr_offset_mm:
            lines.append(f"SLR offset: +{self.slr_offset_mm:.0f}mm")
        lines.append(f"Total flood days: {self.total_flood_days}")
        lines.append(f"Total flood hours: {self.total_flood_hours:.1f}")
        lines.append("")
        month_names = [
            "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ]
        for ms in self.monthly_summary:
            if ms.flood_days > 0:
                lines.append(
                    f"  {month_names[ms.month]:>3s}: {ms.flood_days} days, "
                    f"max {ms.max_height:.3f}m, {ms.total_hours:.1f}h"
                )
        return "\n".join(lines)


# ─── Discovery ───────────────────────────────────────────────────────────────


class ProviderStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    available: bool
    station_count: int
    auth_configured: bool


class StatusResponse(BaseModel):
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


class ProviderInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    short_name: str
    coverage: str
    auth_required: bool
    station_count: int
    url: str | None = None


class DatumInfoCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    full_name: str
    notes: str | None = None


class ScenarioInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    rate_mm_yr: float
    source: str


class WorkflowInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str
    servers: list[str]


class CapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    server: str
    version: str
    providers: list[ProviderInfo]
    datums: list[DatumInfoCapability]
    scenarios: list[ScenarioInfo]
    tool_count: int
    cross_server_workflows: list[WorkflowInfo]

    def to_text(self) -> str:
        lines = [
            f"{self.server} v{self.version}",
            f"Tools: {self.tool_count}",
            "",
            "Providers:",
        ]
        for p in self.providers:
            auth = " (API key required)" if p.auth_required else " (free)"
            lines.append(f"  {p.short_name}: {p.name} — {p.coverage}{auth}")
        lines.append(f"\nDatums: {len(self.datums)}")
        for d in self.datums:
            lines.append(f"  {d.name}: {d.full_name}")
        lines.append(f"\nSLR Scenarios: {len(self.scenarios)}")
        for s in self.scenarios:
            lines.append(f"  {s.name}: {s.rate_mm_yr} mm/yr ({s.source})")
        if self.cross_server_workflows:
            lines.append("\nCross-server workflows:")
            for w in self.cross_server_workflows:
                lines.append(f"  {w.name}: {w.description}")
        return "\n".join(lines)
