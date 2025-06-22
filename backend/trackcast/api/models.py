"""API data models using Pydantic."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TrainStop(BaseModel):
    """A stop along a train's route."""

    station_code: Optional[str] = None
    station_name: str
    scheduled_time: Optional[datetime] = Field(
        None, description="Scheduled time in Eastern timezone"
    )
    departure_time: Optional[datetime] = Field(
        None, description="Actual departure time in Eastern timezone"
    )
    actual_arrival_time: Optional[datetime] = Field(
        None, description="Actual arrival time at platform in Eastern timezone"
    )
    pickup_only: bool = False
    dropoff_only: bool = False
    departed: bool = False
    stop_status: Optional[str] = None


class PredictionFactor(BaseModel):
    """A factor that contributed to a track prediction."""

    feature: str
    importance: float
    direction: str
    explanation: str


class PredictionData(BaseModel):
    """Prediction data for a train."""

    track_probabilities: Dict[str, float]
    prediction_factors: List[PredictionFactor]
    model_version: str
    created_at: datetime

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


class PredictionResponse(PredictionData):
    """API response model for prediction data."""

    pass


class ModelData(BaseModel):
    """Feature data used for prediction."""

    # Time-based features
    hour_sin: float
    hour_cos: float
    day_of_week_sin: float
    day_of_week_cos: float
    is_weekend: bool
    is_morning_rush: bool
    is_evening_rush: bool

    # Categorical features encoded as one-hot vectors
    line_features: Dict[str, Any] = Field(
        ...,
        description="One-hot encoded features for train line (e.g., {'line_NEC': 1.0, 'line_NJCL': 0.0})",
    )
    destination_features: Dict[str, Any] = Field(
        ...,
        description="One-hot encoded features for train destination (e.g., {'dest_Trenton': 1.0, 'dest_LongBranch': 0.0})",
    )

    # Historical track usage patterns
    track_usage_features: Dict[str, Any] = Field(
        ...,
        description="Recent track usage statistics by line and destination (e.g., {'track_1_usage_rate': 0.25})",
    )

    # Historical patterns for similar trains
    historical_features: Dict[str, Any] = Field(
        ...,
        description="Historical track assignment patterns for similar trains (e.g., {'historical_track_1_rate': 0.8})",
    )

    # Metadata
    feature_version: str = Field(
        ..., description="Version of the feature engineering pipeline used"
    )
    created_at: datetime


class TrainBase(BaseModel):
    """Base train model with common fields."""

    train_id: str
    origin_station_code: str = Field(
        ..., description="Origin station code (e.g., 'NY' for Penn Station)"
    )
    origin_station_name: str = Field(
        ..., description="Origin station name (e.g., 'New York Penn Station')"
    )
    data_source: str = Field(..., description="Data source ('njtransit' or 'amtrak')")
    line: str
    line_code: Optional[str] = None
    destination: str
    departure_time: datetime = Field(..., description="Departure time in Eastern timezone")
    status: Optional[str] = None
    track: Optional[str] = None


class TrainResponse(TrainBase):
    """Complete train data with predictions and features."""

    id: int
    prediction_data: Optional[PredictionData] = None
    stops: Optional[List[TrainStop]] = None
    created_at: datetime = Field(..., description="Record creation time in Eastern timezone")
    track_assigned_at: Optional[datetime] = Field(
        None, description="Track assignment time in Eastern timezone"
    )
    track_released_at: Optional[datetime] = Field(
        None, description="Track release time in Eastern timezone"
    )
    delay_minutes: Optional[int] = None
    train_split: Optional[str] = None

    # Journey tracking fields
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


class Metadata(BaseModel):
    """Metadata for API responses."""

    timestamp: str
    model_version: Optional[str] = None
    train_count: int
    page: Optional[int] = None
    total_pages: Optional[int] = None


class TrainListResponse(BaseModel):
    """Response model for listing trains."""

    metadata: Metadata
    trains: List[TrainResponse]


# Consolidated train models for the new consolidation feature


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

    code: str
    name: str
    departure_time: str = Field(..., description="ISO timestamp of departure")


class TrackAssignment(BaseModel):
    """Track assignment information with source attribution."""

    track: Optional[str] = None
    assigned_at: Optional[str] = Field(None, description="ISO timestamp of assignment")
    assigned_by: Optional[str] = Field(None, description="Station code that assigned track")
    source: Optional[str] = Field(None, description="Data source that provided track info")


class StatusSummary(BaseModel):
    """Consolidated status information."""

    current_status: str
    delay_minutes: int
    on_time_performance: str = Field(..., description="'On Time' or 'Delayed'")


class StationPosition(BaseModel):
    """Station position information."""

    code: Optional[str] = None
    name: str
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
    station_name: str
    scheduled_time: Optional[str] = Field(None, description="ISO timestamp")
    departure_time: Optional[str] = Field(None, description="ISO timestamp")
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


class ConsolidatedTrainResponse(BaseModel):
    """Response model for a consolidated train."""

    train_id: str
    consolidated_id: str = Field(..., description="Unique ID for this consolidated journey")
    origin_station: OriginStation
    destination: str
    line: str
    line_code: Optional[str] = None

    # Source tracking
    data_sources: List[DataSourceInfo]

    # Merged data
    track_assignment: TrackAssignment
    status_summary: StatusSummary
    current_position: Optional[CurrentPosition] = None

    # Stops with merged departure information
    stops: List[ConsolidatedStop]

    # Prediction if available
    prediction_data: Optional[PredictionData] = None

    # Consolidation metadata
    consolidation_metadata: ConsolidationMetadata

    # New enhanced fields (optional for backward compatibility)
    status_v2: Optional["StatusV2"] = None
    progress: Optional["Progress"] = None


class ConsolidatedTrainListResponse(BaseModel):
    """Response model for listing consolidated trains."""

    metadata: Metadata
    trains: List[ConsolidatedTrainResponse]


# New enhanced status and progress models


class StatusV2(BaseModel):
    """Enhanced unified status model for clearer train state representation."""

    current: str = Field(
        ..., description="Current status: BOARDING, EN_ROUTE, APPROACHING, ARRIVED, etc."
    )
    location: str = Field(
        ..., description="Human-readable location (e.g., 'at NY Penn Station', 'between NY and NP')"
    )
    updated_at: str = Field(..., description="ISO timestamp of status determination")
    confidence: str = Field(..., description="Confidence level: high, medium, low")
    source: str = Field(..., description="Which data source determined this status")


class DepartedStation(BaseModel):
    """Information about the last departed station."""

    station_code: str
    departed_at: str = Field(..., description="ISO timestamp of actual departure")
    delay_minutes: int = Field(..., description="Delay in minutes at departure")


class NextArrival(BaseModel):
    """Information about the next station arrival."""

    station_code: str
    scheduled_time: str = Field(..., description="ISO timestamp of scheduled arrival")
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
