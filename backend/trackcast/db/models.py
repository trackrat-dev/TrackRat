"""
Database models for TrackCast.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from trackcast.db.connection import Base
from trackcast.utils import get_eastern_now

logger = logging.getLogger(__name__)


class TimestampMixin:
    """Mixin to add creation and update timestamps to models."""

    created_at = Column(DateTime, default=get_eastern_now, nullable=False)
    updated_at = Column(DateTime, default=get_eastern_now, onupdate=get_eastern_now, nullable=False)


class Train(Base, TimestampMixin):
    """
    Train information model representing a train scheduled to depart from a station.
    """

    __tablename__ = "trains"

    # Primary key and identification
    id = Column(Integer, primary_key=True)
    train_id = Column(String(20), nullable=False, index=True)

    # Station information
    origin_station_code = Column(String(10), nullable=False, index=True, default="NY")
    origin_station_name = Column(String(100), nullable=False, default="New York Penn Station")

    # Data source
    data_source = Column(String(20), nullable=False, index=True, default="njtransit")

    # Train details
    line = Column(String(50), nullable=False, index=True)
    line_code = Column(String(10), nullable=True)
    destination = Column(String(50), nullable=False, index=True)
    departure_time = Column(DateTime, nullable=False, index=True)

    # Track and status
    track = Column(String(5), nullable=True, index=True)
    status = Column(String(20), nullable=True, index=True)
    track_assigned_at = Column(DateTime, nullable=True)
    track_released_at = Column(DateTime, nullable=True)
    delay_minutes = Column(Integer, nullable=True, index=True)

    # Data split for model training (train, validation, test)
    train_split = Column(String(10), nullable=True, index=True)

    # Journey tracking fields
    journey_completion_status = Column(String(20), nullable=True, index=True)
    # Values: 'in_progress', 'completed', 'terminated_early', 'lost_tracking'

    journey_validated_at = Column(DateTime, nullable=True)
    # When we last checked this train's full journey via getTrainStopList

    next_validation_check = Column(DateTime, nullable=True, index=True)
    # When to check again if journey not complete

    stops_last_updated = Column(DateTime, nullable=True, index=True)
    # When we last fetched stop data from getTrainStopList API

    # Relationships (one-to-one with the feature and prediction data)
    model_data_id = Column(Integer, ForeignKey("model_data.id", ondelete="SET NULL"), nullable=True)
    prediction_data_id = Column(
        Integer, ForeignKey("prediction_data.id", ondelete="SET NULL"), nullable=True
    )

    # Define relationships
    model_data = relationship("ModelData", foreign_keys=[model_data_id], back_populates="train")
    prediction_data = relationship(
        "PredictionData", foreign_keys=[prediction_data_id], back_populates="train"
    )
    # Note: stops relationship defined in TrainStop model due to composite key complexity

    # Unique constraint to prevent duplicate train records
    __table_args__ = (
        UniqueConstraint(
            "train_id",
            "departure_time",
            "origin_station_code",
            "data_source",
            name="uix_train_origin_departure_source",
        ),
    )

    def __repr__(self) -> str:
        """String representation of the train."""
        return (
            f"<Train(id={self.id}, train_id='{self.train_id}', "
            f"origin='{self.origin_station_code}', line='{self.line}', "
            f"destination='{self.destination}', departure='{self.departure_time}', "
            f"track='{self.track}', source='{self.data_source}')>"
        )

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


class TrainStop(Base, TimestampMixin):
    """
    Train stop information representing individual stops along a train's route.
    """

    __tablename__ = "train_stops"

    # Primary key
    id = Column(Integer, primary_key=True)

    # Foreign key to train (composite foreign key)
    train_id = Column(String(20), nullable=False, index=True)
    train_departure_time = Column(DateTime, nullable=False, index=True)

    # Data source
    data_source = Column(String(20), nullable=False, index=True, default="njtransit")

    # Station information
    station_code = Column(String(10), nullable=True, index=True)
    station_name = Column(String(100), nullable=False)

    # Timing information
    scheduled_time = Column(DateTime, nullable=True)
    departure_time = Column(DateTime, nullable=True)
    actual_arrival_time = Column(DateTime, nullable=True)  # When train actually arrived at platform

    # Stop characteristics
    pickup_only = Column(Boolean, default=False, nullable=False)
    dropoff_only = Column(Boolean, default=False, nullable=False)
    departed = Column(Boolean, default=False, nullable=False)
    stop_status = Column(String(20), nullable=True)

    # Lifecycle tracking
    last_seen_at = Column(DateTime, nullable=False, default=get_eastern_now, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Note: Relationship to train handled via queries due to composite key complexity

    # Unique constraint to prevent duplicate stop records including data source and scheduled time
    # This allows multiple stops at the same station if they occur at different times
    __table_args__ = (
        UniqueConstraint(
            "train_id",
            "train_departure_time",
            "station_name",
            "data_source",
            name="uix_train_stop_unique_without_time",  # Renamed for clarity
        ),
    )

    def __repr__(self) -> str:
        """String representation of the train stop."""
        return (
            f"<TrainStop(id={self.id}, train_id='{self.train_id}', "
            f"station='{self.station_name}', scheduled='{self.scheduled_time}')>"
        )

    @property
    def is_pickup_stop(self) -> bool:
        """Check if this is a pickup-only stop."""
        return self.pickup_only and not self.dropoff_only

    @property
    def is_dropoff_stop(self) -> bool:
        """Check if this is a dropoff-only stop."""
        return self.dropoff_only and not self.pickup_only

    @property
    def is_regular_stop(self) -> bool:
        """Check if this is a regular stop (both pickup and dropoff)."""
        return not self.pickup_only and not self.dropoff_only


class ModelData(Base, TimestampMixin):
    """
    Model feature data for machine learning predictions.
    """

    __tablename__ = "model_data"

    # Primary key and relationship
    id = Column(Integer, primary_key=True)

    # Time features
    hour_sin = Column(Float, nullable=True)
    hour_cos = Column(Float, nullable=True)
    day_of_week_sin = Column(Float, nullable=True)
    day_of_week_cos = Column(Float, nullable=True)
    is_weekend = Column(Boolean, nullable=True)
    is_morning_rush = Column(Boolean, nullable=True)
    is_evening_rush = Column(Boolean, nullable=True)

    # Categorical features
    line_features = Column(JSON, nullable=True)
    destination_features = Column(JSON, nullable=True)

    # Track usage features
    track_usage_features = Column(JSON, nullable=True)

    # Historical features
    historical_features = Column(JSON, nullable=True)

    # Metadata
    feature_version = Column(String(10), nullable=False, index=True)

    # Relationship
    train = relationship(
        "Train", foreign_keys=[Train.model_data_id], back_populates="model_data", uselist=False
    )

    def __repr__(self) -> str:
        """String representation of the model data."""
        train_id = self.train.train_id if self.train else "None"
        return f"<ModelData(id={self.id}, train_id={train_id}, feature_version='{self.feature_version}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert model data to a dictionary for use in ML predictions."""
        # Basic features
        features = {
            "hour_sin": self.hour_sin,
            "hour_cos": self.hour_cos,
            "day_of_week_sin": self.day_of_week_sin,
            "day_of_week_cos": self.day_of_week_cos,
            "is_weekend": self.is_weekend,
            "is_morning_rush": self.is_morning_rush,
            "is_evening_rush": self.is_evening_rush,
        }

        # Add JSON features
        if self.line_features:
            features.update(self.line_features)

        if self.destination_features:
            features.update(self.destination_features)

        if self.track_usage_features:
            features.update(self.track_usage_features)

        if self.historical_features:
            features.update(self.historical_features)

        return features


