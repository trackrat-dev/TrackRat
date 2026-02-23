"""
Pydantic models for API requests and responses.

These models define the API contract for the V2 backend.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_serializer, field_validator


# Custom serializer for Eastern Time datetimes
def serialize_eastern_datetime(dt: datetime | None) -> str | None:
    """Serialize datetime consistently in Eastern Time.

    Normalizes timezone-aware datetimes to Eastern Time before
    serialization to ensure consistent offset representation
    (-05:00 EST / -04:00 EDT), regardless of how the datetime
    was stored internally (e.g., UTC from PostgreSQL roundtrip).
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        from trackrat.utils.time import normalize_to_et

        dt = normalize_to_et(dt)
    return dt.isoformat()


# Enums


class TrainStatus(str, Enum):
    """Train status values."""

    ON_TIME = "ON_TIME"
    LATE = "LATE"
    CANCELLED = "CANCELLED"
    BOARDING = "BOARDING"
    ALL_ABOARD = "ALL_ABOARD"
    DEPARTED = "DEPARTED"
    IN_TRANSIT = "IN_TRANSIT"
    APPROACHING = "APPROACHING"
    ARRIVED = "ARRIVED"
    UNKNOWN = "UNKNOWN"


# Shared Models


class LineInfo(BaseModel):
    """Train line information."""

    code: str = Field(
        ..., min_length=1, max_length=10
    )  # PATH line codes are ~6-7 chars
    name: str
    color: str = Field(..., pattern="^#[0-9A-Fa-f]{6}$")


class StationInfo(BaseModel):
    """Station information with timing data only."""

    code: str = Field(..., min_length=1, max_length=4)
    name: str
    scheduled_time: datetime | None = None
    updated_time: datetime | None = None
    actual_time: datetime | None = None
    track: str | None = None

    @field_serializer("scheduled_time", "updated_time", "actual_time")
    def serialize_dt(self, dt: datetime | None) -> str | None:
        return serialize_eastern_datetime(dt)


class SimpleStationInfo(BaseModel):
    """Simple station information without timing data."""

    code: str = Field(..., min_length=1, max_length=4)
    name: str


class DataFreshness(BaseModel):
    """Information about data freshness."""

    last_updated: datetime
    age_seconds: int = Field(..., ge=0)
    update_count: int | None = Field(None, ge=0)
    collection_method: Literal["scheduled", "just_in_time"] | None = None

    @field_serializer("last_updated")
    def serialize_dt(self, dt: datetime) -> str:
        return serialize_eastern_datetime(dt) or ""


class CurrentStatus(BaseModel):
    """Current train status information."""

    status: TrainStatus
    status_v2: TrainStatus | None = None
    last_updated: datetime
    delay_minutes: int = Field(default=0, ge=0)

    @field_serializer("last_updated")
    def serialize_dt(self, dt: datetime) -> str:
        return serialize_eastern_datetime(dt) or ""


class JourneyProgress(BaseModel):
    """Journey progress information."""

    stops_completed: int = Field(default=0, ge=0)
    stops_total: int = Field(default=0, ge=0)
    journey_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    minutes_to_arrival: int | None = None
    last_departed: str | None = None
    next_arrival: str | None = None


class TrainPosition(BaseModel):
    """Current train position information."""

    last_departed_station_code: str | None = None
    at_station_code: str | None = None
    next_station_code: str | None = None
    between_stations: bool = False


