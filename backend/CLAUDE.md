# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TrackCast is a real-time track prediction system for trains departing from multiple stations. It collects data from both NJ Transit and Amtrak APIs, processes information into a structured database, and employs station-specific machine learning models to predict which track a train will depart from before the official announcement. The system currently supports NY Penn Station, Trenton Transit Center, Princeton Junction, Metropark, Newark Penn Station, and nationwide Amtrak routes.

### Key Features
- **Multi-Source Data Collection**: Integrates NJ Transit station-specific APIs and Amtrak's nationwide tracking API
- **Train Consolidation**: Intelligently merges duplicate train records from multiple sources into unified journey representations
- **Station-Specific Models**: Uses PyTorch neural networks trained on individual station data for accurate predictions
- **Journey Planning**: Context-aware API filtering for seamless trip planning between any two stations
- **Real-Time Updates**: Continuous polling and prediction generation for up-to-date track assignments

### Recent Updates
- **Train Consolidation Service**: Automatically consolidates duplicate train records from multiple data sources
- **Stops API**: New endpoints for querying station information and station-specific train data
- **Enhanced CLI**: Added station code backfilling and advanced data clearing options
- **Model Training Improvements**: Comprehensive visualization outputs including calibration curves and confusion matrices
- **Model Accuracy Tracking**: Real-time monitoring of prediction accuracy with automatic metric updates
- **Health & Metrics Endpoints**: Comprehensive system health monitoring and Prometheus metrics
- **Executive Dashboard**: Google Cloud Monitoring dashboards for system-wide visibility (infrastructure-level)

## Development Commands

### Setup and Installation

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package in development mode
pip install -e .

# Install required dependencies
pip install -r requirements.txt
```

### Database Operations

```bash
# Initialize the database schema
trackcast init-db

# Update schema for multi-station support (if upgrading)
trackcast update-schema
```

### Running Components

```bash
# Run a one-time data collection from both NJ Transit and Amtrak APIs (all configured sources)
trackcast collect-data

# Process collected train data to generate features
trackcast process-features
trackcast process-features --clear  # Clear existing features before processing
trackcast process-features --clear --train-id 1234  # Clear features for specific train
trackcast process-features --clear --time-range "2025-05-01T00:00:00" "2025-05-31T23:59:59"  # Clear features in time range

# Generate track predictions for upcoming trains (uses station-specific models)
trackcast generate-predictions
trackcast generate-predictions --clear  # Clear existing predictions before generating

# Start the API service (default: http://127.0.0.1:8000)
trackcast start-api --host 0.0.0.0 --port 8000

# Start the scheduler for automatic periodic execution of all components
trackcast start-scheduler

# Train prediction models using historical data
trackcast train-model --all-stations  # Train for all configured stations
trackcast train-model --station NY    # Train for specific station
trackcast train-model                 # Train combined model (legacy)

# Import train data from CSV/JSON files into the database
trackcast import-data --source data/processed/ --format csv --overwrite

# Backfill missing station codes in the database
trackcast backfill-station-codes

# Check APNS (Apple Push Notification Service) configuration status
trackcast check-apns-config
```

### Development and Testing

```bash
# Run test suite
pytest

# Run tests with coverage
pytest --cov=trackcast

# Run unit tests only (faster, uses SQLite)
pytest tests/unit/

# Run integration tests (requires PostgreSQL)
pytest tests/integration/

# Run specific test files
pytest test_consolidation.py
pytest test_track_assignment.py

# Format code
black trackcast/

# Check code quality
flake8 trackcast/

# Type checking
mypy trackcast/
```

### Deployment

```bash
# Production deployment with Gunicorn
gunicorn trackcast.api.app:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Project Architecture

### Core Components

1. **Data Collection Service**: Polls both NJ Transit and Amtrak APIs for multiple stations and stores raw train data with origin information and data source
2. **Train Consolidation Service**: Intelligently merges duplicate train records from multiple sources into unified journey representations
3. **Feature Engineering Service**: Processes raw train data into model features
4. **Prediction Service**: Loads station-specific machine learning models and generates track predictions
5. **API Service**: Provides RESTful endpoints for accessing predictions with station filtering, journey planning, and train consolidation
6. **Scheduler Service**: Coordinates periodic execution of the other services
7. **Data Import Service**: Imports historical train data from CSV/JSON files and maintains track assignment state

### Data Flow

