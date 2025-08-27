#!/usr/bin/env python
"""Debug script to investigate missing NY->SE segments."""

import asyncio
import asyncpg
import os
from urllib.parse import urlparse
from datetime import datetime, timedelta

async def main():
    db_url = os.getenv('TRACKRAT_DATABASE_URL', '')
    url = db_url.replace('postgresql+asyncpg://', 'postgresql://')
    parsed = urlparse(url)
    
    conn = await asyncpg.connect(
        host=parsed.hostname or 'localhost',
        port=parsed.port or 5433,
        user=parsed.username,
        password=parsed.password,
        database=parsed.path.lstrip('/') if parsed.path else 'postgres'
    )
    
    print('=== Debugging NY->SE Segment Generation ===\n')
    
    # 1. Check a specific train journey with NY->SE
    train_data = await conn.fetchrow("""
        SELECT tj.id as journey_id, tj.train_id, tj.is_completed, tj.data_source,
               tj.last_updated_at, tj.update_count
        FROM train_journeys tj
        WHERE tj.train_id = '3227'
        AND tj.journey_date = '2025-08-26'
    """)
    
    if train_data:
        journey_id = train_data['journey_id']
        print(f'Examining Train 3227 (Journey ID: {journey_id})')
        print(f'  Last updated: {train_data["last_updated_at"]}')
        print(f'  Update count: {train_data["update_count"]}')
        print(f'  Is completed: {train_data["is_completed"]}')
        print()
        
        # Get all stops for this journey
        stops = await conn.fetch("""
            SELECT station_code, stop_sequence, 
                   scheduled_departure, actual_departure,
                   scheduled_arrival, actual_arrival,
                   has_departed_station
            FROM journey_stops 
            WHERE journey_id = $1
            ORDER BY stop_sequence
        """, journey_id)
        
        print(f'Stops for this journey (checking segment creation potential):')
        print('Seq | Station | Scheduled Dep | Actual Dep | Scheduled Arr | Actual Arr | Departed')
        print('-' * 90)
        
        prev_stop = None
        potential_segments = []
        
        for stop in stops:
            # Format times
            sched_dep = stop['scheduled_departure'].strftime('%H:%M') if stop['scheduled_departure'] else 'None'
            actual_dep = stop['actual_departure'].strftime('%H:%M') if stop['actual_departure'] else 'None'
            sched_arr = stop['scheduled_arrival'].strftime('%H:%M') if stop['scheduled_arrival'] else 'None'
            actual_arr = stop['actual_arrival'].strftime('%H:%M') if stop['actual_arrival'] else 'None'
            departed = 'Y' if stop['has_departed_station'] else 'N'
            
            print(f'{stop["stop_sequence"]:3} | {stop["station_code"]:7} | {sched_dep:13} | {actual_dep:10} | {sched_arr:13} | {actual_arr:10} | {departed}')
            
            # Check if we can create a segment with the previous stop
            if prev_stop:
                # TransitAnalyzer logic: COALESCE approach
                departure_time = prev_stop['actual_departure'] or prev_stop['scheduled_departure']
                arrival_time = stop['actual_arrival'] or stop['scheduled_arrival']
                
                if departure_time and arrival_time:
                    segment_key = f"{prev_stop['station_code']}->{stop['station_code']}"
                    potential_segments.append(segment_key)
                    print(f'    ✓ Could create segment: {segment_key}')
            
            prev_stop = stop
        
        print(f'\nPotential segments for this journey: {len(potential_segments)}')
        for seg in potential_segments:
            print(f'  - {seg}')
        
        # Check actual segments created
        actual_segments = await conn.fetch("""
            SELECT from_station_code, to_station_code, actual_minutes, departure_time
            FROM segment_transit_times 
            WHERE journey_id = $1
        """, journey_id)
        
        print(f'\nActual segments in database: {len(actual_segments)}')
        for seg in actual_segments:
            print(f'  - {seg["from_station_code"]}->{seg["to_station_code"]} ({seg["actual_minutes"]} min)')
        
        # If mismatch, this is the bug!
        if len(potential_segments) > len(actual_segments):
            print('\n❌ BUG FOUND: TransitAnalyzer is not creating all expected segments!')
            print(f'   Expected: {len(potential_segments)} segments')
            print(f'   Actual: {len(actual_segments)} segments')
            
            # Check when TransitAnalyzer runs
            print('\n   Checking if journey is eligible for TransitAnalyzer:')
            print(f'   - Is completed: {train_data["is_completed"]}')
            print(f'   - Has departed stations: {any(s["has_departed_station"] for s in stops)}')
            
    # 2. Check overall segment generation patterns
    print('\n=== Overall Segment Generation Patterns ===')
    
    # Which stations have segments?
    station_stats = await conn.fetch("""
        SELECT 
            station_code,
            SUM(CASE WHEN station_code = from_station_code THEN 1 ELSE 0 END) as from_count,
            SUM(CASE WHEN station_code = to_station_code THEN 1 ELSE 0 END) as to_count
        FROM 
            (SELECT DISTINCT from_station_code as station_code FROM segment_transit_times
             UNION 
             SELECT DISTINCT to_station_code FROM segment_transit_times) stations
        LEFT JOIN segment_transit_times st1 ON stations.station_code = st1.from_station_code
        LEFT JOIN segment_transit_times st2 ON stations.station_code = st2.to_station_code
        GROUP BY station_code
        ORDER BY station_code
    """)
    
    print('\nStations in segment_transit_times:')
    for stat in station_stats:
        print(f'  {stat["station_code"]}: {stat["from_count"]} departures, {stat["to_count"]} arrivals')
    
    # Check if TransitAnalyzer is being called at all
    print('\n=== Recent Journey Updates (TransitAnalyzer should run on these) ===')
    recent_updates = await conn.fetch("""
        SELECT tj.id, tj.train_id, tj.last_updated_at, tj.is_completed,
               COUNT(st.id) as segment_count
        FROM train_journeys tj
        LEFT JOIN segment_transit_times st ON tj.id = st.journey_id
        WHERE tj.last_updated_at >= NOW() - INTERVAL '2 hours'
        GROUP BY tj.id, tj.train_id, tj.last_updated_at, tj.is_completed
        ORDER BY tj.last_updated_at DESC
        LIMIT 10
    """)
    
    for journey in recent_updates:
        print(f'  Journey {journey["id"]} (Train {journey["train_id"]}): Updated {journey["last_updated_at"]} | Segments: {journey["segment_count"]} | Completed: {journey["is_completed"]}')
    
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())