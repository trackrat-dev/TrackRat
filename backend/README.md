# TrackCast: Train Track Prediction System

TrackCast is a real-time track prediction system for trains departing from multiple stations. It collects data from both NJ Transit and Amtrak APIs, processes information into a structured database, and employs station-specific machine learning models to predict which track a train will depart from before the official announcement. The system currently supports NY Penn Station, Trenton Transit Center, Princeton Junction, Metropark, Newark Penn Station, and nationwide Amtrak routes.

## CI/CD Pipeline

The project uses a consolidated CI/CD workflow that ensures all tests pass before deployment:

- **Workflow**: `.github/workflows/ci-cd.yml` - Single pipeline for testing and deployment
- **Testing**: Unit tests, integration tests, code quality checks, and Docker validation
- **Deployment**: Automatic deployment to GCP Cloud Run when tests pass on main branch
- **Safety**: Deployment is physically blocked until all tests succeed

For migration details from the old separate workflows, see `.github/workflows/MIGRATION.md`.

## Type Checking

TrackCast uses mypy for static type checking to improve code reliability and developer experience:

### Running Type Checks Locally

```bash
# Check all modules (shows existing type issues)
mypy trackcast/

# Check enhanced modules with comprehensive type annotations
mypy trackcast/api/routers/trains.py trackcast/cli.py

# With configuration file
mypy trackcast/ --config-file mypy.ini
```

### Type Annotation Status

- ✅ **API Router Functions** (Phase 1): Complete type annotations for all helper functions
- ✅ **CLI Commands** (Phase 2): Complete type annotations for all command parameters  
- ⚠️ **Other Modules**: Gradual type adoption in progress

### Development Guidelines

1. **New Code**: All new functions should include type annotations
2. **Enhanced Modules**: Use strict typing in `trackcast/api/routers/trains.py` and `trackcast/cli.py`
3. **Dependencies**: mypy and type stubs are included in development dependencies
4. **CI Integration**: Type checking runs in GitHub Actions alongside other quality checks

### Configuration

- **Configuration File**: `mypy.ini` with improved third-party library support
- **Type Stubs**: Included for PyYAML, requests, and other dependencies
- **Import Handling**: Missing imports for third-party libraries are properly ignored

## 1. Purpose and Value

Major train stations often announce track assignments only 10-15 minutes before departure, causing passenger congestion and stress. TrackCast aims to predict track assignments with high accuracy up to 30 minutes in advance, allowing passengers to position themselves strategically and reducing platform crowding across multiple stations in the NJ Transit and Amtrak network.

## 2. System Overview

The system consists of three main components:
1. **Data Collection**: Periodically polls the NJ Transit API for train information
2. **Prediction Engine**: Processes historical data to build and apply ML models
3. **Public API**: Exposes predictions to frontend applications or third-party services

## 3. Backend Data Collection Pipeline

### 3.1 Multi-Source API Integration

- We periodically query both NJ Transit and Amtrak APIs:
  - NJ Transit: Station-specific departures from configured stations (NY, TR, PJ, MP, NP)
  - Amtrak: Nationwide train tracking data from the Amtraker API
- Error handling is implemented to retry failed API calls and alert administrators of persistent failures.
- Each API response is timestamped and logged to allow us to re-run all past data through new versions of the pipeline.

Example API data structure from the NJ Transit API:

```json
{
  "STATION_2CHAR": "NY",
  "STATIONNAME": "New York",
  "STATIONMSGS": [
    {
      "MSG_TYPE": "banner",
      "MSG_TEXT": "NEC train #3823, the 9:25 AM arrival into Trenton, is up to 15 minutes late due to congestion from Amtrak train #A141.",
      "MSG_RICHTEXT": "",
      "MSG_PUBDATE": "5/9/2025 9:13:10 AM",
      "MSG_ID": "1913490",
      "MSG_AGENCY": "NJT",
      "MSG_SOURCE": "RSS_NJTRailAlerts",
      "MSG_STATION_SCOPE": " ",
      "MSG_LINE_SCOPE": "*Northeast Corridor Line",
      "MSG_PUBDATE_UTC": "5/9/2025 1:13:10 PM",
      "MSG_URL": "https://www.njtransit.com/node/1913490"
    }
  ],
  "ITEMS": [
    {
      "SCHED_DEP_DATE": "09-May-2025 10:35:00 AM",
      "DESTINATION": "Norfolk",
      "TRACK": "",
      "LINE": "REGIONAL",
      "TRAIN_ID": "A95",
      "CONNECTING_TRAIN_ID": "",
      "STATUS": " ",
      "SEC_LATE": "0",
      "LAST_MODIFIED": "08-May-2025 11:50:22 AM",
      "BACKCOLOR": "#FFFF00",
      "FORECOLOR": "#000000",
      "SHADOWCOLOR": "#FFFF00",
      "GPSLATITUDE": "",
      "GPSLONGITUDE": "",
      "GPSTIME": "",
      "STATION_POSITION": "0",
      "LINECODE": "AM",
      "LINEABBREVIATION": "AMTK",
      "INLINEMSG": "",
      "CAPACITY": [],
      "STOPS": null
    }
  ]
}
```

