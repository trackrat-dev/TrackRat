# Database Indices for TrackCast

This document outlines recommended database indices to optimize the performance of the TrackCast application. These recommendations are based on the most common query patterns across the application's main workflows.

## Overview

TrackCast uses a PostgreSQL database with three main tables:
- `trains`: Core table storing train information
- `model_data`: Features for machine learning prediction
- `prediction_data`: Track predictions and explanation factors

## Current Indices

The database schema already includes the following indices:

- `trains` table:
  - `train_id`: Index on the train identifier
  - `line`: Index on the train line
  - `destination`: Index on the destination
  - `departure_time`: Index on departure time
  - `track`: Index on the assigned track
  - `status`: Index on the train status
  - Unique constraint on `(train_id, departure_time)`

- `model_data` table:
  - `feature_version`: Index on feature version

- `prediction_data` table:
  - `model_version`: Index on model version

## Recommended Additional Indices

Based on analysis of query patterns in the application's code, the following additional indices are recommended:

### 1. Trains Table

```sql
-- Index for frequent queries by train ID and departure time range
CREATE INDEX idx_trains_id_departure_time ON trains(train_id, departure_time);

-- Index for filtering trains by departure time and track assignment status
CREATE INDEX idx_trains_departure_track ON trains(departure_time, track NULLS FIRST);

-- Index for data collection workflow (trains in a specific time window with certain status)
CREATE INDEX idx_trains_departure_status ON trains(departure_time, status);

-- Track assignment tracking
CREATE INDEX idx_trains_track_assigned_at ON trains(track_assigned_at);
CREATE INDEX idx_trains_track_released_at ON trains(track_released_at);

-- Index for finding trains needing feature engineering
CREATE INDEX idx_trains_model_data_id ON trains(model_data_id NULLS FIRST);

-- Index for finding trains needing predictions
CREATE INDEX idx_trains_needs_prediction ON trains(model_data_id, prediction_data_id NULLS FIRST, track NULLS FIRST, departure_time);
```

### 2. Model Data Table

```sql
-- When looking up model data for a specific train
CREATE INDEX idx_model_data_join ON model_data(id) INCLUDE (feature_version);

-- For historical feature queries and model training
CREATE INDEX idx_model_data_version_created ON model_data(feature_version, created_at);
```

### 3. Prediction Data Table

```sql
-- When looking up prediction data for a specific train or model
CREATE INDEX idx_prediction_data_model_data ON prediction_data(model_data_id);

-- For performance evaluation
CREATE INDEX idx_prediction_data_version_created ON prediction_data(model_version, created_at);
```

## Optimization for Key Workflows

### Train Data Collection Workflow

This workflow frequently queries for trains departing in the next few hours with no track assignment or that recently departed:

```sql
-- This covers the common time range + status filter pattern
SELECT * FROM trains
WHERE (departure_time >= now() AND departure_time <= now() + interval '4 hours')
   OR (departure_time >= now() - interval '30 minutes' 
       AND departure_time <= now()
       AND (track IS NULL OR track = '' OR status != 'DEPARTED'));
```

The `idx_trains_departure_track` and `idx_trains_departure_status` indices will optimize this query.

### Feature Engineering Workflow

This workflow finds trains that need feature extraction:

```sql
-- Find trains without features
SELECT * FROM trains
WHERE model_data_id IS NULL
ORDER BY departure_time ASC;
```

The `idx_trains_model_data_id` index will optimize this query.

### Prediction Workflow

This workflow finds trains that need predictions:

```sql
-- Find trains needing predictions (with features but no predictions yet)
SELECT * FROM trains
WHERE model_data_id IS NOT NULL
  AND prediction_data_id IS NULL
  AND track IS NULL
  AND departure_time >= now()
ORDER BY departure_time ASC;
```

The `idx_trains_needs_prediction` composite index will optimize this query.

### API Queries

The API makes heavy use of filtered queries, especially with time ranges:

```sql
-- Common API query pattern
SELECT * FROM trains
WHERE departure_time >= ? AND departure_time <= ?
  AND [other optional filters]
ORDER BY departure_time ASC
LIMIT ? OFFSET ?;
```

The existing `departure_time` index, along with the additional specific indices for common filter combinations, will optimize these queries.

## Track Usage Analysis

For calculating track utilization and last usage:

```sql
-- Track usage history
SELECT * FROM trains
WHERE track_assigned_at >= now() - interval '24 hours'
ORDER BY track_assigned_at ASC;
```

The `idx_trains_track_assigned_at` index will optimize this query.

## Prediction Accuracy Evaluation

For evaluating model performance:

```sql
-- Prediction accuracy
SELECT * FROM trains
WHERE prediction_data_id IS NOT NULL AND track IS NOT NULL;
```

The indices for `prediction_data_id` and `track` will optimize this query.

## Implementation Notes

1. Implement these indices incrementally, prioritizing those that support the most frequent or performance-critical operations.

2. Monitor query performance before and after adding indices to measure their impact.

3. For larger tables (as the system accumulates data), consider partitioning the `trains` table by date range to improve query performance on recent data.

4. Re-evaluate indexing needs as the application evolves and usage patterns change.

5. Consider adding a database maintenance schedule to rebuild indices periodically.