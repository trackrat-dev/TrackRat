#!/usr/bin/env python
"""Test script to verify the journey completion fix generates segments correctly."""

import asyncio
import os
from datetime import datetime
from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.collectors.njt.client import NJTransitClient
from trackrat.db.engine import get_session
from trackrat.models.database import TrainJourney, SegmentTransitTime
from sqlalchemy import select, func

async def test_completion_fix():
    """Test that the fixed completion logic properly generates segments."""
    
    print("=== Testing Journey Completion Fix ===\n")
    
    # Initialize collector
    client = NJTransitClient()
    collector = JourneyCollector(client)
    
    try:
        async with get_session() as session:
            # Count segments before
            segments_before = await session.scalar(
                select(func.count()).select_from(SegmentTransitTime)
            )
            print(f"Segments before collection: {segments_before}")
            
            # Collect a specific train journey that we know has departed stops
            # You can change this to any active train ID
            train_id = "3227"  # Example train that should have segments
            
            print(f"\nCollecting journey for train {train_id}...")
            journey_dict = await collector.collect_journey(train_id)
            
            if journey_dict:
                print(f"✅ Journey collected successfully")
                print(f"  Train: {journey_dict['train_id']}")
                print(f"  Stops: {journey_dict['stops_count']}")
                print(f"  Completed: {journey_dict.get('is_completed', False)}")
                
                # Get the journey from database
                stmt = select(TrainJourney).where(
                    TrainJourney.train_id == train_id,
                    TrainJourney.journey_date == datetime.now().date()
                )
                result = await session.execute(stmt)
                journey = result.scalar_one_or_none()
                
                if journey:
                    # Count segments for this journey
                    journey_segments = await session.scalar(
                        select(func.count()).select_from(SegmentTransitTime).where(
                            SegmentTransitTime.journey_id == journey.id
                        )
                    )
                    print(f"  Segments for this journey: {journey_segments}")
                    
                    # If journey is marked complete, check full analysis results
                    if journey.is_completed:
                        print(f"  ✅ Journey marked as COMPLETE")
                        
                        # Check dwell times and progress
                        from trackrat.models.database import StationDwellTime, JourneyProgress
                        
                        dwell_count = await session.scalar(
                            select(func.count()).select_from(StationDwellTime).where(
                                StationDwellTime.journey_id == journey.id
                            )
                        )
                        
                        progress = await session.get(JourneyProgress, journey.id)
                        
                        print(f"  Dwell times created: {dwell_count}")
                        if progress:
                            print(f"  Progress: {progress.stops_completed}/{progress.stops_total} stops")
                    else:
                        print(f"  Journey NOT marked complete (may still be in progress)")
                
            else:
                print("❌ Journey collection failed")
            
            # Count segments after
            segments_after = await session.scalar(
                select(func.count()).select_from(SegmentTransitTime)
            )
            print(f"\n📊 Results:")
            print(f"  Segments before: {segments_before}")
            print(f"  Segments after: {segments_after}")
            print(f"  New segments created: {segments_after - segments_before}")
            
            if segments_after > segments_before:
                print("\n✅ SUCCESS: Segments are being generated!")
                
                # Show a few sample segments
                recent_segments = await session.execute(
                    select(SegmentTransitTime)
                    .order_by(SegmentTransitTime.created_at.desc())
                    .limit(5)
                )
                
                print("\nSample segments created:")
                for segment in recent_segments.scalars():
                    print(f"  {segment.from_station_code}→{segment.to_station_code}: {segment.actual_minutes} min")
            else:
                print("\n⚠️  No new segments created")
                print("This could mean:")
                print("  1. The train hasn't departed any stops yet")
                print("  2. Segments already exist for this journey")
                print("  3. The train data doesn't have actual times")
            
            await session.commit()
            
    finally:
        await client.close()
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    # Set up environment if needed
    if not os.getenv("TRACKRAT_DATABASE_URL"):
        os.environ["TRACKRAT_DATABASE_URL"] = "postgresql+asyncpg://postgres:password@127.0.0.1:5433/trackratdb"
    
    asyncio.run(test_completion_fix())