"""TrackCast constant values."""

# Version
VERSION = "0.1.0"

# Configuration
DEFAULT_CONFIG_PATH = "config/default.yaml"
DEV_CONFIG_PATH = "config/dev.yaml"
PROD_CONFIG_PATH = "config/prod.yaml"
ENV_VAR_NAME = "TRACKCAST_ENV"

# Data collection
POLL_INTERVAL_SECONDS = 60
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 10
API_TIMEOUT_SECONDS = 30

# Database
DEFAULT_DB_URL = "postgresql://postgres:postgres@localhost:5432/trackcast"
DEFAULT_POOL_SIZE = 5
DEFAULT_MAX_OVERFLOW = 10
DEFAULT_POOL_TIMEOUT = 30

# Model
MODEL_SAVE_PATH = "models/saved"
DEFAULT_MODEL_VERSION = "1.0.0"
MAX_TRAIN_EPOCHS = 100
EARLY_STOPPING_PATIENCE = 10
TRAIN_BATCH_SIZE = 64
VALIDATION_SPLIT = 0.2
TEST_SPLIT = 0.1

# API
DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8000
DEFAULT_API_WORKERS = 4

# Tracks
TRACK_NUMBERS = [
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
]

# Time features
MORNING_RUSH_START_HOUR = 6
MORNING_RUSH_END_HOUR = 10
EVENING_RUSH_START_HOUR = 16
EVENING_RUSH_END_HOUR = 20

# Logging
DEFAULT_LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
