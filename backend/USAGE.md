# TrackCast Project Usage Guide

This guide explains how to set up, configure, and use the TrackCast system.

## Installation

1. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install the package in development mode:

```bash
pip install -e .
```

3. Install required dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

TrackCast uses YAML configuration files in the `config/` directory. There are three default configuration files:

- `default.yaml`: Base configuration with default values
- `dev.yaml`: Development environment configuration
- `prod.yaml`: Production environment configuration

You can specify which configuration file to use by setting the environment variable `TRACKCAST_ENV`:

```bash
export TRACKCAST_ENV=dev  # Use dev.yaml
```

Or by using the `--env` option with the CLI:

```bash
trackcast --env dev init-db
```

### Multi-Station Configuration

TrackCast now supports tracking trains from multiple origin stations. Configure stations in your YAML file:

```yaml
njtransit_api:
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
```

## Database Setup

Before starting TrackCast, initialize the database:

```bash
trackcast init-db
```

This will create all necessary tables in the PostgreSQL database specified in your configuration.

If you're upgrading from a single-station setup, run the database migration:

```bash
trackcast update-schema
```

This will add the necessary fields for multi-station support.

### Recreating Database from Scratch

If you need to completely recreate the database and import historical data:

1. Drop all existing tables (using PostgreSQL client or admin tool)
2. Initialize the database:
   ```bash
   trackcast init-db
   ```
3. Import historical data from JSON files:
   ```bash
   trackcast import-data --source data/import/ --format json
   ```
4. Process features for all imported data:
   ```bash
   trackcast process-features
   ```
5. Train models:
   ```bash
   trackcast train-model --all-stations
   ```
6. Generate predictions:
   ```bash
   trackcast generate-predictions
   ```

Note: When importing NJ Transit API debug archives, remember to remove authentication token files (e.g., `getToken_*.json`) from the import directory.

## Quick Start

After database setup, here's the typical sequence to get TrackCast running:

```bash
# 1. Import or collect data
trackcast collect-data  # OR: trackcast import-data --source data/import/ --format json

# 2. Process features
trackcast process-features

# 3. Train models
trackcast train-model --all-stations

# 4. Generate predictions
trackcast generate-predictions

# 5. Start the API
trackcast start-api --host 127.0.0.1 --port 8000

# 6. (Optional) Start the scheduler for automatic updates
trackcast start-scheduler
```

## Running the System

TrackCast has several components that can be run independently or together:

### 1. Data Collection

Run a one-time data collection from the NJ Transit API:

```bash
trackcast collect-data
```

This will collect data from all enabled stations configured in your YAML file.

### 2. Feature Engineering

Process collected train data to generate features for the prediction model:

```bash
trackcast process-features
```

### 3. Prediction Generation

Generate track predictions for upcoming trains:

```bash
trackcast generate-predictions
```

### 4. API Service

Start the API service to expose predictions:

```bash
trackcast start-api --host 0.0.0.0 --port 8000
```

### 5. Scheduled Service

Start the scheduler to automatically run all components periodically:

```bash
trackcast start-scheduler
```

### 6. Training a New Model

Train prediction models using historical data:

```bash
# Train models for all configured stations
trackcast train-model --all-stations

# Train model for a specific station
trackcast train-model --station NY
trackcast train-model --station TR
trackcast train-model --station PJ
trackcast train-model --station MP
trackcast train-model --station NP

# Train a combined model (legacy behavior)
trackcast train-model
```

TrackCast uses station-specific models for better prediction accuracy. Each station's model learns the unique track assignment patterns for that location.

### 7. Importing Historical Data

Import train data from CSV/JSON files into the database:

```bash
trackcast import-data --source data/processed/ --format csv --overwrite
```

Options:
- `--source`: Directory containing data files (required)
- `--format`: Data format type ('csv' or 'json')
- `--pattern`: File pattern to match (e.g., "trains_*.csv")
- `--overwrite`: Whether to replace existing records with same IDs

## API Usage

Once the API service is running, you can access track predictions:

### Get All Upcoming Trains

```
GET /api/trains/
```

Example response:

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
      "origin_station_code": "NY",
      "origin_station_name": "New York Penn Station",
      "line": "Morristown Line",
      "destination": "Dover",
      "departure_time": "2025-05-07T21:51:00Z",
      "status": "BOARDING",
      "track": "10",
      "prediction_data": {
        "track_probabilities": {
          "1": 0.060751706,
          "2": 0.001234567,
          "10": 0.851234567
        },
        "prediction_factors": [
          {
            "feature": "track_recency",
            "importance": 0.24,
            "direction": "positive",
            "explanation": "Track 10 has not been used recently"
          }
        ],
        "model_version": "1.0.5_NY"
      }
    }
  ]
}
```

### Filter Trains

The API supports various filtering options:

```
GET /api/trains/?line=Northeast%20Corridor&departure_time_after=2025-05-09T09:00:00Z
```

Available filters:
- `train_id` - Filter by train identifier
- `line` - Filter by train line
- `destination` - Filter by destination
- `departure_time_after` - Filter by trains departing after this timestamp
- `departure_time_before` - Filter by trains departing before this timestamp
- `track` - Filter by assigned track number
- `status` - Filter by current status
- `has_prediction` - Boolean filter for trains with predictions
- `origin_station_code` - Filter by origin station code (e.g., 'NY', 'TR', 'PJ', 'MP', 'NP')
- `origin_station_name` - Filter by origin station name (partial match)

Example filtering by station:

```
GET /api/trains/?origin_station_code=TR
GET /api/trains/?origin_station_code=PJ
GET /api/trains/?origin_station_code=MP
GET /api/trains/?origin_station_code=NP
GET /api/trains/?origin_station_name=Penn
GET /api/trains/?origin_station_name=Princeton
```

## Monitoring

TrackCast logs are stored in `trackcast.log`. For proper production monitoring, configure additional logging handlers and metrics collection.

## Development

### Running Tests

Run the test suite:

```bash
pytest
```

Or with coverage:

```bash
pytest --cov=trackcast
```

### Code Style

Format your code using Black:

```bash
black trackcast/
```

Check code quality with flake8:

```bash
flake8 trackcast/
```

## Deployment

For production deployment, configure a proper WSGI server such as Gunicorn:

```bash
gunicorn trackcast.api.app:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

Consider using Docker for containerized deployment:

```bash
docker build -t trackcast .
docker run -p 8000:8000 trackcast
```