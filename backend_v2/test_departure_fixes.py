#!/usr/bin/env python
"""
Test script to validate the three critical data quality fixes:
1. Actual arrival/departure population (should increase from 18.8% to ~95%)
2. has_departed_station flag staleness (should be properly updated)
3. Swapped arrival/departure times (should be corrected)
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import asyncpg
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Add the src directory to path
import sys
sys.path.insert(0, '/Users/andy/projects/TrackRat/backend_v2/src')

from trackrat.db.engine import get_db
from trackrat.models.database import TrainJourney, JourneyStop
from trackrat.collectors.njt.client import NJTransitClient
from trackrat.collectors.njt.journey import JourneyCollector
from trackrat.utils.time import now_et
from structlog import get_logger

logger = get_logger(__name__)

# Database URL for test database
DATABASE_URL = os.getenv(
    "TRACKRAT_DATABASE_URL",
    "postgresql+asyncpg://postgres:password@127.0.0.1:5433/trackratdb"
)


async def get_test_session() -> AsyncSession:
    """Create a test database session."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        return session


async def analyze_current_data_quality() -> Dict:
    """Analyze current data quality metrics before running the fix."""
    session = await get_test_session()
    
    try:
        # Metric 1: Actual arrival/departure population for NY Penn with tracks
        result = await session.execute(
            select(
                func.count(JourneyStop.id).label('total'),
                func.count(JourneyStop.actual_arrival).label('has_actual_arrival'),
                func.count(JourneyStop.actual_departure).label('has_actual_departure'),
            ).where(
                and_(
                    JourneyStop.station_code == 'NY',
                    JourneyStop.track.isnot(None),
                    JourneyStop.scheduled_departure >= now_et() - timedelta(days=7)
                )
            )
        )
        population_stats = result.first()
        
        # Metric 2: has_departed_station staleness
        result = await session.execute(
            select(
                func.count(JourneyStop.id).label('total'),
                func.count(func.nullif(JourneyStop.has_departed_station, False)).label('marked_departed')
            ).where(
                and_(
                    JourneyStop.station_code == 'NY',
                    JourneyStop.scheduled_departure <= now_et() - timedelta(hours=2),
                    JourneyStop.scheduled_departure >= now_et() - timedelta(days=1)
                )
            )
        )
        departure_stats = result.first()
        
        # Metric 3: Swapped times (arrival > departure for intermediate stops)
        result = await session.execute(
            select(func.count(JourneyStop.id)).where(
                and_(
                    JourneyStop.actual_arrival.isnot(None),
                    JourneyStop.actual_departure.isnot(None),
                    JourneyStop.actual_arrival > JourneyStop.actual_departure,
                    JourneyStop.stop_sequence > 0  # Not origin
                )
            )
        )
        swapped_count = result.scalar()
        
        # NEW: Check departure_source distribution
        result = await session.execute(
            select(
                JourneyStop.departure_source,
                func.count(JourneyStop.id).label('count')
            ).where(
                JourneyStop.has_departed_station == True
            ).group_by(JourneyStop.departure_source)
        )
        departure_sources = {row.departure_source: row.count for row in result}
        
        await session.close()
        
        return {
            'population': {
                'total': population_stats.total,
                'has_actual_arrival': population_stats.has_actual_arrival,
                'has_actual_departure': population_stats.has_actual_departure,
                'arrival_rate': (population_stats.has_actual_arrival / population_stats.total * 100) if population_stats.total > 0 else 0,
                'departure_rate': (population_stats.has_actual_departure / population_stats.total * 100) if population_stats.total > 0 else 0,
            },
            'departed_flag': {
                'total_overdue': departure_stats.total,
                'marked_departed': departure_stats.marked_departed,
                'departed_rate': (departure_stats.marked_departed / departure_stats.total * 100) if departure_stats.total > 0 else 0,
            },
            'swapped_times': swapped_count,
            'departure_sources': departure_sources
        }
        
    except Exception as e:
        logger.error(f"Error analyzing data quality: {e}")
        await session.close()
        raise


async def run_njt_collection_cycle() -> int:
    """Run a single NJT collection cycle to test the fixes."""
    session = await get_test_session()
    
    try:
        # Initialize NJT client and collector
        # Note: This will use TRACKRAT_NJT_API_TOKEN from environment
        njt_client = NJTransitClient()
        collector = JourneyCollector(njt_client)
        
        # Find active journeys that need updates
        # Use 2025-08-22 data since we have 476 NJT journeys from that date
        from datetime import date
        test_date = date(2025, 8, 22)
        
        result = await session.execute(
            select(TrainJourney).where(
                and_(
                    TrainJourney.data_source == 'NJT',
                    TrainJourney.journey_date == test_date,
                )
            ).limit(20)  # Test with 20 journeys to get good sample
        )
        journeys = result.scalars().all()
        
        logger.info(f"Found {len(journeys)} active NJT journeys to update")
        
        # Update each journey
        updated_count = 0
        for journey in journeys:
            try:
                logger.info(f"Updating journey {journey.train_id} (ID: {journey.id})")
                await collector.collect_journey_details(session, journey)
                await session.commit()
                updated_count += 1
            except Exception as e:
                logger.error(f"Failed to update journey {journey.train_id}: {e}")
                await session.rollback()
        
        await session.close()
        return updated_count
        
    except Exception as e:
        logger.error(f"Error in collection cycle: {e}")
        await session.close()
        raise


