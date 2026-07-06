import { Stop } from '../types';
import { formatTime, getDelayMinutes } from '../utils/date';
import { SubwayLineChips } from './SubwayLineChips';
import { TimeDisplay } from './TimeDisplay';

interface StopCardProps {
  stop: Stop;
  isOrigin?: boolean;
  isDestination?: boolean;
  currentLine?: string;
}

/**
 * Best available time. Priority: actual > updated/estimated > scheduled.
 */
function getBestTime(scheduled?: string, updated?: string, actual?: string): string | undefined {
  return actual || updated || scheduled;
}

export function StopCard({ stop, isOrigin = false, isDestination = false, currentLine }: StopCardProps) {
  const arrivalBest = getBestTime(stop.scheduled_arrival, stop.updated_arrival, stop.actual_arrival);
  const departureBest = getBestTime(stop.scheduled_departure, stop.updated_departure, stop.actual_departure);

  const arrivalDelay = getDelayMinutes(stop.scheduled_arrival, arrivalBest);
  const departureDelay = getDelayMinutes(stop.scheduled_departure, departureBest);

  return (
    <div className="bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4">
      <div className="flex items-start justify-between mb-2">
        <div className="flex-1">
          <div className="font-semibold text-text-primary flex items-center gap-1.5">
            {stop.station.name}
            <SubwayLineChips stationCode={stop.station.code} excludeLine={currentLine} />
          </div>
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
            <span>
              <TimeDisplay
                scheduledTime={stop.scheduled_arrival}
                liveTime={arrivalBest}
                delayMinutes={arrivalDelay}
              />
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
            <span>
              <TimeDisplay
                scheduledTime={stop.scheduled_departure}
                liveTime={departureBest}
                delayMinutes={departureDelay}
              />
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
