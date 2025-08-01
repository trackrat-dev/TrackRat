#!/usr/bin/env python3
import asyncio
from sqlalchemy import select, and_, func
from trackrat.db.engine import get_engine
from trackrat.models import TrainJourney, JourneyStop
from datetime import datetime

async def investigate_stop_mismatch():
    from sqlalchemy.ext.asyncio import AsyncSession
    engine = get_engine()
    async with AsyncSession(engine) as session:
        # Find journeys where stops_count != actual stops
        journeys_with_counts = await session.execute(
            select(
                TrainJourney.train_id,
                TrainJourney.stops_count,
                func.count(JourneyStop.id).label('actual_stops')
            )
            .outerjoin(JourneyStop, JourneyStop.journey_id == TrainJourney.id)
            .where(
                and_(
                    TrainJourney.data_source == 'NJT',
                    TrainJourney.journey_date >= datetime.now().date()
                )
            )
            .group_by(TrainJourney.id, TrainJourney.train_id, TrainJourney.stops_count)
            .order_by(TrainJourney.train_id)
        )
        
        print('Train ID | Reported Stops | Actual Stops | Match')
        print('-' * 50)
        
        mismatches = 0
        total = 0
        
        for train_id, reported_stops, actual_stops in journeys_with_counts:
            total += 1
            match = 'YES' if reported_stops == actual_stops else 'NO'
            if reported_stops != actual_stops:
                mismatches += 1
            print(f'{train_id:8} | {reported_stops or 0:13} | {actual_stops:12} | {match}')
        
        print(f'\nSummary: {mismatches}/{total} trains have mismatched stop counts')

if __name__ == "__main__":
    asyncio.run(investigate_stop_mismatch())