class TrainDeparture(BaseModel):
    """Train departure information for list view."""

    train_id: str
    journey_date: date
    line: LineInfo
    destination: str
    departure: StationInfo
    arrival: StationInfo | None = None
    train_position: TrainPosition
    data_freshness: DataFreshness
    data_source: str = Field(..., description="Data source (NJT or AMTRAK)")
    observation_type: str = Field(
        default="OBSERVED",
        description="SCHEDULED (from schedule API) or OBSERVED (real-time data)",
    )
    is_cancelled: bool = Field(
        default=False, description="Whether the train is cancelled"
    )
    cancellation_reason: str | None = Field(
        default=None, description="Reason for cancellation if train is cancelled"
    )
    is_expired: bool = Field(
        default=False, description="Train no longer in real-time feed"
    )
    # Progress and prediction fields
    progress: JourneyProgress | None = None
    predicted_arrival: datetime | None = None

    @field_serializer("journey_date")
    def serialize_journey_date(self, journey_date: date) -> str:
        """Serialize date as datetime string for iOS compatibility."""
        return f"{journey_date.isoformat()}T00:00:00"

    @field_serializer("predicted_arrival")
    def serialize_dt(self, dt: datetime | None) -> str | None:
        return serialize_eastern_datetime(dt)


class DeparturesResponse(BaseModel):
    """Response for departures endpoint."""

    departures: list[TrainDeparture]
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        examples=[
            {
                "from_station": {"code": "NP", "name": "Newark Penn Station"},
                "to_station": {"code": "TR", "name": "Trenton"},
                "count": 12,
                "generated_at": "2024-01-15T14:47:00-05:00",
            }
        ],
    )


# Train Details API Models


class RouteInfo(BaseModel):
    """Route information."""

    origin: str
    destination: str
    origin_code: str
    destination_code: str


class RawStopStatus(BaseModel):
    """Raw status information from data source."""

    amtrak_status: str | None = None
    njt_departed_flag: str | None = None


class StopDetails(BaseModel):
    """Detailed information for a single stop."""

    station: SimpleStationInfo
    stop_sequence: int = Field(..., ge=0)
    scheduled_arrival: datetime | None = None
    scheduled_departure: datetime | None = None
    updated_arrival: datetime | None = None
    updated_departure: datetime | None = None
    actual_arrival: datetime | None = None
    actual_departure: datetime | None = None
    track: str | None = None
    track_assigned_at: datetime | None = None
    raw_status: RawStopStatus
    has_departed_station: bool = False

    @field_serializer(
        "scheduled_arrival",
        "scheduled_departure",
        "updated_arrival",
        "updated_departure",
        "actual_arrival",
        "actual_departure",
        "track_assigned_at",
        "predicted_arrival",
    )
    def serialize_dt(self, dt: datetime | None) -> str | None:
        return serialize_eastern_datetime(dt)

    # Prediction fields (added for arrival forecasting)
    predicted_arrival: datetime | None = None
    predicted_arrival_samples: int | None = Field(
        None, ge=0, description="Number of recent trains used for prediction"
    )


class TrainDetails(BaseModel):
    """Complete train journey details."""

    train_id: str
    journey_date: date
    line: LineInfo
    route: RouteInfo
    train_position: TrainPosition
    stops: list[StopDetails]
    data_freshness: DataFreshness
    data_source: str = Field(..., description="Data source (NJT or AMTRAK)")
    observation_type: str = Field(
        default="OBSERVED",
        description="SCHEDULED (from schedule API) or OBSERVED (real-time data)",
    )
    raw_train_state: str | None = None
    is_cancelled: bool = Field(
        default=False, description="Whether the train is cancelled"
    )
    cancellation_reason: str | None = Field(
        default=None, description="Reason for cancellation if train is cancelled"
    )
    is_completed: bool = Field(
        default=False, description="Whether the train has completed its journey"
    )
    # Progress and prediction fields
    progress: JourneyProgress | None = None
    predicted_arrival: datetime | None = None

    @field_serializer("journey_date")
    def serialize_journey_date(self, journey_date: date) -> str:
        """Serialize date as datetime string for iOS compatibility."""
        # Convert date to datetime at midnight in Eastern time
        return f"{journey_date.isoformat()}T00:00:00"


class TrackPrediction(BaseModel):
    """Inline track prediction included in train details when track is unassigned."""

    platform_probabilities: dict[str, float]
    primary_prediction: str
    confidence: float
    top_3: list[str]
    station_code: str


