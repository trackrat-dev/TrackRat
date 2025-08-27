#!/usr/bin/env python
"""Debug script to investigate why journeys are not marked complete."""

import asyncio
import asyncpg
import os
from urllib.parse import urlparse

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
    
    print('=== Debug: Why Journeys Are Not Marked Complete ===\n')
    
    # 1. Find trains with all stops departed but not marked complete
    result = await conn.fetch("""
        SELECT tj.id, tj.train_id, tj.data_source, tj.is_completed,
               COUNT(js.id) as total_stops,
               COUNT(CASE WHEN js.has_departed_station = true THEN 1 END) as departed_stops
        FROM train_journeys tj
        JOIN journey_stops js ON tj.id = js.journey_id
        WHERE tj.journey_date >= CURRENT_DATE - INTERVAL '1 day'
        GROUP BY tj.id, tj.train_id, tj.data_source, tj.is_completed
        HAVING COUNT(js.id) = COUNT(CASE WHEN js.has_departed_station = true THEN 1 END)
        ORDER BY tj.id DESC
        LIMIT 3
    """)
    
    print(f'Found {len(result)} trains with ALL stops departed:\n')
    
    for row in result:
        journey_id = row['id']
        print(f'Train {row["train_id"]} (Journey {journey_id}, {row["data_source"]}):')
        print(f'  Status: is_completed = {row["is_completed"]}')
        print(f'  Progress: {row["departed_stops"]}/{row["total_stops"]} stops departed')
        
        # Get the LAST stop details (critical for completion check)
        last_stop = await conn.fetchrow("""
            SELECT station_code, stop_sequence, has_departed_station, 
                   raw_njt_departed_flag, departure_source,
                   actual_departure, scheduled_departure
            FROM journey_stops
            WHERE journey_id = $1
            ORDER BY stop_sequence DESC
            LIMIT 1
        """, journey_id)
        
        if last_stop:
            print(f'  Last stop: {last_stop["station_code"]} (sequence {last_stop["stop_sequence"]})')
            print(f'    has_departed_station: {last_stop["has_departed_station"]}')
            print(f'    raw_njt_departed_flag: "{last_stop["raw_njt_departed_flag"]}"')
            print(f'    departure_source: {last_stop["departure_source"]}')
            
            # The critical check from journey.py line 1164
            if last_stop['raw_njt_departed_flag'] == 'YES':
                print('    ✅ SHOULD BE MARKED COMPLETE (raw flag = YES)')
            else:
                print(f'    ❌ NOT MARKED COMPLETE (raw flag = {last_stop["raw_njt_departed_flag"]})')
        
        # Check segment generation
        segments = await conn.fetchval("""
            SELECT COUNT(*) FROM segment_transit_times 
            WHERE journey_id = $1
        """, journey_id)
        print(f'  Segments generated: {segments}')
        print()
    
    # 2. Check the pattern of raw_njt_departed_flag values
    print('=== Raw DEPARTED Flag Values ===\n')
    flag_counts = await conn.fetch("""
        SELECT raw_njt_departed_flag, COUNT(*) as count
        FROM journey_stops js
        JOIN train_journeys tj ON js.journey_id = tj.id
        WHERE tj.journey_date >= CURRENT_DATE - INTERVAL '1 day'
        GROUP BY raw_njt_departed_flag
        ORDER BY count DESC
    """)
    
    print('Distribution of raw_njt_departed_flag values:')
    for row in flag_counts:
        flag = row['raw_njt_departed_flag'] if row['raw_njt_departed_flag'] else 'NULL'
        print(f'  "{flag}": {row["count"]} occurrences')
    
    # 3. The core issue - check the completion logic
    print('\n=== The Core Issue ===\n')
    print('Journey completion logic (njt/journey.py lines 1163-1164):')
    print('  last_stop = stops_data[-1]')
    print('  if last_stop.DEPARTED == "YES":  # Checks API response')
    print('    journey.is_completed = True')
    print()
    print('But has_departed_station is set via inference (time-based, sequential)')
    print('The raw_njt_departed_flag may not be "YES" even when departed!')
    print()
    
    # Check if ANY journey has raw flag = YES for last stop
    yes_last_stops = await conn.fetchval("""
        SELECT COUNT(DISTINCT js.journey_id)
        FROM journey_stops js
        WHERE js.raw_njt_departed_flag = 'YES'
        AND js.stop_sequence = (
            SELECT MAX(js2.stop_sequence)
            FROM journey_stops js2
            WHERE js2.journey_id = js.journey_id
        )
    """)
    
    print(f'Journeys with last stop raw_njt_departed_flag="YES": {yes_last_stops}')
    
    # 4. Impact assessment
    print('\n=== Impact Assessment ===\n')
    
    # Count of segments that SHOULD exist
    potential_segments = await conn.fetchval("""
        SELECT SUM(stop_count - 1) as potential
        FROM (
            SELECT COUNT(*) as stop_count
            FROM journey_stops js
            JOIN train_journeys tj ON js.journey_id = tj.id
            WHERE tj.journey_date >= CURRENT_DATE - INTERVAL '1 day'
            AND js.has_departed_station = true
            GROUP BY tj.id
            HAVING COUNT(*) >= 2
        ) t
    """)
    
    actual_segments = await conn.fetchval("""
        SELECT COUNT(*) FROM segment_transit_times
        WHERE departure_time >= CURRENT_DATE - INTERVAL '1 day'
    """)
    
    print(f'Potential segments (if all analyzed): {potential_segments or 0}')
    print(f'Actual segments in database: {actual_segments}')
    print(f'Missing segments: {(potential_segments or 0) - actual_segments}')
    
    await conn.close()
    
    print('\n=== Root Cause ===\n')
    print('BUG IDENTIFIED: Journey completion check uses raw API "DEPARTED" flag,')
    print('but most stops use inferred departure (time_inference, sequential_inference).')
    print('This means journeys are NEVER marked complete, so analyze_journey() is')
    print('NEVER called, resulting in NO segment generation!')
    print()
    print('Solution: Fix completion logic to use has_departed_station instead of raw flag.')

if __name__ == '__main__':
    asyncio.run(main())