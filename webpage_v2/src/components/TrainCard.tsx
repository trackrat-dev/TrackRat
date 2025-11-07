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
    train.departure.actual_time
  );

  const status = train.is_cancelled
    ? 'cancelled'
    : delayMinutes > 0
    ? 'delayed'
    : 'on time';

  return (
    <button
      onClick={onClick}
      className="w-full bg-surface/70 backdrop-blur-xl border border-white/10 rounded-2xl p-4 hover:bg-white/5 transition-all text-left"
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="text-lg font-semibold text-white">
            Train {train.train_id}
          </div>
          <div className="text-sm text-white/60">{train.line.name}</div>
        </div>
        <span className={getStatusBadgeClass(status)}>
          {train.is_cancelled ? 'Cancelled' : formatDelayText(delayMinutes)}
        </span>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="text-sm text-white/60">Departure</div>
          <div className="font-medium">
            {formatTime(train.departure.scheduled_time)}
            {train.departure.actual_time && delayMinutes > 0 && (
              <span className="text-warning ml-2">
                ({formatTime(train.departure.actual_time)})
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div className="text-sm text-white/60">Arrival</div>
          <div className="font-medium">
            {formatTime(train.arrival.scheduled_time)}
          </div>
        </div>

        <div className="flex items-center justify-between text-sm">
          <div className="text-white/60">{train.destination}</div>
          <div className="text-white/60">{train.data_source}</div>
        </div>
      </div>
    </button>
  );
}