class TrainDetailsResponse(BaseModel):
    """Response for train details endpoint."""

    train: TrainDetails
    track_prediction: TrackPrediction | None = None


# History API Models


class HistoricalJourney(BaseModel):
    """Historical journey summary."""

    journey_date: date
    scheduled_departure: datetime
    actual_departure: datetime | None = None
    scheduled_arrival: datetime | None = None
    actual_arrival: datetime | None = None
    delay_minutes: int = Field(default=0, ge=0)
    was_cancelled: bool = False
    track_assignments: dict[str, str | None] = Field(
        default_factory=dict, examples=[{"NY": "7", "NP": "2", "TR": None}]
    )

    @field_serializer(
        "scheduled_departure", "actual_departure", "scheduled_arrival", "actual_arrival"
    )
    def serialize_dt(self, dt: datetime | None) -> str | None:
        return serialize_eastern_datetime(dt)


class TrainHistoryResponse(BaseModel):
    """Response for train history endpoint."""

    train_id: str
    journeys: list[HistoricalJourney]
    statistics: dict[str, Any] = Field(
        default_factory=dict,
        examples=[
            {
                "total_journeys": 30,
                "on_time_percentage": 85.5,
                "average_delay_minutes": 3.2,
                "cancellation_rate": 2.1,
            }
        ],
    )
    route_statistics: dict[str, Any] | None = Field(
        default=None,
        description="Statistics for all trains on the same route (same service only)",
    )
    data_source: str | None = Field(
        default=None, description="Data source for this train (NJT or AMTRAK)"
    )


class OccupiedTracksResponse(BaseModel):
    """Response for occupied tracks endpoint."""

    station_code: str = Field(..., min_length=1, max_length=4)
    station_name: str
    occupied_tracks: list[str]
    last_updated: datetime
    cache_expires_at: datetime

    @field_serializer("last_updated", "cache_expires_at")
    def serialize_dt(self, dt: datetime) -> str:
        return serialize_eastern_datetime(dt) or ""


# Internal Models (not exposed via API)


class NJTransitStopData(BaseModel):
    """Raw stop data from NJ Transit API."""

    STATION_2CHAR: str | None = None
    STATIONNAME: str | None = None
    TIME: str | None = None
    PICKUP: str | None = None
    DROPOFF: str | None = None
    DEPARTED: str | None = None
    STOP_STATUS: str | None = None

    @field_validator("DEPARTED", mode="before")
    @classmethod
    def normalize_departed(cls, v: str | None) -> str | None:
        return v.upper() if v else v

    @field_validator("STOP_STATUS", mode="before")
    @classmethod
    def normalize_stop_status(cls, v: str | None) -> str | None:
        return v.upper() if v else v

    DEP_TIME: str | None = None
    TIME_UTC_FORMAT: str | None = None
    TRACK: str | None = None
    STOP_LINES: list[dict[str, str]] | None = None
    # Original schedule times (immutable, from NJT schedule data).
    # These are the true scheduled times, unlike TIME/DEP_TIME which have
    # different semantics at origin vs intermediate stops.
    SCHED_ARR_DATE: str | None = None
    SCHED_DEP_DATE: str | None = None


class NJTransitTrainData(BaseModel):
    """Raw train data from NJ Transit getTrainStopList API."""

    TRAIN_ID: str
    LINECODE: str
    BACKCOLOR: str
    FORECOLOR: str
    SHADOWCOLOR: str
    DESTINATION: str
    TRANSFERAT: str = ""
    STOPS: list[NJTransitStopData]


# Amtrak API Models