class PredictionData(Base, TimestampMixin):
    """
    Model prediction output containing track probabilities and explanations.
    """

    __tablename__ = "prediction_data"

    # Primary key and relationships
    id = Column(Integer, primary_key=True)
    model_data_id = Column(Integer, ForeignKey("model_data.id", ondelete="SET NULL"), nullable=True)

    # Prediction data
    track_probabilities = Column(JSON, nullable=False)
    prediction_factors = Column(JSON, nullable=True)

    # Metadata
    model_version = Column(String(10), nullable=False, index=True)

    # Relationships
    model_data = relationship("ModelData", foreign_keys=[model_data_id])
    train = relationship(
        "Train",
        foreign_keys=[Train.prediction_data_id],
        back_populates="prediction_data",
        uselist=False,
    )

    def __repr__(self) -> str:
        """String representation of the prediction data."""
        train_id = self.train.train_id if self.train else "None"
        return f"<PredictionData(id={self.id}, train_id={train_id}, model_version='{self.model_version}')>"

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

    def get_top_factors(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Get the top N prediction factors by importance."""
        if not self.prediction_factors:
            return []

        sorted_factors = sorted(
            self.prediction_factors, key=lambda x: x.get("importance", 0), reverse=True
        )

        return sorted_factors[:limit]
