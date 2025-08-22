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
    
    # Query to extract training data
    # Each row is a historical track assignment with features
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
    ),
    platform_usage AS (
        -- Calculate time since each platform was last used
        -- Platform mapping: 1&2, 3&4, 5&6, etc.
        SELECT 
            js.station_code,
            CASE 
                WHEN js.track IN ('1', '2') THEN '1 & 2'
                WHEN js.track IN ('3', '4') THEN '3 & 4'
                WHEN js.track IN ('5', '6') THEN '5 & 6'
                WHEN js.track IN ('7', '8') THEN '7 & 8'
                WHEN js.track IN ('9', '10') THEN '9 & 10'
                WHEN js.track IN ('11', '12') THEN '11 & 12'
                WHEN js.track IN ('13', '14') THEN '13 & 14'
                WHEN js.track IN ('15', '16') THEN '15 & 16'
                WHEN js.track = '17' THEN '17'
                WHEN js.track IN ('18', '19') THEN '18 & 19'
                WHEN js.track IN ('20', '21') THEN '20 & 21'
                ELSE js.track
            END as platform,
            js.scheduled_departure,
            LAG(js.scheduled_departure) OVER (
                PARTITION BY js.station_code,
                CASE 
                    WHEN js.track IN ('1', '2') THEN '1 & 2'
                    WHEN js.track IN ('3', '4') THEN '3 & 4'
                    WHEN js.track IN ('5', '6') THEN '5 & 6'
                    WHEN js.track IN ('7', '8') THEN '7 & 8'
                    WHEN js.track IN ('9', '10') THEN '9 & 10'
                    WHEN js.track IN ('11', '12') THEN '11 & 12'
                    WHEN js.track IN ('13', '14') THEN '13 & 14'
                    WHEN js.track IN ('15', '16') THEN '15 & 16'
                    WHEN js.track = '17' THEN '17'
                    WHEN js.track IN ('18', '19') THEN '18 & 19'
                    WHEN js.track IN ('20', '21') THEN '20 & 21'
                    ELSE js.track
                END
                ORDER BY js.scheduled_departure
            ) as prev_platform_use_time
        FROM journey_stops js
        WHERE js.station_code = 'NY'
          AND js.track IS NOT NULL
          AND js.track != ''
          AND js.scheduled_departure >= NOW() - INTERVAL '90 days'
    )
    SELECT 
        js.station_code,
        js.track,
        -- Platform mapping for NY Penn Station
        CASE 
            WHEN js.track IN ('1', '2') THEN '1 & 2'
            WHEN js.track IN ('3', '4') THEN '3 & 4'
            WHEN js.track IN ('5', '6') THEN '5 & 6'
            WHEN js.track IN ('7', '8') THEN '7 & 8'
            WHEN js.track IN ('9', '10') THEN '9 & 10'
            WHEN js.track IN ('11', '12') THEN '11 & 12'
            WHEN js.track IN ('13', '14') THEN '13 & 14'
            WHEN js.track IN ('15', '16') THEN '15 & 16'
            WHEN js.track = '17' THEN '17'
            WHEN js.track IN ('18', '19') THEN '18 & 19'
            WHEN js.track IN ('20', '21') THEN '20 & 21'
            ELSE js.track
        END as platform,
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
        -- Time since platform was last used (in minutes)
        COALESCE(
            EXTRACT(EPOCH FROM (js.scheduled_departure - pu.prev_platform_use_time)) / 60,
            -1  -- Use -1 for unknown/first use
        ) as minutes_since_platform_used
    FROM journey_stops js
    JOIN train_journeys tj ON js.journey_id = tj.id
    LEFT JOIN track_usage tu ON 
        js.station_code = tu.station_code 
        AND js.track = tu.track 
        AND js.scheduled_departure = tu.scheduled_departure
    LEFT JOIN platform_usage pu ON 
        js.station_code = pu.station_code 
        AND js.scheduled_departure = pu.scheduled_departure
    WHERE js.station_code = 'NY'
      AND js.track IS NOT NULL
      AND js.track != ''
      -- Use last 60 days for training (keeping 30 days for testing)
      AND js.scheduled_departure >= NOW() - INTERVAL '60 days'
      AND js.scheduled_departure < NOW() - INTERVAL '1 day'
    ORDER BY js.scheduled_departure
    """
    
    print("Executing query...")
    rows = await conn.fetch(query)
    print(f"Found {len(rows)} training samples")
    
    # Create output directory if it doesn't exist
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)
    
    # Write to CSV
    output_file = output_dir / "ny_penn_track_training_data.csv"
    
    with open(output_file, 'w', newline='') as csvfile:
        fieldnames = [
            'station_code', 'track', 'platform', 'hour_of_day', 'day_of_week', 
            'is_amtrak', 'line_code', 'destination',
            'minutes_since_track_used', 'minutes_since_platform_used'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        
        for row in rows:
            writer.writerow({
                'station_code': row['station_code'],
                'track': row['track'],
                'platform': row['platform'],
                'hour_of_day': int(row['hour_of_day']),
                'day_of_week': int(row['day_of_week']),
                'is_amtrak': row['is_amtrak'],
                'line_code': row['line_code'] or 'UNKNOWN',
                'destination': row['destination'] or 'UNKNOWN',
                'minutes_since_track_used': round(row['minutes_since_track_used'], 1),
                'minutes_since_platform_used': round(row['minutes_since_platform_used'], 1)
            })
    
    print(f"Training data exported to {output_file}")
    
    # Print some basic statistics
    print("\n=== Data Statistics ===")
    
    # Platform distribution (what we're now predicting)
    platform_counts = {}
    for row in rows:
        platform = row['platform']
        platform_counts[platform] = platform_counts.get(platform, 0) + 1
    
    print("\nPlatform distribution:")
    for platform in sorted(platform_counts.keys()):
        count = platform_counts[platform]
        percentage = (count / len(rows)) * 100
        print(f"  Platform {platform}: {count} samples ({percentage:.1f}%)")
    
    # Track distribution (for reference)
    track_counts = {}
    for row in rows:
        track = row['track']
        track_counts[track] = track_counts.get(track, 0) + 1
    
    print("\nTrack distribution (for reference):")
    for track in sorted(track_counts.keys(), key=lambda x: int(x) if x.isdigit() else 999):
        count = track_counts[track]
        percentage = (count / len(rows)) * 100
        print(f"  Track {track}: {count} samples ({percentage:.1f}%)")
    
    # Hour distribution
    hour_counts = {}
    for row in rows:
        hour = int(row['hour_of_day'])
        hour_counts[hour] = hour_counts.get(hour, 0) + 1
    
    print("\nHour of day distribution:")
    for hour in sorted(hour_counts.keys()):
        count = hour_counts[hour]
        print(f"  Hour {hour:02d}: {count} samples")
    
    # Line distribution
    line_counts = {}
    for row in rows:
        line = row['line_code'] or 'UNKNOWN'
        line_counts[line] = line_counts.get(line, 0) + 1
    
    print("\nLine distribution:")
    for line in sorted(line_counts.keys()):
        count = line_counts[line]
        percentage = (count / len(rows)) * 100
        print(f"  Line {line}: {count} samples ({percentage:.1f}%)")
    
    await conn.close()
    print("\nExport complete!")


if __name__ == "__main__":
    asyncio.run(export_training_data())