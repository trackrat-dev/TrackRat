import { Train } from '../types';
import { formatTime, getDelayMinutes } from '../utils/date';
import { formatDelayText, getStatusBadgeClass } from '../utils/formatting';
import { ShareButton } from './ShareButton';
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
    : train.observation_type === 'SCHEDULED'
    ? 'scheduled'
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

  return (
    <button onClick={onClick} className={cardClasses}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <div className={`text-lg font-semibold text-text-primary ${train.is_cancelled ? 'line-through' : ''}`}>
            Train {train.train_id}
          </div>
          <div className="text-sm text-text-muted">{train.line.name}</div>
        </div>
        <div className="flex items-center gap-2">
          <div onClick={(e) => e.stopPropagation()}>
            <ShareButton
              shareData={buildTrainShareData({
                trainId: train.train_id,
                origin: train.departure.name,
                destination: train.destination,
                from: from,
                to: to,
              })}
              className="scale-90"
            />
          </div>
          <span className={getStatusBadgeClass(status)}>
            {status === 'cancelled'
              ? 'Cancelled'
              : status === 'departed'
              ? 'Departed'
              : status === 'boarding'
              ? 'Boarding'
              : status === 'scheduled'
              ? 'Scheduled'
              : formatDelayText(delayMinutes)}
          </span>
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
          <div className="font-medium text-text-primary">
            {formatTime(train.departure.scheduled_time)}
            {bestDepartureTime && delayMinutes > 0 && (
              <span className="text-warning ml-2">
                ({formatTime(bestDepartureTime)})
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div className="text-sm text-text-muted">Arrival</div>
          <div className="font-medium text-text-primary">
            {formatTime(train.arrival.scheduled_time)}
            {bestArrivalTime && arrivalDelayMinutes > 0 && (
              <span className="text-warning ml-2">
                ({formatTime(bestArrivalTime)})
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between text-sm">
          <div className="text-text-muted">{train.destination}</div>
          <div className="text-text-muted">{train.data_source}</div>
        </div>
      </div>
    </button>
  );
}