async def validate_fixes() -> None:
    """Validate that all three fixes are working correctly."""
    print("\n" + "="*80)
    print("VALIDATING DATA QUALITY FIXES")
    print("="*80)
    
    # Analyze before fixes
    print("\n📊 BEFORE: Current Data Quality Metrics")
    print("-" * 40)
    before_metrics = await analyze_current_data_quality()
    
    print(f"1. Actual Times Population (NY Penn with tracks):")
    print(f"   - Arrival Rate: {before_metrics['population']['arrival_rate']:.1f}%")
    print(f"   - Departure Rate: {before_metrics['population']['departure_rate']:.1f}%")
    print(f"   - Total Records: {before_metrics['population']['total']}")
    
    print(f"\n2. Departed Flag Staleness (trains >2 hours old):")
    print(f"   - Marked Departed: {before_metrics['departed_flag']['departed_rate']:.1f}%")
    print(f"   - Total Overdue: {before_metrics['departed_flag']['total_overdue']}")
    
    print(f"\n3. Swapped Times (arrival > departure):")
    print(f"   - Affected Records: {before_metrics['swapped_times']}")
    
    print(f"\n4. Departure Sources:")
    for source, count in before_metrics['departure_sources'].items():
        print(f"   - {source or 'NULL'}: {count}")
    
    # Run collection cycle
    print("\n🔄 Running NJT Collection Cycle...")
    print("-" * 40)
    updated = await run_njt_collection_cycle()
    print(f"✅ Updated {updated} journeys")
    
    # Analyze after fixes
    print("\n📊 AFTER: Updated Data Quality Metrics")
    print("-" * 40)
    after_metrics = await analyze_current_data_quality()
    
    print(f"1. Actual Times Population (NY Penn with tracks):")
    print(f"   - Arrival Rate: {after_metrics['population']['arrival_rate']:.1f}% " +
          f"({'↑' if after_metrics['population']['arrival_rate'] > before_metrics['population']['arrival_rate'] else '↓'} " +
          f"{after_metrics['population']['arrival_rate'] - before_metrics['population']['arrival_rate']:.1f}%)")
    print(f"   - Departure Rate: {after_metrics['population']['departure_rate']:.1f}% " +
          f"({'↑' if after_metrics['population']['departure_rate'] > before_metrics['population']['departure_rate'] else '↓'} " +
          f"{after_metrics['population']['departure_rate'] - before_metrics['population']['departure_rate']:.1f}%)")
    
    print(f"\n2. Departed Flag Staleness (trains >2 hours old):")
    print(f"   - Marked Departed: {after_metrics['departed_flag']['departed_rate']:.1f}% " +
          f"({'↑' if after_metrics['departed_flag']['departed_rate'] > before_metrics['departed_flag']['departed_rate'] else '↓'} " +
          f"{after_metrics['departed_flag']['departed_rate'] - before_metrics['departed_flag']['departed_rate']:.1f}%)")
    
    print(f"\n3. Swapped Times (arrival > departure):")
    print(f"   - Affected Records: {after_metrics['swapped_times']} " +
          f"({'↓' if after_metrics['swapped_times'] < before_metrics['swapped_times'] else '↑'} " +
          f"{before_metrics['swapped_times'] - after_metrics['swapped_times']})")
    
    print(f"\n4. Departure Sources (NEW):")
    for source, count in after_metrics['departure_sources'].items():
        before_count = before_metrics['departure_sources'].get(source, 0)
        diff = count - before_count
        print(f"   - {source or 'NULL'}: {count} {'(+' + str(diff) + ')' if diff > 0 else ''}")
    
    # Validate success criteria
    print("\n" + "="*80)
    print("VALIDATION RESULTS")
    print("="*80)
    
    success = True
    
    # Check Fix 1: Actual times should be >90% populated
    if after_metrics['population']['arrival_rate'] > 90:
        print("✅ Fix 1 PASSED: Actual arrival rate > 90%")
    else:
        print("❌ Fix 1 FAILED: Actual arrival rate still low")
        success = False
    
    # Check Fix 2: Departed flag should be >90% for old trains
    if after_metrics['departed_flag']['departed_rate'] > 90:
        print("✅ Fix 2 PASSED: Departed flag properly updated")
    else:
        print("❌ Fix 2 FAILED: Departed flag still stale")
        success = False
    
    # Check Fix 3: Swapped times should be 0
    if after_metrics['swapped_times'] == 0:
        print("✅ Fix 3 PASSED: No swapped times detected")
    else:
        print("❌ Fix 3 FAILED: Still have swapped times")
        success = False
    
    # Check departure sources are being populated
    if any(after_metrics['departure_sources'].values()):
        print("✅ Departure sources properly tracked")
    else:
        print("⚠️  No departure sources recorded")
    
    print("\n" + "="*80)
    if success:
        print("🎉 ALL FIXES VALIDATED SUCCESSFULLY!")
    else:
        print("⚠️  Some fixes need attention")
    print("="*80)


async def main():
    """Main test runner."""
    try:
        await validate_fixes()
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())