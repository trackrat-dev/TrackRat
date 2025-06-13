"""
Feature engineering pipelines for TrackCast.

This module combines feature extractors into pipelines for generating
feature sets used in machine learning models.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from trackcast.db.models import ModelData, Train
from trackcast.db.repository import ModelDataRepository, TrainRepository
from trackcast.features.extractors import (
    CategoricalFeatureExtractor,
    FeatureExtractor,
    HistoricalTrackFeatureExtractor,
    TimeFeatureExtractor,
    TrackUsageFeatureExtractor,
)

logger = logging.getLogger(__name__)


class FeaturePipeline:
    """
    Pipeline for extracting, transforming, and combining features for model training
    and prediction.
    """

    def __init__(
        self,
        session: Session,
        feature_version: str = "1.0.0",
        include_extractors: Optional[List[str]] = None,
    ):
        """
        Initialize the feature pipeline.

        Args:
            session: SQLAlchemy database session
            feature_version: Version identifier for feature set
            include_extractors: List of extractor types to include (defaults to all)
        """
        self.session = session
        self.feature_version = feature_version
        self.train_repo = TrainRepository(session)
        self.model_data_repo = ModelDataRepository(session)

        # Initialize feature extractors
        self.extractors: List[FeatureExtractor] = []

        # Decide which extractors to include
        include_all = include_extractors is None

        if include_all or "time" in include_extractors:
            self.extractors.append(TimeFeatureExtractor())

        if include_all or "categorical" in include_extractors:
            # Get all lines and destinations from the repository
            try:
                lines_and_destinations = self.train_repo.get_all_lines_and_destinations()
                all_lines = lines_and_destinations.get("lines", [])
                all_destinations = lines_and_destinations.get("destinations", [])
                logger.info(
                    f"Retrieved {len(all_lines)} lines and {len(all_destinations)} destinations for categorical features"
                )
                self.extractors.append(
                    CategoricalFeatureExtractor(
                        all_lines=all_lines, all_destinations=all_destinations
                    )
                )
            except Exception as e:
                logger.error(f"Error retrieving lines and destinations: {str(e)}")
                # Fall back to empty lists if there's an error
                self.extractors.append(
                    CategoricalFeatureExtractor(all_lines=[], all_destinations=[])
                )

        if include_all or "track_usage" in include_extractors:
            self.extractors.append(TrackUsageFeatureExtractor(session))

        if include_all or "historical" in include_extractors:
            self.extractors.append(HistoricalTrackFeatureExtractor(session))

        logger.info(f"Feature pipeline initialized with {len(self.extractors)} extractors")

    def extract_features(
        self, train: Train, reference_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Extract all features for a train.

        Args:
            train: Train object to extract features for
            reference_time: Time to use as reference (defaults to now)

        Returns:
            Dictionary with all extracted features
        """
        # Set reference time if not provided
        # Use train's departure time to prevent self-conflicts in track occupancy
        if reference_time is None:
            reference_time = train.departure_time

        # Initialize feature dictionary
        all_features = {}

        # Extract features from each extractor
        for extractor in self.extractors:
            try:
                # Only use reference_time for specialized time-dependent feature extractors
                # For track usage features, we want to use each train's specific departure time
                if isinstance(extractor, TrackUsageFeatureExtractor):
                    features = extractor.extract(train)
                else:
                    # For other extractors, we can use the reference time
                    features = extractor.extract(train, reference_time=reference_time)

                # Update feature dictionary
                all_features.update(features)

            except Exception as e:
                logger.error(
                    f"Error extracting features with {extractor.__class__.__name__}: {str(e)}"
                )

        return all_features

    def process_train(
        self, train: Train, reference_time: Optional[datetime] = None, save: bool = True
    ) -> Optional[ModelData]:
        """
        Process a train to extract features and optionally save to database.

        Args:
            train: Train object to process
            reference_time: Time to use as reference
            save: Whether to save the model data to the database

        Returns:
            ModelData object with extracted features
        """
        try:
            # Skip if train already has model data
            if train.model_data_id:
                logger.debug(f"Train {train.id} already has model data")
                return None

            # Extract features
            features = self.extract_features(train, reference_time)

            # Create ModelData object
            model_data_dict = {
                # Basic features
                "hour_sin": features.get("hour_sin"),
                "hour_cos": features.get("hour_cos"),
                "day_of_week_sin": features.get("day_of_week_sin"),
                "day_of_week_cos": features.get("day_of_week_cos"),
                "is_weekend": features.get("is_weekend"),
                "is_morning_rush": features.get("is_morning_rush"),
                "is_evening_rush": features.get("is_evening_rush"),
                # Complex feature sets
                "line_features": features.get("line_features"),
                "destination_features": features.get("destination_features"),
                "track_usage_features": features.get("track_usage_features"),
                "historical_features": features.get("historical_features"),
                # Metadata
                "feature_version": self.feature_version,
            }

            # Create ModelData object
            model_data = ModelData(**model_data_dict)

            # Save to database if requested
            if save:
                # Add to session
                self.session.add(model_data)
                self.session.flush()  # Generate ID without committing

                # Associate with train
                train.model_data_id = model_data.id

                # Commit changes
                self.session.commit()

                logger.info(f"Created model data (id={model_data.id}) for train {train.train_id}")

            return model_data

        except Exception as e:
            if save:
                self.session.rollback()
            logger.error(f"Error creating model data for train {train.train_id}: {str(e)}")
            return None

    def precompute_historical_data(self, reference_time: Optional[datetime] = None):
        """
        Precompute historical data for all extractors in a single operation.
        This significantly reduces database queries when processing multiple trains.

        Args:
            reference_time: Time to use as reference for feature extraction
        """
        logger.info("Precomputing historical data for all feature extractors")

        # Precompute data for each extractor that supports it
        for extractor in self.extractors:
            if hasattr(extractor, "precompute_historical_data"):
                try:
                    extractor.precompute_historical_data(reference_time)
                except Exception as e:
                    logger.error(
                        f"Error precomputing data for {extractor.__class__.__name__}: {str(e)}"
                    )

        logger.info("Completed precomputation of historical data")

    def process_trains(
        self, trains: List[Train], reference_time: Optional[datetime] = None
    ) -> Tuple[int, int, List[str]]:
        """
        Process multiple trains in batch.

        Args:
            trains: List of Train objects to process
            reference_time: Time to use as reference for precomputation only.
                           Each train's features will be based on its own departure time.

        Returns:
            Tuple containing:
            - Number of successfully processed trains
            - Number of failures
            - List of error messages
        """
        success_count = 0
        failure_count = 0
        errors = []

        # Don't precompute with a global reference time to avoid self-conflicts
        # Each train will precompute its own timeline based on its departure time
        # Note: We skip global precomputation to ensure each train sees only trains that departed before it

        # Set default reference time if not provided (only used for logging/metadata)
        if reference_time is None:
            reference_time = datetime.utcnow()

        logger.info(f"Processing features for {len(trains)} trains")

        for train in trains:
            try:
                # Don't pass reference_time to use train's own departure time for TrackUsageFeatureExtractor
                result = self.process_train(train)
                if result:
                    success_count += 1
                else:
                    # Skip trains that already have features
                    if train.model_data_id:
                        logger.debug(f"Skipped train {train.train_id}: already has features")
                    else:
                        failure_count += 1
                        error_msg = f"Failed to process train {train.train_id}: unknown error"
                        errors.append(error_msg)
            except Exception as e:
                failure_count += 1
                error_msg = f"Failed to process train {train.train_id}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        return success_count, failure_count, errors

    def process_trains_in_range(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        reference_time: Optional[datetime] = None,
    ) -> Tuple[int, int, List[str]]:
        """
        Process all trains in a given time range.

        Args:
            start_time: Start of time range (defaults to now)
            end_time: End of time range (defaults to 2 hours from now)
            reference_time: Time to use as reference for feature extraction

        Returns:
            Tuple containing:
            - Number of successfully processed trains
            - Number of failures
            - List of error messages
        """
        try:
            # Default to processing trains departing in the next 2 hours
            if start_time is None:
                start_time = datetime.utcnow()
            if end_time is None:
                end_time = start_time + timedelta(hours=2)

            # Set reference time if not provided
            if reference_time is None:
                reference_time = datetime.utcnow()

            # Get trains that need feature engineering
            trains = self.train_repo.get_trains_needing_features()

            # Filter by time range
            trains = [t for t in trains if start_time <= t.departure_time <= end_time]

            if not trains:
                logger.info(
                    "No trains found needing feature engineering in the specified time range"
                )
                return 0, 0, []

            logger.info(f"Processing {len(trains)} trains for feature engineering in time range")

            # Process trains - the precompute_historical_data is called inside process_trains
            return self.process_trains(trains, reference_time)

        except Exception as e:
            error_msg = f"Error in process_trains_in_range: {str(e)}"
            logger.error(error_msg)
            return 0, 1, [error_msg]

    def get_feature_names(self) -> List[str]:
        """
        Get all feature names produced by this pipeline.

        Returns:
            List of feature names
        """
        feature_names = []
        for extractor in self.extractors:
            feature_names.extend(extractor.feature_names)
        return feature_names
