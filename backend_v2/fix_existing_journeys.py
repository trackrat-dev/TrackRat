#!/usr/bin/env python
"""Script to retroactively fix journey completion status and generate missing segments."""

import asyncio
import os
from datetime import datetime, timedelta
from trackrat.db.engine import get_session
from trackrat.models.database import TrainJourney, JourneyStop, SegmentTransitTime
from trackrat.services.transit_analyzer import TransitAnalyzer
from sqlalchemy import select, and_, func

async def fix_existing_journeys(days_back: int = 7):
    """Fix journey completion status for existing data.
    
    Args:
        days_back: Number of days to look back for journeys to fix
    """
    
    print(f"=== Fixing Journey Completion Status ({days_back} days) ===\n")
    
    transit_analyzer = TransitAnalyzer()
    
    async with get_session() as session:
        # Find journeys that should be complete but aren't
        cutoff_date = datetime.now().date() - timedelta(days=days_back)
        
        # Get journeys where all stops have departed but journey isn't marked complete
        stmt = (
            select(TrainJourney)
            .where(
                and_(
                    TrainJourney.journey_date >= cutoff_date,
                    TrainJourney.is_completed == False,
                    TrainJourney.is_cancelled == False,
                )
            )
        )
        
        result = await session.execute(stmt)
        journeys = result.scalars().all()
        
        print(f"Found {len(journeys)} uncompleted journeys to check\n")
        
        fixed_count = 0
        segments_created_total = 0
        
        for journey in journeys:
            # Get the last stop for this journey
            last_stop_stmt = (
                select(JourneyStop)
                .where(JourneyStop.journey_id == journey.id)
                .order_by(JourneyStop.stop_sequence.desc())
                .limit(1)
            )
            
            last_stop_result = await session.execute(last_stop_stmt)
            last_stop = last_stop_result.scalar_one_or_none()
            
            if last_stop and last_stop.has_departed_station:
                # This journey should be marked complete
                print(f"Fixing journey {journey.train_id} (ID: {journey.id})")
                print(f"  Last stop {last_stop.station_code} has departed")
                
                # Mark journey as complete
                journey.is_completed = True
                fixed_count += 1
                
                # Run full analysis
                print(f"  Running full analysis...")
                await transit_analyzer.analyze_journey(session, journey)
                
                # Count segments created
                segments_count = await session.scalar(
                    select(func.count()).select_from(SegmentTransitTime).where(
                        SegmentTransitTime.journey_id == journey.id
                    )
                )
                segments_created_total += segments_count
                print(f"  ✅ Fixed! Generated {segments_count} segments")
                
                # Commit after each journey to avoid large transactions
                await session.commit()
        
        print(f"\n📊 Summary:")
        print(f"  Journeys fixed: {fixed_count}/{len(journeys)}")
        print(f"  Total segments generated: {segments_created_total}")
        
        if fixed_count > 0:
            print("\n✅ SUCCESS: Historical data has been fixed!")
            
            # Show overall segment statistics
            total_segments = await session.scalar(
                select(func.count()).select_from(SegmentTransitTime)
            )
            
            recent_segments = await session.scalar(
                select(func.count()).select_from(SegmentTransitTime).where(
                    SegmentTransitTime.departure_time >= datetime.now() - timedelta(hours=6)
                )
            )
            
            print(f"\nDatabase Statistics:")
            print(f"  Total segments: {total_segments}")
            print(f"  Segments in last 6 hours: {recent_segments}")
            
            # Check specific high-traffic routes
            ny_se_segments = await session.scalar(
                select(func.count()).select_from(SegmentTransitTime).where(
                    and_(
                        SegmentTransitTime.from_station_code == "NY",
                        SegmentTransitTime.to_station_code == "SE"
                    )
                )
            )
            
            print(f"  NY→SE segments: {ny_se_segments}")
        else:
            print("\nℹ️  No journeys needed fixing (all were already correct)")

async def main():
    """Main function to run the fix."""
    
    print("This script will fix journey completion status and generate missing segments.")
    print("It's safe to run multiple times - it only fixes journeys that need it.\n")
    
    # You can adjust the number of days to look back
    days = 7  # Look back 7 days by default
    
    await fix_existing_journeys(days_back=days)
    
    print("\n=== Fix Complete ===")

if __name__ == "__main__":
    # Set up environment if needed
    if not os.getenv("TRACKRAT_DATABASE_URL"):
        os.environ["TRACKRAT_DATABASE_URL"] = "postgresql+asyncpg://postgres:password@127.0.0.1:5433/trackratdb"
    
    asyncio.run(main())