#!/usr/bin/env python3
"""
Export training data for track predictions across multiple stations.

This script extracts historical track assignments and features from the database
to create CSV files for training machine learning models.

Usage:
    python export_track_training_data.py          # Export for all eligible stations
    python export_track_training_data.py NY       # Export for specific station
    python export_track_training_data.py NP TR    # Export for multiple stations

Output: data/{station_code}_track_training_data.csv
"""

import asyncio
import csv
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trackrat.config.station_configs import (
    get_station_config,
    get_ml_enabled_stations,
)

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


async def export_training_data_for_station(conn, station_code: str):
    """Export track prediction training data for a specific station."""
    
    config = get_station_config(station_code)
    
    # Check if station has ML enabled
    if not config["ml_enabled"]:
        print(f"Skipping {station_code}: ML not enabled")
        return False
    
    # First check if station has enough data
    count_query = """
        SELECT COUNT(*) as count
        FROM journey_stops js
        JOIN train_journeys tj ON js.journey_id = tj.id
        WHERE js.station_code = $1
          AND js.track IS NOT NULL
          AND js.track != ''
          AND tj.is_expired = false
          AND tj.is_cancelled = false
    """
    
    result = await conn.fetchrow(count_query, station_code)
    record_count = result['count']
    
    if record_count < config['min_samples_required']:
        print(f"Skipping {station_code}: only {record_count} samples (minimum {config['min_samples_required']} required)")
        return False
    
    print(f"\nExporting data for {station_code} ({record_count} samples available)")
    
    # Query to extract training data for track-level prediction
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
        WHERE js.station_code = $1
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
    WHERE js.station_code = $1
      AND js.track IS NOT NULL
      AND js.track != ''
      -- Use last 60 days for training (keeping 30 days for testing)
      AND js.scheduled_departure >= NOW() - INTERVAL '60 days'
      AND js.scheduled_departure < NOW() - INTERVAL '1 day'
      AND tj.is_expired = false
      AND tj.is_cancelled = false
    ORDER BY js.scheduled_departure
    """
    
    rows = await conn.fetch(query, station_code)
    print(f"  Found {len(rows)} training samples")
    
    if len(rows) < config['min_samples_required']:
        print(f"  Not enough training samples after filtering")
        return False
    
    # Create training data
    training_data = []
    
    for row in rows:
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
    output_file = output_dir / f"{station_code.lower()}_track_training_data.csv"
    
    with open(output_file, 'w', newline='') as csvfile:
        fieldnames = [
            'station_code', 'track', 'hour_of_day', 'day_of_week', 
            'is_amtrak', 'line_code', 'destination', 'minutes_since_track_used'
        ]
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for feature_row in training_data:
            writer.writerow(feature_row)
    
    print(f"  Exported to {output_file}")
    
    # Print basic statistics
    track_counts = {}
    for feature_row in training_data:
        track = feature_row['track']
        track_counts[track] = track_counts.get(track, 0) + 1
    
    # Sort tracks properly (numeric first, then alphabetic)
    sorted_tracks = sorted(track_counts.keys(), 
                          key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x))
    
    print(f"  Track distribution: {', '.join(f'{t}:{track_counts[t]}' for t in sorted_tracks)}")
    
    return True


async def export_training_data(station_codes: list[str] = None):
    """Export track prediction training data for specified stations or all eligible ones."""
    
    conn = await get_database_connection()
    print("Connected to database")
    
    # Determine which stations to export
    if station_codes:
        stations = station_codes
        print(f"Exporting data for specified stations: {', '.join(stations)}")
    else:
        stations = get_ml_enabled_stations()
        print(f"Exporting data for all {len(stations)} ML-enabled stations")
    
    # Export data for each station
    successful_exports = []
    failed_exports = []
    
    for station_code in stations:
        try:
            success = await export_training_data_for_station(conn, station_code)
            if success:
                successful_exports.append(station_code)
            else:
                failed_exports.append(station_code)
        except Exception as e:
            print(f"Error exporting data for {station_code}: {e}")
            failed_exports.append(station_code)
    
    await conn.close()
    
    # Print summary
    print("\n=== Export Summary ===")
    print(f"Successfully exported: {len(successful_exports)} stations")
    if successful_exports:
        print(f"  Stations: {', '.join(successful_exports)}")
    
    if failed_exports:
        print(f"Failed/Skipped: {len(failed_exports)} stations")
        print(f"  Stations: {', '.join(failed_exports)}")
    
    print("\nExport complete!")


if __name__ == "__main__":
    # Get station codes from command line arguments
    station_codes = sys.argv[1:] if len(sys.argv) > 1 else None
    asyncio.run(export_training_data(station_codes))