### 3.2 Data Persistence and Processing

- Log the raw API data to a local JSON file with timestamps for auditing purposes and later replayability.
- Process this data into a record of just the relevant train info and log to a CSV file:

```
Timestamp,Train_ID,Destination,Track,Departure_Time,Status,Line
2025-05-09 09:03:23,A2151,Washington,,09:00 AM,DELAYED,ACELA EXPRESS
2025-05-09 09:03:23,3917,Trenton -SEC &#9992,1,09:04 AM,BOARDING,Northeast Corrdr
2025-05-09 09:03:23,6227,MSU -SEC,2,09:09 AM,BOARDING,Montclair-Boonton
2025-05-09 09:03:23,3829,Trenton -SEC &#9992,,09:19 AM, ,Northeast Corrdr
2025-05-09 09:03:23,6317,Summit -SEC,,09:22 AM, ,Morristown Line
```

*Note: "MSU" refers to Montclair State University, and "SEC" indicates that the train is a NJ Transit Secaucus Junction transfer option. The &#9992 symbol indicates an airport connection is available at this destination.*

### 3.3 Database Schema and Operations

We use PostgreSQL for our primary database due to its robustness with time-series data and ability to handle complex queries efficiently.

For each train in the API response:

1. Check the database for whether a matching train exists by searching for a train with both a matching Train_ID and a matching Departure_Time.
2. If this train does not exist yet, create a DB record with the following schema:

```sql
CREATE TABLE trains (
    id SERIAL PRIMARY KEY,
    train_id VARCHAR(10) NOT NULL,
    line VARCHAR(50) NOT NULL,
    destination VARCHAR(50) NOT NULL,
    departure_time TIMESTAMP NOT NULL,
    track VARCHAR(5),
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    track_assigned_at TIMESTAMP,
    track_released_at TIMESTAMP,
    model_data_id INTEGER REFERENCES model_data(id),
    prediction_data_id INTEGER REFERENCES prediction_data(id)
);
```

3. If the train already exists, check for track assignment or status changes and update the DB record accordingly.
   - Status typically progresses from empty string → "DELAYED"/"BOARDING" → "DEPARTED"
   - Track assignments are recorded with track_assigned_at timestamp
   - When a train is no longer in the API data or has a status of "DEPARTED", mark it as "DEPARTED" and set track_released_at

## 4. Model Data Preparation

### 4.1 Feature Engineering

For each train record, we create a comprehensive set of features to feed into the machine learning model:

#### 4.1.1 Time Features

- **Hour_Sin/Hour_Cos**: Cyclical encoding of the hour of day that preserves the circular nature of time, calculated as:
  - Hour_Sin = sin(2π × hour/24)  (TODO: ensure hour/day is 1 indexed or switch to 23/6)
  - Hour_Cos = cos(2π × hour/24)
- **Day_Of_Week_Sin/Day_Of_Week_Cos**: Cyclical encoding of the day of week:
  - Day_Of_Week_Sin = sin(2π × day/7)
  - Day_Of_Week_Cos = cos(2π × day/7)
- **Is_Weekend**: Binary indicator (1 if Saturday or Sunday, 0 otherwise)
- **Is_Morning_Rush**: Binary indicator (1 if departure time is between 6:00-10:00 AM on weekdays, 0 otherwise)
- **Is_Evening_Rush**: Binary indicator (1 if departure time is between 4:00-8:00 PM on weekdays, 0 otherwise)

#### 4.1.2 Categorical Features (One-Hot Encoded)

- **Line_\***: One-hot encoded train lines (e.g., Line_Northeast_Corridor, Line_Morristown, etc.)
- **Destination_\***: One-hot encoded destinations (e.g., Destination_Trenton, Destination_Dover, etc.)

#### 4.1.3 Time-based Station Track Usage Features

For each of these feature classes, there is one feature for each track:
- **Track_\*_Last_Used**: Minutes since a specific track was last used (maximum: 24 hours ago)
- **Is_Track_\*_Occupied**: Binary indicator showing if a track is currently occupied
- **Track_\*_Utilization_24h**: Percentage of time the track was occupied in the last 24 hours

#### 4.1.4 Historical Track Usage Features

- **Matching_TrainID_Count**: Number of historical records for this specific train ID
- **Matching_Line_Count**: Number of historical records for this line
- **Matching_Dest_Count**: Number of historical records for this destination

