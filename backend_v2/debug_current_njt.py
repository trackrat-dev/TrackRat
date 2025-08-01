#!/usr/bin/env python3
import asyncio
from sqlalchemy import select, and_
from trackrat.db.engine import get_engine
from trackrat.models import TrainJourney, JourneyStop
from datetime import datetime, timedelta

async def check_current_njt_collection():
    from sqlalchemy.ext.asyncio import AsyncSession
    engine = get_engine()
    async with AsyncSession(engine) as session:
        now = datetime.now()
        
        # Check recent NJT trains from today that are active
        recent_trains = await session.execute(
            select(
                TrainJourney.train_id,
                TrainJourney.actual_departure,
                TrainJourney.has_complete_journey,
                TrainJourney.stops_count,
                TrainJourney.last_updated_at,
                TrainJourney.is_completed,
                TrainJourney.is_cancelled
            )
            .where(
                and_(
                    TrainJourney.data_source == 'NJT',
                    TrainJourney.journey_date == now.date(),
                    TrainJourney.last_updated_at >= now - timedelta(hours=2)  # Updated in last 2 hours
                )
            )
            .order_by(TrainJourney.last_updated_at.desc())
            .limit(10)
        )
        
        print(f'Recent NJT trains updated in last 2 hours ({now.strftime("%H:%M")}):')
        print('Train ID | Actual Dep | Complete | Stops | Last Updated | Status')
        print('-' * 70)
        
        for train_id, actual_dep, complete, stops, last_updated, completed, cancelled in recent_trains:
            actual_str = actual_dep.strftime('%H:%M') if actual_dep else 'None'
            complete_str = 'YES' if complete else 'NO'
            status = []
            if completed: status.append('COMP')
            if cancelled: status.append('CANC')
            status_str = ','.join(status) if status else 'ACTIVE'
            last_updated_str = last_updated.strftime('%H:%M') if last_updated else 'None'
            
            print(f'{train_id:8} | {actual_str:10} | {complete_str:8} | {stops or 0:5} | {last_updated_str:12} | {status_str}')
        
        # Check if any of these should have gotten actual_departure by now
        print('\nChecking if any trains should have actual_departure by the 30-minute rule...')
        
        for train_id, actual_dep, complete, stops, last_updated, completed, cancelled in recent_trains:
            if actual_dep is None and complete:
                # Check first stop's scheduled departure
                first_stop = await session.scalar(
                    select(JourneyStop)
                    .where(
                        and_(
                            JourneyStop.journey_id == TrainJourney.id,
                            TrainJourney.train_id == train_id,
                            TrainJourney.data_source == 'NJT'
                        )
                    )
                    .order_by(JourneyStop.stop_sequence)
                    .limit(1)
                )
                
                if first_stop and first_stop.scheduled_departure:
                    time_since_scheduled = now - first_stop.scheduled_departure.replace(tzinfo=None)
                    minutes_since = time_since_scheduled.total_seconds() / 60
                    
                    if minutes_since > 30:
                        print(f'  {train_id}: Should have actual_departure (30min rule: {minutes_since:.0f} min past scheduled)')
                    else:
                        print(f'  {train_id}: Within 30min window ({minutes_since:.0f} min past scheduled)')

if __name__ == "__main__":
    asyncio.run(check_current_njt_collection())