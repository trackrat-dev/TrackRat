"""
Consolidated API data models using Pydantic v2 with SQLAlchemy integration.

This module contains the new consolidated models that will replace the manual
conversion approach. These models use Pydantic v2's from_attributes=True to
automatically convert from SQLAlchemy models.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class TrainStopResponse(BaseModel):
    """Consolidated train stop response model that matches SQLAlchemy TrainStop exactly."""

    model_config = ConfigDict(from_attributes=True)

    # Core fields (matches SQLAlchemy TrainStop exactly)
    station_code: Optional[str] = Field(None, description="Station code (e.g., 'NY', 'TR')")
    station_name: str = Field(..., description="Station name")

    # Timing information - matches SQLAlchemy field names exactly
    scheduled_arrival: Optional[datetime] = Field(
        None, description="Scheduled arrival time at platform in Eastern timezone"
    )
    scheduled_departure: Optional[datetime] = Field(
        None, description="Scheduled departure time from platform in Eastern timezone"
    )
    actual_arrival: Optional[datetime] = Field(
        None, description="Actual arrival time at platform in Eastern timezone"
    )
    actual_departure: Optional[datetime] = Field(
        None, description="Actual departure time from platform in Eastern timezone"
    )
    estimated_arrival: Optional[datetime] = Field(
        None, description="Estimated arrival time based on current delays in Eastern timezone"
    )

    # Stop characteristics - matches SQLAlchemy field names exactly
    pickup_only: bool = Field(False, description="Pickup only stop")
    dropoff_only: bool = Field(False, description="Dropoff only stop")
    departed: bool = Field(False, description="Train has departed this stop")
    stop_status: Optional[str] = Field(None, description="Stop status")


class PredictionFactorResponse(BaseModel):
    """A factor that contributed to a track prediction."""

    feature: str = Field(..., description="Feature name")
    importance: float = Field(..., description="Feature importance score")
    direction: str = Field(..., description="Direction of influence")
    explanation: str = Field(..., description="Human-readable explanation")


class PredictionDataResponse(BaseModel):
    """Consolidated prediction data response model that matches SQLAlchemy PredictionData."""

    model_config = ConfigDict(from_attributes=True)

    # Core fields (matches SQLAlchemy PredictionData exactly)
    track_probabilities: Dict[str, float] = Field(..., description="Track probability distribution")
    prediction_factors: List[Dict[str, Any]] = Field(
        default_factory=list, description="Factors that influenced the prediction"
    )
    model_version: str = Field(..., description="Model version used for prediction")
    created_at: datetime = Field(..., description="Prediction creation time in Eastern timezone")

    @property
    def top_track(self) -> Optional[str]:
        """Get the track with the highest probability."""
        if not self.track_probabilities:
            return None
        return max(self.track_probabilities.items(), key=lambda x: x[1])[0]

    @property
    def top_probability(self) -> Optional[float]:
        """Get the highest probability value."""
        if not self.track_probabilities:
            return None
        return max(self.track_probabilities.values())


class ModelDataResponse(BaseModel):
    """Consolidated model data response model that matches SQLAlchemy ModelData."""

    model_config = ConfigDict(from_attributes=True)

    # Time-based features (matches SQLAlchemy ModelData exactly)
    hour_sin: Optional[float] = Field(None, description="Hour sine transformation")
    hour_cos: Optional[float] = Field(None, description="Hour cosine transformation")
    day_of_week_sin: Optional[float] = Field(None, description="Day of week sine transformation")
    day_of_week_cos: Optional[float] = Field(None, description="Day of week cosine transformation")
    is_weekend: Optional[bool] = Field(None, description="Weekend indicator")
    is_morning_rush: Optional[bool] = Field(None, description="Morning rush hour indicator")
    is_evening_rush: Optional[bool] = Field(None, description="Evening rush hour indicator")

    # Categorical features encoded as one-hot vectors (matches SQLAlchemy exactly)
    line_features: Optional[Dict[str, Any]] = Field(
        None, description="One-hot encoded features for train line"
    )
    destination_features: Optional[Dict[str, Any]] = Field(
        None, description="One-hot encoded features for train destination"
    )
    track_usage_features: Optional[Dict[str, Any]] = Field(
        None, description="Recent track usage statistics by line and destination"
    )
    historical_features: Optional[Dict[str, Any]] = Field(
        None, description="Historical track assignment patterns for similar trains"
    )

    # Metadata (matches SQLAlchemy exactly)
    feature_version: str = Field(
        ..., description="Version of the feature engineering pipeline used"
    )
    created_at: datetime = Field(..., description="Feature creation time in Eastern timezone")


class TrainResponse(BaseModel):
    """Consolidated train response model that matches current API TrainResponse exactly."""

    model_config = ConfigDict(from_attributes=True)

    # Fields that match the current API TrainResponse exactly
    # Based on trackcast.api.models.TrainResponse (inherits from TrainBase)

    # From TrainBase
    train_id: str = Field(..., description="Train identifier")
    origin_station_code: str = Field(..., description="Origin station code (e.g., 'NY', 'TR')")
    origin_station_name: str = Field(..., description="Origin station name")
    data_source: str = Field(..., description="Data source ('njtransit' or 'amtrak')")
    line: str = Field(..., description="Train line")
    line_code: Optional[str] = Field(None, description="Train line code")
    destination: str = Field(..., description="Train destination")
    departure_time: datetime = Field(..., description="Departure time in Eastern timezone")
    status: Optional[str] = Field(None, description="Train status")
    track: Optional[str] = Field(None, description="Assigned track")

    # From TrainResponse (additional fields)
    id: int = Field(..., description="Database primary key")
    prediction_data: Optional[PredictionDataResponse] = Field(
        None, description="Track prediction data"
    )
    stops: Optional[List[TrainStopResponse]] = Field(
        None, description="Train stops along the route"
    )
    created_at: datetime = Field(..., description="Record creation time in Eastern timezone")
    track_assigned_at: Optional[datetime] = Field(
        None, description="Track assignment time in Eastern timezone"
    )
    track_released_at: Optional[datetime] = Field(
        None, description="Track release time in Eastern timezone"
    )
    delay_minutes: Optional[int] = Field(None, description="Delay in minutes")
    train_split: Optional[str] = Field(None, description="Data split (train, validation, test)")

    # Journey tracking fields (subset that are in current API)
    journey_completion_status: Optional[str] = Field(
        None,
        description="Journey status: 'in_progress', 'completed', 'terminated_early', 'lost_tracking'",
    )
    stops_last_updated: Optional[datetime] = Field(
        None, description="When stop data was last refreshed from NJ Transit getTrainStopList API"
    )
    journey_validated_at: Optional[datetime] = Field(
        None, description="When this train's complete journey was last validated"
    )

    # NOTE: Deliberately excluding fields that are in SQLAlchemy but not in current API:
    # - next_validation_check
    # - updated_at

    # Computed properties (matches SQLAlchemy Train)
    @property
    def has_track(self) -> bool:
        """Check if train has a track assigned."""
        return self.track is not None and self.track.strip() != ""

    @property
    def is_departed(self) -> bool:
        """Check if train has departed."""
        return self.status == "DEPARTED" or self.track_released_at is not None

    @property
    def is_boarding(self) -> bool:
        """Check if train is boarding."""
        return self.status == "BOARDING"

    @property
    def is_delayed(self) -> bool:
        """Check if train is delayed."""
        return self.status == "DELAYED"


class TrainListResponseConsolidated(BaseModel):
    """Consolidated response model for listing trains."""

    metadata: Dict[str, Any] = Field(..., description="Response metadata")
    trains: List[TrainResponse] = Field(..., description="List of trains")


# Enhanced models for consolidated trains (existing structure preserved)


class DataSourceInfo(BaseModel):
    """Information about a data source contributing to a consolidated train."""

    origin: str = Field(..., description="Origin station code")
    data_source: str = Field(..., description="Data source ('njtransit' or 'amtrak')")
    last_update: str = Field(..., description="ISO timestamp of last update")
    status: Optional[str] = None
    track: Optional[str] = None
    delay_minutes: Optional[int] = None
    db_id: int = Field(..., description="Database ID of the original train record")


class OriginStation(BaseModel):
    """Origin station information for consolidated train."""

    code: str = Field(..., description="Station code")
    name: str = Field(..., description="Station name")
    departure_time: str = Field(..., description="ISO timestamp of departure")


class TrackAssignment(BaseModel):
    """Track assignment information with source attribution."""

    track: Optional[str] = None
    assigned_at: Optional[str] = Field(None, description="ISO timestamp of assignment")
    assigned_by: Optional[str] = Field(None, description="Station code that assigned track")
    source: Optional[str] = Field(None, description="Data source that provided track info")


class StatusSummary(BaseModel):
    """Consolidated status information."""

    current_status: str = Field(..., description="Current train status")
    delay_minutes: int = Field(..., description="Delay in minutes")
    on_time_performance: str = Field(..., description="'On Time' or 'Delayed'")


class StatusV2(BaseModel):
    """Enhanced unified status model for clearer train state representation."""

    current: str = Field(
        ..., description="Current status: BOARDING, EN_ROUTE, APPROACHING, ARRIVED, etc."
    )
    location: str = Field(..., description="Human-readable location")
    updated_at: str = Field(..., description="ISO timestamp of status determination")
    confidence: str = Field(..., description="Confidence level: high, medium, low")
    source: str = Field(..., description="Which data source determined this status")


class DepartedStation(BaseModel):
    """Information about the last departed station."""

    station_code: str = Field(..., description="Station code")
    departed_at: str = Field(..., description="ISO timestamp of actual departure")
    delay_minutes: int = Field(..., description="Delay in minutes at departure")


class NextArrival(BaseModel):
    """Information about the next station arrival."""

    station_code: str = Field(..., description="Station code")
    scheduled_arrival: str = Field(..., description="ISO timestamp of scheduled arrival")
    estimated_time: str = Field(..., description="ISO timestamp of estimated arrival")
    minutes_away: int = Field(..., description="Minutes until arrival at next station")


class Progress(BaseModel):
    """Journey progress tracking information."""

    last_departed: Optional[DepartedStation] = None
    next_arrival: Optional[NextArrival] = None
    journey_percent: int = Field(
        ..., ge=0, le=100, description="Overall journey completion percentage"
    )
    stops_completed: int = Field(..., ge=0, description="Number of stops completed")
    total_stops: int = Field(..., ge=1, description="Total number of stops in journey")


class StationPosition(BaseModel):
    """Station position information."""

    code: Optional[str] = None
    name: str = Field(..., description="Station name")
    scheduled_departure: Optional[str] = Field(None, description="ISO timestamp")
    scheduled_arrival: Optional[str] = Field(None, description="ISO timestamp")
    actual_departure: Optional[str] = Field(None, description="ISO timestamp")
    estimated_arrival: Optional[str] = Field(None, description="ISO timestamp")
    distance_miles: Optional[float] = None


class CurrentPosition(BaseModel):
    """Current train position between stations."""

    status: Optional[str] = Field(None, description="Position status description")
    last_departed_station: Optional[StationPosition] = None
    next_station: Optional[StationPosition] = None
    segment_progress: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Progress between stations (0.0 to 1.0)"
    )
    estimated_speed_mph: Optional[float] = None


class ConsolidatedStop(BaseModel):
    """Stop information with merged departure status."""

    station_code: Optional[str] = None
    station_name: str = Field(..., description="Station name")
    scheduled_arrival: Optional[str] = Field(None, description="ISO timestamp of scheduled arrival")
    scheduled_departure: Optional[str] = Field(
        None, description="ISO timestamp of scheduled departure"
    )
    actual_arrival: Optional[str] = Field(None, description="ISO timestamp of actual arrival")
    actual_departure: Optional[str] = Field(None, description="ISO timestamp of actual departure")
    pickup_only: bool = False
    dropoff_only: bool = False
    departed: bool = False
    departed_confirmed_by: List[str] = Field(
        [], description="List of origin stations confirming departure"
    )
    stop_status: Optional[str] = None
    platform: Optional[str] = Field(None, description="Platform/track at this stop")


class ConsolidationMetadata(BaseModel):
    """Metadata about the consolidation process."""

    source_count: int = Field(..., description="Number of source records consolidated")
    last_update: str = Field(..., description="ISO timestamp of most recent update")
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in consolidation accuracy"
    )


class ConsolidatedTrainResponseConsolidated(BaseModel):
    """Consolidated response model for a consolidated train - matches existing exactly."""

    train_id: str = Field(..., description="Train identifier")
    consolidated_id: str = Field(..., description="Unique ID for this consolidated journey")
    origin_station: OriginStation = Field(..., description="Origin station information")
    destination: str = Field(..., description="Train destination")
    line: str = Field(..., description="Train line")
    line_code: Optional[str] = Field(None, description="Train line code")

    # Source tracking
    data_sources: List[DataSourceInfo] = Field(..., description="Contributing data sources")

    # Merged data
    track_assignment: TrackAssignment = Field(..., description="Track assignment information")
    status_summary: StatusSummary = Field(..., description="Consolidated status")
    current_position: Optional[CurrentPosition] = Field(None, description="Current position")

    # Stops with merged departure information
    stops: List[ConsolidatedStop] = Field(..., description="Train stops")

    # Prediction if available
    prediction_data: Optional[PredictionDataResponse] = Field(
        None, description="Track prediction data"
    )

    # Consolidation metadata
    consolidation_metadata: ConsolidationMetadata = Field(..., description="Consolidation metadata")

    # New enhanced fields (optional for backward compatibility)
    status_v2: Optional[StatusV2] = Field(None, description="Enhanced status information")
    progress: Optional[Progress] = Field(None, description="Journey progress information")


class ConsolidatedTrainListResponseConsolidated(BaseModel):
    """Consolidated response model for listing consolidated trains."""

    metadata: Dict[str, Any] = Field(..., description="Response metadata")
    trains: List[ConsolidatedTrainResponseConsolidated] = Field(
        ..., description="List of consolidated trains"
    )


# Type aliases for backward compatibility during transition
TrainResponseConsolidated = TrainResponse
TrainStopResponseConsolidated = TrainStopResponse
PredictionDataResponseConsolidated = PredictionDataResponse
