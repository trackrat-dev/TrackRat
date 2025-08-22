#!/usr/bin/env python3
"""
Export training data for NY Penn Station track predictions.

This script extracts historical track assignments and features from the database
to create a CSV file for training a machine learning model.

Output: data/ny_penn_track_training_data.csv
"""

import asyncio
import csv
import os
from datetime import datetime, timedelta
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def get_database_connection():
    """Create a connection to the PostgreSQL database."""
    database_url = os.getenv("TRACKRAT_DATABASE_URL", "")
    
    # Convert from SQLAlchemy format to asyncpg format
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    
    print(f"Connecting to: {database_url}")
    
    try:
        return await asyncpg.connect(database_url)
    except Exception as e:
        print(f"Connection failed: {e}")
        # Try direct connection parameters as fallback
        return await asyncpg.connect(
            host="localhost",
            port=5433,
            user="postgres", 
            password="password",
            database="trackratdb"
        )


async def export_training_data():
    """Export track prediction training data for NY Penn Station."""
    
    conn = await get_database_connection()
    print("Connected to database")
    
    # Query to extract training data for track-level prediction
    # Each row is a historical track assignment with features (target: track)
    query = """
    WITH track_usage AS (
        -- Calculate time since each track was last used
        SELECT 
            js.station_code,
            js.track,
            js.scheduled_departure,
            LAG(js.scheduled_departure) OVER (
                PARTITION BY js.station_code, js.track 
                ORDER BY js.scheduled_departure
            ) as prev_track_use_time
        FROM journey_stops js
        WHERE js.station_code = 'NY'
          AND js.track IS NOT NULL
          AND js.track != ''
          AND js.scheduled_departure >= NOW() - INTERVAL '90 days'
    )
    SELECT 
        js.station_code,
        js.track,
        EXTRACT(HOUR FROM js.scheduled_departure) as hour_of_day,
        EXTRACT(DOW FROM js.scheduled_departure) as day_of_week,
        CASE 
            WHEN tj.train_id LIKE 'A%' THEN 1 
            ELSE 0 
        END as is_amtrak,
        tj.line_code,
        tj.destination,
        -- Time since track was last used (in minutes)
        COALESCE(
            EXTRACT(EPOCH FROM (js.scheduled_departure - tu.prev_track_use_time)) / 60,
            -1  -- Use -1 for unknown/first use
        ) as minutes_since_track_used,
        js.scheduled_departure,
        tj.id as journey_id
    FROM journey_stops js
    JOIN train_journeys tj ON js.journey_id = tj.id
    LEFT JOIN track_usage tu ON 
        js.station_code = tu.station_code 
        AND js.track = tu.track 
        AND js.scheduled_departure = tu.scheduled_departure
    WHERE js.station_code = 'NY'
      AND js.track IS NOT NULL
      AND js.track != ''
      -- Use last 60 days for training (keeping 30 days for testing)
      AND js.scheduled_departure >= NOW() - INTERVAL '60 days'
      AND js.scheduled_departure < NOW() - INTERVAL '1 day'
      AND tj.is_expired = false
      AND tj.is_cancelled = false
    ORDER BY js.scheduled_departure
    """
    
    print("Executing query...")
    rows = await conn.fetch(query)
    print(f"Found {len(rows)} training samples")
    
    # Create training data with 6 features (track-level prediction)
    print("Processing training data...")
    training_data = []
    
    for row in rows:
        # Create feature row with 6 features (no platform features)
        feature_row = {
            'station_code': row['station_code'],
            'track': row['track'],
            'hour_of_day': int(row['hour_of_day']),
            'day_of_week': int(row['day_of_week']),
            'is_amtrak': row['is_amtrak'],
            'line_code': row['line_code'] or 'UNKNOWN',
            'destination': row['destination'] or 'UNKNOWN',
            'minutes_since_track_used': round(row['minutes_since_track_used'], 1),
        }
        
        training_data.append(feature_row)
    
    # Create output directory if it doesn't exist
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)
    
    # Write to CSV
    output_file = output_dir / "ny_penn_track_training_data.csv"
    
    with open(output_file, 'w', newline='') as csvfile:
        # Define field names with 6 core features (track-level prediction)
        fieldnames = [
            'station_code', 'track', 'hour_of_day', 'day_of_week', 
            'is_amtrak', 'line_code', 'destination', 'minutes_since_track_used'
        ]
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for feature_row in training_data:
            writer.writerow(feature_row)
    
    print(f"Training data exported to {output_file}")
    
    # Print some basic statistics
    print("\n=== Data Statistics ===")
    
    # Track distribution (what we're now predicting)
    track_counts = {}
    for feature_row in training_data:
        track = feature_row['track']
        track_counts[track] = track_counts.get(track, 0) + 1
    
    print("\nTrack distribution (prediction target):")
    for track in sorted(track_counts.keys(), key=lambda x: int(x) if x.isdigit() else 999):
        count = track_counts[track]
        percentage = (count / len(training_data)) * 100
        print(f"  Track {track}: {count} samples ({percentage:.1f}%)")
    
    # Hour distribution
    hour_counts = {}
    for feature_row in training_data:
        hour = feature_row['hour_of_day']
        hour_counts[hour] = hour_counts.get(hour, 0) + 1
    
    print("\nHour of day distribution:")
    for hour in sorted(hour_counts.keys()):
        count = hour_counts[hour]
        print(f"  Hour {hour:02d}: {count} samples")
    
    # Line distribution
    line_counts = {}
    for feature_row in training_data:
        line = feature_row['line_code']
        line_counts[line] = line_counts.get(line, 0) + 1
    
    print("\nLine distribution:")
    for line in sorted(line_counts.keys()):
        count = line_counts[line]
        percentage = (count / len(training_data)) * 100
        print(f"  Line {line}: {count} samples ({percentage:.1f}%)")
    
    # Feature completeness statistics
    print("\nFeature completeness:")
    track_time_available = sum(1 for row in training_data if row['minutes_since_track_used'] != -1)
    
    print(f"  Track usage times available: {track_time_available}/{len(training_data)} samples ({track_time_available/len(training_data)*100:.1f}%)")
    
    await conn.close()
    print("\nExport complete!")


if __name__ == "__main__":
    asyncio.run(export_training_data())