1. The Data Collector fetches train data from both NJ Transit and Amtrak APIs:
   - NJ Transit: Station-specific departures from configured stations (NY, TR, PJ, MP, NP)
   - Amtrak: Nationwide train tracking data from the Amtraker API
2. Raw data is processed and stored in the database (Train table) with origin station information and data source identifier
3. The Train Consolidation service identifies and merges duplicate train records:
   - Matches trains by ID and stop schedules
   - Merges track assignments with confidence scoring
   - Creates unified journey representations
4. The Feature Engineering service extracts features from train data
5. Features are stored in the ModelData table
6. The Prediction service applies station-specific models to generate track predictions
7. Predictions are stored in the PredictionData table
8. The API exposes train records with their predictions, filterable by station, data source, and journey segments, with optional consolidation

### Machine Learning Pipeline

1. **Feature Engineering**: Time-based, categorical, and historical track usage features
2. **Training**: Station-specific PyTorch neural network models with safeguards to prevent data leakage
   - Supports both PyTorch and XGBoost models (configurable)
   - Generates comprehensive visualization outputs (calibration curves, confusion matrices, learning curves)
   - Implements proper temporal splitting to avoid data leakage
3. **Prediction**: Generates probability distributions across possible tracks using the appropriate station model
4. **Explanation**: Uses perturbation-based feature importance to explain prediction factors
5. **Accuracy Tracking**: Automatic model performance monitoring
   - When a train's actual track is assigned, the system compares it with the predicted track
   - Updates the `model_prediction_accuracy` metric by station
   - Enables real-time monitoring of model performance degradation
   - Supports alerting when accuracy drops below thresholds

### Push Notification System

TrackCast includes an integrated Apple Push Notification Service (APNS) system for iOS Live Activities and push notifications:

1. **Device Token Management**: Stores iOS device tokens for push notification delivery
2. **Live Activity Integration**: Supports Live Activity push tokens for Dynamic Island updates
3. **Smart Notification Detection**: Automatically detects significant train changes (track assignments, boarding, departures)
4. **Dual Notification System**: Sends both Live Activity updates and regular push notifications
5. **Rate Limiting & Error Handling**: Production-ready APNS client with proper retry logic

Key features:
- **JWT Authentication**: Preferred APNS auth key method with automatic token refresh
- **Certificate Support**: Alternative certificate-based authentication
- **Environment Detection**: Automatic sandbox/production endpoint selection
- **Mock Mode**: Graceful fallback when APNS is not configured
- **Change Detection**: Only sends notifications for meaningful train updates

#### APNS Setup

**Important**: iOS Live Activities use a separate extension bundle ID. The backend now supports different bundle IDs for regular push notifications vs Live Activities. Live Activities use the extension bundle ID (e.g., `net.trackrat.TrackRat.TrainLiveActivityExtension`) while regular notifications use the main app bundle ID.

See `APNS_SETUP.md` for complete configuration instructions. Quick setup:

```bash
# Required environment variables (Auth Key method - recommended)
export APNS_TEAM_ID="YOUR_TEAM_ID"
export APNS_KEY_ID="ABC123DEF4"
export APNS_AUTH_KEY_PATH="/path/to/AuthKey_ABC123DEF4.p8"
export APNS_BUNDLE_ID="net.trackrat.TrackRat"
export APNS_LIVE_ACTIVITY_BUNDLE_ID="net.trackrat.TrackRat.TrainLiveActivityExtension"  # Optional, defaults to main bundle + .TrainLiveActivityExtension
export TRACKCAST_ENV="prod"  # or "dev" for sandbox

# Check configuration
trackcast check-apns-config
```

The system automatically integrates with data collection - when trains are updated, the notification service processes changes and sends appropriate alerts to users tracking those trains.

## Configuration

TrackCast uses YAML configuration files in the `config/` directory:
- `default.yaml`: Base configuration
- `dev.yaml`: Development environment configuration
- `prod.yaml`: Production environment configuration

### Multi-Station Configuration

Configure multiple stations in your YAML file:

