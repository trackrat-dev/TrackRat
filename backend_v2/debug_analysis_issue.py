#!/usr/bin/env python3
import asyncio
from sqlalchemy import select, and_, func
from trackrat.db.engine import get_engine
from trackrat.models import TrainJourney, JourneyStop, SegmentTransitTime
from datetime import datetime, timedelta

async def find_analysis_gap():
    from sqlalchemy.ext.asyncio import AsyncSession
    engine = get_engine()
    async with AsyncSession(engine) as session:
        # Find NJT journeys from the last 24 hours that have actual_departure but no segment data
        cutoff = datetime.now() - timedelta(hours=24)
        
        # Get journeys with actual_departure
        journeys_with_departure = await session.execute(
            select(TrainJourney.id, TrainJourney.train_id, TrainJourney.actual_departure)
            .where(
                and_(
                    TrainJourney.data_source == 'NJT',
                    TrainJourney.actual_departure.isnot(None),
                    TrainJourney.journey_date >= cutoff.date()
                )
            )
        )
        
        journeys = list(journeys_with_departure)
        print(f'Found {len(journeys)} NJT journeys with actual_departure in last 24h')
        
        # Check which have segment transit times
        for journey_id, train_id, actual_dep in journeys:
            segments = await session.scalar(
                select(func.count(SegmentTransitTime.id))
                .where(SegmentTransitTime.journey_id == journey_id)
            )
            
            stops_count = await session.scalar(
                select(func.count(JourneyStop.id))
                .where(JourneyStop.journey_id == journey_id)
            )
            
            status = "ANALYZED" if segments > 0 else "NOT ANALYZED"
            print(f'  {train_id}: {stops_count} stops, {segments} segments - {status}')
        
        # Count totals
        unanalyzed = 0
        for journey_id, train_id, actual_dep in journeys:
            segments = await session.scalar(
                select(func.count(SegmentTransitTime.id))
                .where(SegmentTransitTime.journey_id == journey_id)
            )
            if segments == 0:
                unanalyzed += 1
        
        print(f'\nSummary: {unanalyzed}/{len(journeys)} journeys not analyzed despite having actual_departure')

if __name__ == "__main__":
    asyncio.run(find_analysis_gap())