class AmtrakStationData(BaseModel):
    """Raw station/stop data from Amtrak API."""

    name: str
    code: str
    tz: str | None = None  # Made optional - some Gulf Coast stations don't provide this
    bus: bool
    schArr: str | None = None
    schDep: str | None = None
    arr: str | None = None
    dep: str | None = None
    arrCmnt: str = ""
    depCmnt: str = ""
    status: str
    stopIconColor: str = ""
    platform: str = ""


class AmtrakTrainData(BaseModel):
    """Raw train data from Amtrak API."""

    routeName: str
    trainNum: str
    trainNumRaw: str
    trainID: str
    lat: float
    lon: float
    trainTimely: str = ""
    iconColor: str = ""
    textColor: str = ""
    stations: list[AmtrakStationData]
    heading: str
    eventCode: str
    eventTZ: str = ""
    eventName: str = ""
    origCode: str
    originTZ: str = ""
    origName: str = ""
    destCode: str
    destTZ: str = ""
    destName: str = ""
    trainState: str
    velocity: float
    statusMsg: str = ""
    createdAt: str
    updatedAt: str
    lastValTS: str | None = None
    objectID: int | None = None
    provider: str = "Amtrak"
    providerShort: str = "AMTK"
    onlyOfTrainNum: bool = False
    alerts: list[dict[str, Any]] = Field(default_factory=list)


# Route History API Models


class HistoricalRouteInfo(BaseModel):
    """Route information for route-based historical data."""

    from_station: str = Field(..., min_length=1, max_length=4)
    to_station: str = Field(..., min_length=1, max_length=4)
    total_trains: int = Field(..., ge=0)
    data_source: Literal["NJT", "AMTRAK", "PATH", "PATCO", "LIRR", "MNR", "SUBWAY"]


class DelayBreakdown(BaseModel):
    """Delay breakdown percentages."""

    on_time: int = Field(..., ge=0, le=100)
    slight: int = Field(..., ge=0, le=100)
    significant: int = Field(..., ge=0, le=100)
    major: int = Field(..., ge=0, le=100)


class AggregateStats(BaseModel):
    """Aggregate statistics for all trains on the route."""

    on_time_percentage: float = Field(..., ge=0.0, le=100.0)
    average_delay_minutes: float = Field(..., ge=0.0)
    average_departure_delay_minutes: float = Field(
        0.0, ge=0.0, description="Average departure delay at origin in minutes"
    )
    cancellation_rate: float = Field(..., ge=0.0, le=100.0)
    delay_breakdown: DelayBreakdown
    track_usage_at_origin: dict[str, int] = Field(
        default_factory=dict, description="Track number to usage percentage mapping"
    )


class HighlightedTrain(BaseModel):
    """Statistics for a specific train compared to the route."""

    train_id: str
    on_time_percentage: float = Field(..., ge=0.0, le=100.0)
    average_delay_minutes: float = Field(..., ge=0.0)
    average_departure_delay_minutes: float = Field(
        0.0, ge=0.0, description="Average departure delay at origin in minutes"
    )
    delay_breakdown: DelayBreakdown
    track_usage_at_origin: dict[str, int] = Field(
        default_factory=dict, description="Track number to usage percentage mapping"
    )


class RouteHistoryResponse(BaseModel):
    """Response for route history endpoint."""

    route: HistoricalRouteInfo
    aggregate_stats: AggregateStats
    highlighted_train: HighlightedTrain | None = None


# Congestion API Models


class TrainLocationData(BaseModel):
    """Current train location data for map display."""

    train_id: str
    line: str
    data_source: Literal["NJT", "AMTRAK", "PATH", "PATCO", "LIRR", "MNR", "SUBWAY"]

    # GPS coordinates (Amtrak only)
    lat: float | None = None
    lon: float | None = None

    # Station-based position (NJT and fallback for Amtrak)
    last_departed_station: str | None = None
    at_station: str | None = None
    next_station: str | None = None
    between_stations: bool = False

    # Progress tracking
    journey_percent: float | None = Field(None, ge=0.0, le=100.0)

    # Movement data (Amtrak only)
    velocity: float | None = None
    heading: str | None = None


