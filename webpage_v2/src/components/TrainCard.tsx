import { Train } from '../types';
import { formatTime, getDelayMinutes } from '../utils/date';
import { formatDelayText, getStatusBadgeClass } from '../utils/formatting';

interface TrainCardProps {
  train: Train;
  onClick: () => void;
}

export function TrainCard({ train, onClick }: TrainCardProps) {
  const delayMinutes = getDelayMinutes(
    train.departure.scheduled_time,
    train.departure.actual_time || undefined
  );

  const status = train.is_cancelled
    ? 'cancelled'
    : delayMinutes > 0
    ? 'delayed'
    : 'on time';

  return (
    <button
      onClick={onClick}
      className="w-full bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4 hover:bg-surface transition-all text-left"
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="text-lg font-semibold text-text-primary">
            Train {train.train_id}
          </div>
          <div className="text-sm text-text-muted">{train.line.name}</div>
        </div>
        <span className={getStatusBadgeClass(status)}>
          {train.is_cancelled ? 'Cancelled' : formatDelayText(delayMinutes)}
        </span>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="text-sm text-text-muted">Departure</div>
          <div className="font-medium text-text-primary">
            {formatTime(train.departure.scheduled_time)}
            {train.departure.actual_time && delayMinutes > 0 && (
              <span className="text-warning ml-2">
                ({formatTime(train.departure.actual_time)})
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div className="text-sm text-text-muted">Arrival</div>
          <div className="font-medium text-text-primary">
            {formatTime(train.arrival.scheduled_time)}
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
