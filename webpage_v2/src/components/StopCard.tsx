import { Stop } from '../types';
import { formatTime, getDelayMinutes } from '../utils/date';

interface StopCardProps {
  stop: Stop;
}

export function StopCard({ stop }: StopCardProps) {
  const departureDelay = getDelayMinutes(
    stop.scheduled_departure,
    stop.actual_departure
  );
  const arrivalDelay = getDelayMinutes(
    stop.scheduled_arrival,
    stop.actual_arrival
  );

  return (
    <div className="bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl p-4">
      <div className="flex items-start justify-between mb-2">
        <div className="flex-1">
          <div className="font-semibold text-text-primary">{stop.station.name}</div>
          <div className="text-sm text-text-muted">{stop.station.code}</div>
        </div>
        {stop.track && (
          <div className="px-2 py-1 bg-accent/20 text-accent rounded text-sm font-semibold">
            Track {stop.track}
          </div>
        )}
      </div>

      <div className="space-y-1 text-sm">
        {stop.scheduled_arrival && (
          <div className="flex justify-between">
            <span className="text-text-muted">Arrival:</span>
            <span className="font-medium text-text-primary">
              {formatTime(stop.scheduled_arrival)}
              {stop.actual_arrival && arrivalDelay > 0 && (
                <span className="text-warning ml-2">
                  +{arrivalDelay}m
                </span>
              )}
            </span>
          </div>
        )}

        {stop.scheduled_departure && (
          <div className="flex justify-between">
            <span className="text-text-muted">Departure:</span>
            <span className="font-medium text-text-primary">
              {formatTime(stop.scheduled_departure)}
              {stop.actual_departure && departureDelay > 0 && (
                <span className="text-warning ml-2">
                  +{departureDelay}m
                </span>
              )}
            </span>
          </div>
        )}

        {stop.has_departed_station && (
          <div className="text-success text-xs mt-2">✓ Departed</div>
        )}
      </div>
    </div>
  );
}