class IndividualJourneySegment(BaseModel):
    """Individual journey segment data for visualization."""

    journey_id: str
    train_id: str
    from_station: str
    to_station: str
    from_station_name: str
    to_station_name: str
    data_source: str
    scheduled_departure: datetime
    actual_departure: datetime
    scheduled_arrival: datetime
    actual_arrival: datetime
    scheduled_minutes: float = Field(..., ge=0.0)
    actual_minutes: float = Field(..., ge=0.0)

    @field_serializer(
        "scheduled_departure", "actual_departure", "scheduled_arrival", "actual_arrival"
    )
    def serialize_dt(self, dt: datetime) -> str:
        return serialize_eastern_datetime(dt) or ""

    delay_minutes: float
    congestion_factor: float = Field(..., ge=0.0)
    congestion_level: Literal["normal", "moderate", "heavy", "severe"]
    is_cancelled: bool
    journey_date: date


class SegmentCongestion(BaseModel):
    """Aggregated congestion data for a route segment."""

    from_station: str
    to_station: str
    from_station_name: str
    to_station_name: str
    data_source: str
    congestion_level: Literal["normal", "moderate", "heavy", "severe"]
    congestion_factor: float = Field(..., ge=0.0)
    average_delay_minutes: float
    sample_count: int = Field(..., ge=0)
    baseline_minutes: float = Field(..., ge=0.0)
    current_average_minutes: float = Field(..., ge=0.0)
    cancellation_count: int = Field(default=0, ge=0)
    cancellation_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    # Frequency/health metrics (train count vs baseline)
    # None for schedule-only data sources (e.g., PATCO)
    train_count: int | None = Field(default=None, ge=0)
    baseline_train_count: float | None = Field(default=None, ge=0.0)
    frequency_factor: float | None = Field(default=None, ge=0.0)
    frequency_level: Literal["healthy", "moderate", "reduced", "severe"] | None = None


class CongestionMapResponse(BaseModel):
    """Response for congestion map endpoint."""

    individual_segments: list[IndividualJourneySegment]
    aggregated_segments: list[SegmentCongestion]
    train_positions: list[TrainLocationData] = Field(default_factory=list)
    generated_at: datetime
    time_window_hours: int
    max_per_segment: int = Field(default=100, ge=0, le=500)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_serializer("generated_at")
    def serialize_dt(self, dt: datetime) -> str:
        return serialize_eastern_datetime(dt) or ""


# Segment Train Details API Models


class SegmentTrainDetail(BaseModel):
    """Individual train detail for a segment."""

    train_id: str
    line: str
    scheduled_departure: datetime
    actual_departure: datetime
    scheduled_arrival: datetime
    actual_arrival: datetime
    departure_delay_minutes: int
    arrival_delay_minutes: int
    congestion_factor: float = Field(..., ge=0.0)
    delay_category: Literal[
        "on_time", "slight_delay", "delayed", "significantly_delayed"
    ]
    data_source: str

    @field_serializer(
        "scheduled_departure", "actual_departure", "scheduled_arrival", "actual_arrival"
    )
    def serialize_dt(self, dt: datetime) -> str:
        return serialize_eastern_datetime(dt) or ""


class SegmentTrainDetailsResponse(BaseModel):
    """Response for segment train details endpoint."""

    segment: dict[str, str] = Field(
        ...,
        examples=[
            {
                "from_station": "NY",
                "to_station": "NP",
                "from_station_name": "New York Penn Station",
                "to_station_name": "Newark Penn Station",
            }
        ],
    )
    trains: list[SegmentTrainDetail]
    summary: dict[str, Any] = Field(
        ...,
        examples=[
            {
                "total_trains": 127,
                "returned_trains": 50,
                "average_departure_delay": 2.8,
                "average_arrival_delay": 3.2,
                "average_congestion_factor": 1.15,
                "on_time_percentage": 68.5,
            }
        ],
    )