For each of these feature classes, there is one feature for each track:
- **Matching_TrainID_Track_\*_Pct**: Percentage of times this specific train ID used a particular track historically
- **Matching_Line_Track_\*_Pct**: Percentage of times trains on this line used a particular track
- **Matching_Dest_Track_\*_Pct**: Percentage of times trains to this destination used a particular track

### 4.2 Data Processing Pipeline

1. Sort train records by departure time and identify the time range to analyze.
2. Collect all train records from 24 hours before the first train to 1 hour after the last train.
3. Process each train record chronologically, creating Model Data records with all features described above.
4. Handle missing values through imputation based on historical averages.
5. Normalize numerical features to prevent scale-related bias in the model.

**CRITICAL:** Ensure that any feature generated for a train at its prediction time `T` (or for a historical training instance) uses *only* information that would have been available *before or at* time `T`, and specifically before its track was assigned.

### 4.3 Model Data Schema

```sql
CREATE TABLE model_data (
    id SERIAL PRIMARY KEY,
    train_id INTEGER REFERENCES trains(id),
    
    -- Time features
    hour_sin FLOAT,
    hour_cos FLOAT,
    day_of_week_sin FLOAT,
    day_of_week_cos FLOAT,
    is_weekend BOOLEAN,
    is_morning_rush BOOLEAN,
    is_evening_rush BOOLEAN,
    
    -- Categorical features (stored as JSON for flexibility)
    line_features JSONB,
    destination_features JSONB,
    
    -- Track usage features
    track_usage_features JSONB,
    
    -- Historical features
    historical_features JSONB,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    feature_version VARCHAR(10)
);
```

## 5. Machine Learning Model

### 5.1 Model Selection and Training

We use a gradient boosting decision tree algorithm (XGBoost) for our predictions because:
- It handles mixed feature types well (numerical, categorical, binary)
- It provides feature importance for explainability
- It performs well with imbalanced class distributions (some tracks are used more frequently)

The training process includes:
1. Splitting data into 80% training and 20% validation sets, stratified by track to ensure representation
2. Hyperparameter tuning via grid search with 5-fold cross-validation
3. Evaluation using accuracy, F1-score, and confusion matrix metrics
4. Feature importance analysis to guide future feature engineering efforts
5. Production of confusion matrix and calibration charts, both on a global as well as per-line and per-destination basis

**CRITICAL:** For time-series data, a random 80/20 split will lead to data leakage and overly optimistic performance. **A temporal split is mandatory.**

Example:
* Train on data from `t_start` to `t_train_end`.
* Validate on data from `t_train_end + 1 day` to `t_validation_end`.
* Test on data from `t_validation_end + 1 day` to `t_test_end`.

### 5.2 Inference Process

When generating predictions for upcoming trains:
1. Load the latest production model from disk
2. Generate MODEL_DATA for the target trains
3. Run inference to produce track probability distributions
4. Calculate prediction factors based on SHAP values from the model
5. Store results in the Prediction Data table

### 5.3 Prediction Data Schema

