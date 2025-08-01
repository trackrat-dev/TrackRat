#!/usr/bin/env python3
import asyncio
from sqlalchemy import select, and_
from trackrat.db.engine import get_engine
from trackrat.models import TrainJourney, JourneyStop
from datetime import datetime

async def check_specific_problematic_train():
    from sqlalchemy.ext.asyncio import AsyncSession
    engine = get_engine()
    async with AsyncSession(engine) as session:
        # Check a train that has stops_count=0 but 1 actual stop
        journey = await session.scalar(
            select(TrainJourney)
            .where(
                and_(
                    TrainJourney.data_source == 'NJT',
                    TrainJourney.train_id == '5401',  # Has stops_count=0 but 1 actual stop
                    TrainJourney.journey_date == datetime.now().date()
                )
            )
        )
        
        if journey:
            print(f'Train {journey.train_id}:')
            print(f'  Journey date: {journey.journey_date}')
            print(f'  Actual departure: {journey.actual_departure}')
            print(f'  Stops count (field): {journey.stops_count}')
            print(f'  Is completed: {journey.is_completed}')
            print(f'  Is cancelled: {journey.is_cancelled}')
            print(f'  Has complete journey: {journey.has_complete_journey}')
            print(f'  Update count: {journey.update_count}')
            print(f'  Last updated: {journey.last_updated_at}')
            
            # Check its stops
            stops = await session.execute(
                select(JourneyStop)
                .where(JourneyStop.journey_id == journey.id)
                .order_by(JourneyStop.stop_sequence)
            )
            stops_list = list(stops.scalars().all())
            print(f'  Actual stops in DB: {len(stops_list)}')
            
            if stops_list:
                print('  All stops:')
                for stop in stops_list:
                    departed_str = 'YES' if stop.has_departed_station else 'NO'
                    actual_dep = stop.actual_departure.strftime('%H:%M') if stop.actual_departure else 'None'
                    sched_dep = stop.scheduled_departure.strftime('%H:%M') if stop.scheduled_departure else 'None'
                    print(f'    {stop.station_code} (seq={stop.stop_sequence}): departed={departed_str}, actual={actual_dep}, sched={sched_dep}')
        else:
            print('Train not found')

if __name__ == "__main__":
    asyncio.run(check_specific_problematic_train())