# Operations Summary API Models


class TrainDelaySummaryResponse(BaseModel):
    """Summary of a single train's delay for visualization."""

    train_id: str = Field(..., description="Train identifier")
    delay_minutes: float = Field(..., ge=0.0, description="Delay in minutes")
    category: Literal["on_time", "slight_delay", "delayed", "cancelled"] = Field(
        ..., description="Delay category"
    )
    scheduled_departure: datetime = Field(..., description="Scheduled departure time")

    @field_serializer("scheduled_departure")
    def serialize_dt(self, dt: datetime) -> str:
        return serialize_eastern_datetime(dt) or ""


class SummaryMetricsResponse(BaseModel):
    """Raw metrics included with summary response."""

    on_time_percentage: float | None = Field(
        None, ge=0.0, le=100.0, description="Percentage of trains on time"
    )
    average_delay_minutes: float | None = Field(
        None, ge=0.0, description="Average delay in minutes"
    )
    cancellation_count: int | None = Field(
        None, ge=0, description="Number of cancellations"
    )
    train_count: int | None = Field(None, ge=0, description="Total number of trains")
    trains_by_category: dict[str, list[TrainDelaySummaryResponse]] | None = Field(
        None, description="Trains grouped by delay category for visualization"
    )


class OperationsSummaryResponse(BaseModel):
    """Response for operations summary endpoint."""

    headline: str = Field(
        ...,
        max_length=100,
        description="Headline for collapsed view (max 100 chars)",
    )
    body: str = Field(
        ..., max_length=500, description="Detailed summary (2-4 sentences)"
    )
    scope: Literal["network", "route", "train"] = Field(
        ..., description="Summary scope"
    )
    time_window_minutes: int = Field(
        ...,
        ge=0,
        description="Time window in minutes (90 for recent, 43200 for 30-day)",
    )
    data_freshness_seconds: int = Field(..., ge=0, description="Age of data in seconds")
    generated_at: datetime = Field(..., description="When summary was generated")
    metrics: SummaryMetricsResponse | None = Field(
        None, description="Raw metrics for optional UI display"
    )

    @field_serializer("generated_at")
    def serialize_dt(self, dt: datetime) -> str:
        return serialize_eastern_datetime(dt) or ""


# Delay Forecast API Models


class DelayBreakdownProbabilities(BaseModel):
    """Delay probability breakdown."""

    on_time: float = Field(
        ..., ge=0.0, le=1.0, description="Probability <= 5 min delay"
    )
    slight: float = Field(..., ge=0.0, le=1.0, description="Probability 6-15 min delay")
    significant: float = Field(
        ..., ge=0.0, le=1.0, description="Probability 16-30 min delay"
    )
    major: float = Field(..., ge=0.0, le=1.0, description="Probability > 30 min delay")


class DelayForecastResponse(BaseModel):
    """Response for delay/cancellation forecast endpoint."""

    train_id: str
    station_code: str
    journey_date: date

    # Cancellation probability
    cancellation_probability: float = Field(
        ..., ge=0.0, le=1.0, description="Probability of cancellation"
    )

    # Delay probabilities (sum to 1.0 for non-cancelled scenario)
    delay_probabilities: DelayBreakdownProbabilities

    # Point estimate
    expected_delay_minutes: int = Field(
        ..., ge=0, description="Expected delay in minutes"
    )

    # Metadata
    confidence: Literal["high", "medium", "low"] = Field(
        ..., description="Confidence level based on sample size"
    )
    sample_count: int = Field(..., ge=0, description="Historical samples used")
    factors: list[str] = Field(
        default_factory=list,
        description="Factors used in forecast",
        examples=[["train_history", "line_pattern", "congestion"]],
    )

    @field_serializer("journey_date")
    def serialize_journey_date(self, journey_date: date) -> str:
        return journey_date.isoformat()