```yaml
njtransit_api:
  base_url: "https://raildata.njtransit.com/api/TrainData"
  stations:
    - code: "NY"
      name: "New York Penn Station"
      enabled: true
    - code: "TR"
      name: "Trenton Transit Center"
      enabled: true
    - code: "PJ"
      name: "Princeton Junction"
      enabled: true
    - code: "MP"
      name: "Metropark"
      enabled: true
    - code: "NP"
      name: "Newark Penn Station"
      enabled: true
  polling_interval_seconds: 60
  retry_attempts: 3
  timeout_seconds: 10
  username: ""  # Set via NJT_USERNAME env var
  password: ""  # Set via NJT_PASSWORD env var

amtrak_api:
  base_url: "https://api-v3.amtraker.com/v3/trains"
  enabled: true
  polling_interval_seconds: 120
  retry_attempts: 3
  timeout_seconds: 15
  debug_mode: false

# Model Configuration
model:
  version: "1.0.0"
  save_path: "models/"
  type: "pytorch"  # or "xgboost"
  hyperparameters:
    learning_rate: 0.001
    hidden_layers: [128, 64, 32]
    dropout_rate: 0.3
    batch_size: 64
    num_epochs: 50

# Timezone Configuration
timezone:
  display_timezone: "US/Eastern"
  storage_timezone: "US/Eastern"
  api_response_timezone: "US/Eastern"

# Database Configuration
database:
  url: "postgresql://user@localhost:5432/trackcast"
  pool_size: 10
  max_overflow: 25

# Scheduler Configuration
scheduler:
  collection_interval_minutes: 1
  feature_engineering_interval_minutes: 1
  prediction_interval_minutes: 2
```

Set configuration with environment variable:
```bash
export TRACKCAST_ENV=dev  # Use dev.yaml
```

Or with CLI:
```bash
trackcast --env dev init-db
```

## API Endpoints

### Train Endpoints

- `GET /api/trains/` - List all trains with filtering options
  - `origin_station_code` - Filter by station code (e.g., 'NY', 'TR', 'PJ', 'MP', 'NP')
  - `origin_station_name` - Filter by station name (partial match)
  - `from_station_code` - Filter trains that stop at this station (boarding station)
  - `to_station_code` - Filter trains that stop at this station after from_station_code (alighting station)
  - `stops_at_station_code` - Filter trains that stop at this exact station code (only shows future stops)
  - `stops_at_station_name` - Filter trains that stop at this station name (partial match, only future stops)
  - `data_source` - Filter by data source ('njtransit' or 'amtrak')
  - `departure_time_after` / `departure_time_before` - Context-aware time filtering (see Smart Time Filtering below)
  - `consolidate` - Boolean flag to enable train consolidation (merges duplicates from multiple sources)
  - `train_split` - Filter by data split (train, validation, test) for ML training
  - `exclude_train_split` - Exclude trains with this data split
  - `has_track` - Filter to only include trains with assigned tracks
  - `sort_by` - Field to sort by (e.g., 'departure_time', 'train_id')
  - `sort_order` - Sort order: 'asc' or 'desc'
  - `no_pagination` - Set to true to disable pagination and get all results
  - Other filters: `train_id`, `line`, `destination`, `track`, `status`, `has_prediction`
  - Pagination: `limit` (default: 20, max: 100), `offset`

- `GET /api/trains/{train_id}` - Get a specific train by ID
  - Returns detailed train information including predictions

- `GET /api/trains/{train_id}/prediction` - Get prediction data for a specific train
  - Returns track probabilities and prediction factors

#### Smart Time Filtering

The `departure_time_after` and `departure_time_before` parameters intelligently adapt based on query context:

- **When using `from_station_code`**: Filters based on departure time from the boarding station
- **When using `origin_station_code` only**: Filters based on train's original departure time  
- **When using neither**: Filters based on train's original departure time

This makes journey planning intuitive - searching for trains "from Washington after 3pm" finds trains that actually depart Washington after 3pm, regardless of where they originally started.