```sql
CREATE TABLE prediction_data (
    id SERIAL PRIMARY KEY,
    train_id INTEGER REFERENCES trains(id),
    model_data_id INTEGER REFERENCES model_data(id),
    track_probabilities JSONB,
    prediction_factors JSONB,
    model_version VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 6. API Services

### 6.1 API Design

The API follows RESTful principles and provides the following endpoints:

- `GET /api/trains/`: List all trains with optional filtering

### 6.2 Filtering and Pagination

The `/api/trains/` endpoint supports filtering by:
- `train_id`: Filter by train identifier
- `line`: Filter by train line
- `destination`: Filter by destination
- `departure_time_after`: Filter by trains departing after this timestamp
- `departure_time_before`: Filter by trains departing before this timestamp
- `track`: Filter by assigned track number
- `status`: Filter by current status
- `has_prediction`: Boolean filter for trains with predictions

Pagination is implemented with:
- `limit`: Number of results per page (default: 20, max: 100)
- `offset`: Starting point for pagination

### 6.3 Response Format

Example API response:

```json
{
  "metadata": {
    "timestamp": "2025-05-09T09:05:30.123Z",
    "model_version": "1.0.5",
    "train_count": 19,
    "page": 1,
    "total_pages": 1
  },
  "trains": [
    {
      "id": 12345,
      "train_id": "6675",
      "line": "Morristown Line",
      "destination": "Dover",
      "departure_time": "2025-05-07T21:51:00Z",
      "status": "BOARDING",
      "track": "10",
      "model_data": {
        "hour_sin": 0.866,
        "hour_cos": 0.5,
        "is_evening_rush": true,
        /* Additional features omitted for brevity */
      },
      "prediction_data": {
        "track_probabilities": {
          "1": 0.060751706,
          "2": 0.001234567,
          "10": 0.851234567,
          /* Additional tracks omitted for brevity */
        },
        "prediction_factors": [
          {
            "feature": "track_recency",
            "importance": 0.24,
            "direction": "positive",
            "explanation": "Track 10 has not been used recently"
          },
          {
            "feature": "matching_line",
            "importance": 0.18,
            "direction": "positive",
            "explanation": "Morristown Line trains use Track 10 frequently"
          }
        ],
        "model_version": "1.0.5"
      }
    }
    /* Additional trains omitted for brevity */
  ]
}
```

## 7. System Architecture and Operations

### 7.1 Component Architecture

The system is designed with the following components:

1. **Data Collector Service**:
   - Polls the NJ Transit API on a schedule
   - Processes and stores raw data
   - Runs as a microservice with automatic failover

2. **Data Import Service**:
   - Imports historical train data from CSV/JSON files
   - Maintains track assignment state transitions
   - Supports both processed data and raw API responses

3. **Feature Engineering Service**:
   - Processes raw train data into model features
   - Updates the MODEL_DATA table
   - Runs both on a schedule and on-demand

4. **Prediction Service**:
   - Loads model and generates predictions
   - Updates the PREDICTION_DATA table
   - Runs both on a schedule and on-demand

5. **API Service**:
   - Provides RESTful endpoints
   - Handles authentication and rate limiting
   - Serves frontend and third-party applications

### 7.2 Repository Structure

```
trackcast/
├── .github/                    # CI/CD workflows
├── .gitignore
├── LICENSE
├── README.md                   # Project documentation
├── pyproject.toml              # Modern Python project config
├── requirements.txt            # Dependencies
├── config/                     # Configuration files
│   ├── default.yaml            # Default configuration
│   ├── dev.yaml                # Development settings
│   └── prod.yaml               # Production settings
├── docs/                       # TODO: Documentation
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests (uses SQLite in-memory DB)
│   ├── integration/            # Integration tests (requires PostgreSQL)
│   ├── conftest.py             # Test configuration and fixtures
│   └── test_config.yaml        # SQLite test configuration
└── trackcast/                  # Main package
    ├── __init__.py
    ├── cli.py                  # Command-line interface
    ├── config.py               # Configuration management
    ├── constants.py            # System constants
    ├── exceptions.py           # Custom exceptions
    ├── utils.py                # Utility functions
    ├── api/                    # API service
    │   ├── __init__.py
    │   ├── app.py              # FastAPI application
    │   ├── routers/            # API endpoints
    │   └── models.py           # API models (Pydantic)
    ├── data/                   # Data handling
    │   ├── __init__.py
    │   ├── collectors.py       # NJ Transit API integration
    │   ├── processors.py       # Data processing
    │   └── repository.py       # Data access layer
    ├── db/                     # Database handling
    │   ├── __init__.py
    │   ├── connection.py       # Database connection
    │   ├── models.py           # SQLAlchemy models
    │   └── migrations/         # Alembic migrations
    ├── features/               # Feature engineering
    │   ├── __init__.py
    │   ├── extractors.py       # Feature extraction
    │   ├── transformers.py     # Feature transformation
    │   └── pipelines.py        # Feature pipelines
    ├── models/                 # ML models
    │   ├── __init__.py
    │   ├── base.py             # Base model interface
    │   ├── xgboost_model.py    # XGBoost implementation
    │   ├── pytorch_model.py    # PyTorch implementation
    │   ├── inference.py        # Inference logic
    │   └── training.py         # Training logic
    └── services/               # Business logic services
        ├── __init__.py
        ├── data_collector.py   # Data collection service
        ├── data_import.py      # Data import service
        ├── estimated_arrival_service.py  # Arrival time estimation
        ├── feature_engineering.py  # Feature engineering service
        ├── gcp_metrics.py      # Google Cloud metrics integration
        ├── journey_validator.py  # Journey validation service
        ├── prediction.py       # Prediction service
        └── push_notification.py  # Apple Push Notification service
```

## 8. Future Enhancements

1. Additional Data Sources:
   - Weather data integration
   - Special events calendar
   - Historical delay patterns

2. User Experience Improvements:
   - Mobile app with push notifications
   - Personalized recommendations based on user travel patterns

4. Expanded Coverage:
   - Include delays, on-time percentages, etc
   - Additional stations beyond NY Penn
   - Cancelled status?
   - Integration with other transit systems (PATH, PATCO, LIRR, etc)
   - Track/predict final arrival times

5. Monitoring and Alerting
   - Prometheus metrics for system health monitoring
   - Grafana dashboards for visualization
   - Automated alerts for:
     - API outages or errors
     - Data collection failures
     - Model performance degradation
     - Unusual prediction patterns
   
6. Scaling Strategy
   - Horizontal scaling for API services
   - Database sharding by time period for efficient queries
   - Caching layer for frequently accessed predictions
   - Batch processing for historical data analysis
