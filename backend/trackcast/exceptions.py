"""TrackCast custom exceptions."""


class TrackCastError(Exception):
    """Base exception for all TrackCast errors."""

    pass


class ConfigError(TrackCastError):
    """Error related to configuration loading or validation."""

    pass


class APIError(TrackCastError):
    """Error related to external API interactions."""

    pass


class DataCollectionError(TrackCastError):
    """Error during data collection process."""

    pass


class DataProcessingError(TrackCastError):
    """Error during data processing."""

    pass


class DatabaseError(TrackCastError):
    """Error related to database operations."""

    pass


class ModelError(TrackCastError):
    """Error related to machine learning models."""

    pass


class ModelTrainingError(ModelError):
    """Error during model training."""

    pass


class ModelInferenceError(ModelError):
    """Error during model inference."""

    pass


class FeatureEngineeringError(TrackCastError):
    """Error during feature engineering."""

    pass


class ValidationError(TrackCastError):
    """Error during data validation."""

    pass
