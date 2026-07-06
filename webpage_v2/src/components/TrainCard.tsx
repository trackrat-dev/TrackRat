import type { KeyboardEvent } from 'react';
import { Train } from '../types';
import { formatRelativeMinutes, getDelayMinutes, isToday } from '../utils/date';
import { formatDelayText } from '../utils/formatting';
import { StatusBadge } from './StatusBadge';
import { ShareButton } from './ShareButton';
import { TimeDisplay } from './TimeDisplay';
import { buildTrainShareData } from '../utils/share';

interface TrainCardProps {
  train: Train;
  onClick: () => void;
  from?: string;
  to?: string;
  departed?: boolean;
}

export function TrainCard({ train, onClick, from, to, departed = false }: TrainCardProps) {
  const bestDepartureTime = train.departure.actual_time || train.departure.updated_time || undefined;
  const delayMinutes = getDelayMinutes(train.departure.scheduled_time, bestDepartureTime);

  const bestArrivalTime = train.arrival.actual_time || train.arrival.updated_time || undefined;
  const arrivalDelayMinutes = getDelayMinutes(train.arrival.scheduled_time, bestArrivalTime);

  // "in N min" countdown, only for today's live journeys (not future-date searches).
  const countdown =
    !train.is_cancelled && !departed && isToday(train.journey_date)
      ? formatRelativeMinutes(bestDepartureTime || train.departure.scheduled_time)
      : null;

  // Detect boarding: train is at our departure station and hasn't departed yet
  const isBoarding =
    !departed &&
    !train.is_cancelled &&
    from &&
    train.train_position?.at_station_code === from;

  const status = train.is_cancelled
    ? 'cancelled'
    : departed
    ? 'departed'
    : isBoarding
    ? 'boarding'
    : delayMinutes > 0
    ? 'delayed'
    : 'on time';

  const cardClasses = [
    'w-full border rounded-2xl p-4 text-left transition-all',
    departed
      ? 'bg-surface/40 backdrop-blur-xl border-text-muted/10 opacity-60'
      : isBoarding
      ? 'bg-accent/10 backdrop-blur-xl border-accent/40'
      : 'bg-surface/70 backdrop-blur-xl border-text-muted/20 hover:bg-surface',
  ].join(' ');

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onClick();
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      className={cardClasses}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <div className={`text-lg font-semibold text-text-primary ${train.is_cancelled ? 'line-through' : ''}`}>
            Train {train.observation_type === 'SCHEDULED' ? 'TBD' : train.train_id}
          </div>
          <div className="text-sm text-text-muted">{train.line.name}</div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <div className="flex items-center gap-2">
            <ShareButton
              shareData={buildTrainShareData({
                trainId: train.train_id,
                origin: train.departure.name,
                destination: train.destination,
                from: from,
                to: to,
                journeyDate: train.journey_date,
                dataSource: train.data_source,
              })}
              className="scale-90"
            />
            <StatusBadge
              status={status}
              label={
                status === 'cancelled' || status === 'departed' || status === 'boarding'
                  ? undefined
                  : formatDelayText(delayMinutes)
              }
            />
          </div>
          {countdown && (
            <span className="text-sm font-semibold text-accent">{countdown}</span>
          )}
        </div>
      </div>

      {isBoarding && train.departure.track && (
        <div className="mb-3 text-sm font-semibold text-accent">
          Boarding on Track {train.departure.track}
        </div>
      )}

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="text-sm text-text-muted">Departure</div>
          <div>
            <TimeDisplay
              scheduledTime={train.departure.scheduled_time}
              liveTime={bestDepartureTime}
              delayMinutes={delayMinutes}
            />
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div className="text-sm text-text-muted">Arrival</div>
          <div>
            <TimeDisplay
              scheduledTime={train.arrival.scheduled_time}
              liveTime={bestArrivalTime}
              delayMinutes={arrivalDelayMinutes}
            />
          </div>
        </div>

        <div className="flex items-center justify-between text-sm">
          <div className="text-text-muted">{train.destination}</div>
          <div className="text-text-muted">{train.data_source}</div>
        </div>
      </div>
    </div>
  );
}
