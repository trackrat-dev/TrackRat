import { Stop } from '../types';
import { formatTime, getDelayMinutes } from '../utils/date';

interface StopCardProps {
  stop: Stop;
  isOrigin?: boolean;
  isDestination?: boolean;
}

/**
 * Get the best available time and its source label.
 * Priority: actual > updated/estimated > scheduled
 */
function getBestTime(
  scheduled?: string,
  updated?: string,
  actual?: string
): { time: string; label: 'actual' | 'updated' | 'scheduled' } | null {
  if (actual) return { time: actual, label: 'actual' };
  if (updated) return { time: updated, label: 'updated' };
  if (scheduled) return { time: scheduled, label: 'scheduled' };
  return null;
}

export function StopCard({ stop, isOrigin = false, isDestination = false }: StopCardProps) {
  const arrivalBest = getBestTime(stop.scheduled_arrival, stop.updated_arrival, stop.actual_arrival);
  const departureBest = getBestTime(stop.scheduled_departure, stop.updated_departure, stop.actual_departure);

  const arrivalDelay = getDelayMinutes(stop.scheduled_arrival, arrivalBest?.time);
  const departureDelay = getDelayMinutes(stop.scheduled_departure, departureBest?.time);

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
        {stop.scheduled_arrival && !isOrigin && (
          <div className="flex justify-between">
            <span className="text-text-muted">Arrival:</span>
            <span className="font-medium text-text-primary">
              {formatTime(stop.scheduled_arrival)}
              {arrivalBest && arrivalBest.label !== 'scheduled' && arrivalDelay !== 0 && (
                <span className={arrivalDelay > 0 ? 'text-warning ml-2' : 'text-success ml-2'}>
                  ({formatTime(arrivalBest.time)}{arrivalDelay > 0 ? ` +${arrivalDelay}m` : ''})
                </span>
              )}
            </span>
          </div>
        )}

        {stop.predicted_arrival && !isOrigin && !stop.actual_arrival && (
          <div className="flex justify-between">
            <span className="text-text-muted text-xs">Predicted:</span>
            <span className="text-xs text-accent">
              {formatTime(stop.predicted_arrival)}
            </span>
          </div>
        )}

        {stop.scheduled_departure && !isDestination && (
          <div className="flex justify-between">
            <span className="text-text-muted">Departure:</span>
            <span className="font-medium text-text-primary">
              {formatTime(stop.scheduled_departure)}
              {departureBest && departureBest.label !== 'scheduled' && departureDelay !== 0 && (
                <span className={departureDelay > 0 ? 'text-warning ml-2' : 'text-success ml-2'}>
                  ({formatTime(departureBest.time)}{departureDelay > 0 ? ` +${departureDelay}m` : ''})
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
