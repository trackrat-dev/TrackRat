import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Train, TripOption } from '../types';
import { apiService } from '../services/api';
import { formatTime, getDelayMinutes } from '../utils/date';
import { buildTrainUrl } from '../utils/routes';

interface Props {
  from: string;
  to: string;
}

const MAX_TRAINS = 3;

export function UpcomingTrains({ from, to }: Props) {
  const [trains, setTrains] = useState<Train[]>([]);

  useEffect(() => {
    apiService.searchTrips(from, to, 10)
      .then(response => {
        const direct = response.trips
          .filter(t => t.is_direct)
          .map(tripToTrain)
          .filter(t => !t.is_cancelled && !hasTrainDeparted(t))
          .slice(0, MAX_TRAINS);
        setTrains(direct);
      })
      .catch(() => {}); // Fail silently
  }, [from, to]);

  if (trains.length === 0) return null;

  return (
    <div className="mb-4 bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4">
      <h4 className="text-sm font-semibold text-text-primary mb-3">Upcoming Trains</h4>
      <div className="space-y-2">
        {trains.map(train => {
          const delayMins = getDelayMinutes(
            train.departure.scheduled_time,
            train.departure.updated_time || train.departure.actual_time || undefined
          );
          return (
            <Link
              key={train.train_id}
              to={buildTrainUrl({
                trainId: train.train_id,
                from,
                to,
                date: train.journey_date,
                dataSource: train.data_source,
              })}
              className="flex items-center gap-3 p-2 rounded-lg hover:bg-surface/50 transition-colors"
            >
              {/* Line color dot */}
              <div
                className="w-2 h-8 rounded-full flex-shrink-0"
                style={{ backgroundColor: train.line.color || '#CC5500' }}
              />
              {/* Train info */}
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-text-primary truncate">
                  {train.line.name}
                </div>
                {train.departure.track && (
                  <div className="text-[10px] text-text-muted">Track {train.departure.track}</div>
                )}
              </div>
              {/* Time + delay */}
              <div className="text-right flex-shrink-0">
                <div className="text-sm font-medium text-text-primary">
                  {formatTime(train.departure.scheduled_time)}
                </div>
                {delayMins > 0 && (
                  <div className="text-[10px] text-warning font-medium">{delayMins}m late</div>
                )}
              </div>
            </Link>
          );
        })}
      </div>
      <Link
        to={`/trains/${from}/${to}`}
        className="block mt-3 text-xs text-accent hover:text-accent/80 font-medium text-center"
      >
        View All Departures →
      </Link>
    </div>
  );
}

function tripToTrain(trip: TripOption): Train {
  const leg = trip.legs[0];
  return {
    train_id: leg.train_id,
    journey_date: leg.journey_date,
    line: leg.line,
    destination: leg.destination,
    departure: leg.boarding,
    arrival: leg.alighting,
    train_position: leg.train_position,
    data_freshness: { last_updated: '', age_seconds: 0, update_count: 0, collection_method: null },
    data_source: leg.data_source,
    observation_type: (leg.observation_type as 'OBSERVED' | 'SCHEDULED') || 'OBSERVED',
    is_cancelled: leg.is_cancelled,
  };
}

function hasTrainDeparted(train: Train): boolean {
  const timeStr = train.departure.actual_time || train.departure.updated_time || train.departure.scheduled_time;
  if (!timeStr) return false;
  return new Date(timeStr).getTime() + 60000 < Date.now();
}