**Important Notes:**
- The `stops_at_station` filters only return trains with future stops at the specified station (stops that haven't occurred yet)
- When using `from_station_code` with `to_station_code`, the API ensures proper stop ordering (the train stops at 'from' before 'to')

Examples:
```bash
# Get trains from specific stations (originating)
curl "http://localhost:8000/api/trains/?origin_station_code=TR"  # Trenton
curl "http://localhost:8000/api/trains/?origin_station_code=PJ"  # Princeton Junction
curl "http://localhost:8000/api/trains/?origin_station_code=MP"  # Metropark

# Get trains from stations with "Penn" in the name (NY and NP)
curl "http://localhost:8000/api/trains/?origin_station_name=Penn"

# Get trains from Newark Penn Station specifically
curl "http://localhost:8000/api/trains/?origin_station_code=NP"

# Get trains traveling from Washington Union to New York Penn (through trains)
curl "http://localhost:8000/api/trains/?from_station_code=WAS&to_station_code=NY"

# Get trains traveling from New York Penn to Trenton
curl "http://localhost:8000/api/trains/?from_station_code=NY&to_station_code=TR"

# Get trains departing Washington after 3pm going to NY (uses Washington departure time)
curl "http://localhost:8000/api/trains/?from_station_code=WAS&to_station_code=NY&departure_time_after=2025-05-26T15:00:00"

# Get trains originating from NY after 3pm (uses origin departure time)
curl "http://localhost:8000/api/trains/?origin_station_code=NY&departure_time_after=2025-05-26T15:00:00"

# Get all Amtrak trains
curl "http://localhost:8000/api/trains/?data_source=amtrak"

# Get NJ Transit trains only
curl "http://localhost:8000/api/trains/?data_source=njtransit"

# Get trains that stop at Washington Union
curl "http://localhost:8000/api/trains/?stops_at_station_code=WAS"

# Get consolidated trains (merges duplicates from multiple sources)
curl "http://localhost:8000/api/trains/?consolidate=true"
```

### Stops Endpoints

- `GET /api/stops/` - List all stations in the system
  - Returns station codes, names, and metadata

- `GET /api/stops/{station_identifier}/trains` - Get trains for a specific station
  - `station_identifier` can be either a station code (e.g., 'NY') or station name
  - Supports all the same filtering parameters as `/api/trains/`

Examples:
```bash
# Get all stations
curl "http://localhost:8000/api/stops/"

# Get trains at New York Penn Station
curl "http://localhost:8000/api/stops/NY/trains"

# Get trains at a station by name
curl "http://localhost:8000/api/stops/Newark%20Penn%20Station/trains"
```

## Train Consolidation

TrackCast automatically consolidates duplicate train records that arise when the same physical train is tracked from multiple sources (different NJ Transit station APIs and/or Amtrak API). This feature provides a unified view of each train's journey.

### How It Works

1. **Matching Algorithm**: The system identifies duplicate trains by:
   - Matching train IDs
   - Comparing stop schedules to verify it's the same journey
   - Validating route patterns

2. **Data Merging**: When duplicates are found, the system:
   - Combines all stop information from all sources
   - Merges track assignments with confidence scoring
   - Preserves the most complete status information
   - Maintains data source attribution

3. **Track Assignment Confidence**: For consolidated trains with different track assignments:
   - Calculates confidence scores based on data recency and source reliability
   - Presents both the primary track assignment and alternatives with their confidence levels

### API Usage

Enable consolidation by adding `consolidate=true` to any trains endpoint:

```bash
# Get consolidated trains from all sources
curl "http://localhost:8000/api/trains/?consolidate=true"

# Combine with other filters
curl "http://localhost:8000/api/trains/?consolidate=true&from_station_code=NY&to_station_code=TR"

# Note: When consolidate=true is used, the response format changes from TrainListResponse
# to ConsolidatedTrainListResponse with additional fields like data_sources, 
# consolidation_metadata, status_v2, and progress
```

### Example: Consolidated Train Response

```json
{
  "train_id": "7871",
  "consolidated_id": "7871_2025-06-01",
  "line": "Northeast Corridor",
  "destination": "Trenton",
  "origin_station": {
    "code": "NY",
    "name": "New York Penn Station",
    "departure_time": "2025-06-01T20:03:00"
  },
  "data_sources": [
    {
      "origin": "NY",
      "data_source": "njtransit", 
      "last_update": "2025-06-01T20:05:00",
      "status": "DEPARTED",
      "track": "13",
      "delay_minutes": 0,
      "db_id": 1234
    },
    {
      "origin": "NP",
      "data_source": "njtransit",
      "last_update": "2025-06-01T20:25:00", 
      "status": "",
      "track": "4",
      "delay_minutes": null,
      "db_id": 1235
    }
  ],
  "track_assignment": {
    "track": "13",
    "assigned_at": "2025-06-01T19:55:00",
    "assigned_by": "NY",
    "source": "njtransit"
  },
  "status_summary": {
    "current_status": "In Transit",
    "delay_minutes": 0,
    "on_time_performance": "On Time"
  },
  "status_v2": {
    "current": "EN_ROUTE",
    "location": "between New York Penn Station and Newark Penn Station",
    "updated_at": "2025-06-01T20:25:00",
    "confidence": "high",
    "source": "NY_njtransit"
  },
  "progress": {
    "last_departed": {
      "station_code": "NY",
      "departed_at": "2025-06-01T20:03:00",
      "delay_minutes": 0
    },
    "next_arrival": {
      "station_code": "NP", 
      "scheduled_time": "2025-06-01T20:21:00",
      "estimated_time": "2025-06-01T20:21:00",
      "minutes_away": 16
    },
    "journey_percent": 20,
    "stops_completed": 1,
    "total_stops": 5
  },
  "stops": [
    {
      "station_code": "NY",
      "station_name": "New York Penn Station",
      "scheduled_time": "2025-06-01T20:03:00",
      "departure_time": "2025-06-01T20:03:00",
      "departed": true,
      "departed_confirmed_by": ["NY"],
      "stop_status": "DEPARTED",
      "platform": "13"
    },
    {
      "station_code": "NP",
      "station_name": "Newark Penn Station", 
      "scheduled_time": "2025-06-01T20:21:00",
      "departure_time": "2025-06-01T20:21:15",
      "departed": false,
      "departed_confirmed_by": [],
      "stop_status": "",
      "platform": "4"
    }
  ],
  "prediction_data": {
    "track_probabilities": {"13": 0.95, "4": 0.05},
    "prediction_factors": [],
    "model_version": "1.0.0_NY",
    "created_at": "2025-06-01T19:50:00"
  },
  "consolidation_metadata": {
    "source_count": 2,
    "last_update": "2025-06-01T20:25:00",
    "confidence_score": 0.90
  }
}
```

### New API Fields

#### StatusV2 - Enhanced Status with Conflict Resolution
The `status_v2` field provides an intelligent unified status that resolves conflicts between data sources:

- **`current`**: The resolved status (BOARDING, EN_ROUTE, APPROACHING, ARRIVED, etc.)
- **`location`**: Human-readable location description
- **`updated_at`**: When this status was determined
- **`confidence`**: high/medium/low based on data consistency
- **`source`**: Which data source determined this status

Key logic:
- DEPARTED status always overrides BOARDING
- Uses most recent update for current position
- Handles the NJ Transit "stuck BOARDING" issue

#### Progress - Real-time Journey Tracking
The `progress` field provides detailed journey progress information:

- **`last_departed`**: Station code, departure time, and delay of last departed stop
- **`next_arrival`**: Next station with scheduled/estimated times and minutes away
- **`journey_percent`**: Overall completion percentage (0-100)
- **`stops_completed`**: Number of stops the train has departed
- **`total_stops`**: Total stops in the journey

This enables:
- Accurate progress bars in UIs
- Time-to-arrival calculations
- Better user journey tracking

### Health & Monitoring Endpoints

- `GET /health` - Comprehensive health check endpoint
  - Returns database connection status
  - Train processing metrics (last hour/24h)
  - Data freshness indicators
  - Source breakdown by station
  - Quality metrics (track assignment rate, prediction rate)
  
- `GET /metrics` - Prometheus metrics endpoint
  - `model_prediction_accuracy` - Accuracy by station (compares predicted vs actual tracks)
  - `trains_processed_total` - Total trains processed
  - `track_prediction_confidence_ratio` - Distribution of prediction confidence scores
  - `nj_transit_fetch_success_total` / `nj_transit_fetch_failures_total` - API fetch metrics
  - `amtrak_fetch_success_total` / `amtrak_fetch_failures_total` - API fetch metrics
  - `model_inference_time_seconds` - Model performance metrics
  - `db_query_duration_seconds` - Database performance metrics

Example health check response:
```json
{
  "status": "healthy",
  "database": {
    "connected": true,
    "latency_ms": 2.5
  },
  "data_freshness": {
    "latest_train": "2025-06-01T20:30:00",
    "minutes_ago": 2
  },
  "processing_metrics": {
    "trains_last_hour": 156,
    "trains_last_24h": 3421,
    "by_source": {
      "njtransit": 2845,
      "amtrak": 576
    }
  },
  "quality_metrics": {
    "track_assignment_rate": 0.78,
    "prediction_rate": 0.92,
    "accuracy_last_24h": 0.85
  }
}
```