import { formatTime } from '../utils/date';

interface TimeDisplayProps {
  scheduledTime: string;
  liveTime?: string;
  delayMinutes: number;
}

/**
 * Departure/arrival time that leads with the live (delayed or early) time and
 * strikes through the scheduled time when they differ. When the train is on
 * schedule (delay 0) or no live time is available, only the scheduled time is
 * shown — identical to the pre-flip rendering. Late times are colored with
 * `text-warning`, early times with `text-success`.
 */
export function TimeDisplay({ scheduledTime, liveTime, delayMinutes }: TimeDisplayProps) {
  if (liveTime && delayMinutes !== 0) {
    return (
      <>
        <span className={`font-medium ${delayMinutes > 0 ? 'text-warning' : 'text-success'}`}>
          {formatTime(liveTime)}
        </span>
        <span className="line-through text-text-muted text-sm ml-2">
          {formatTime(scheduledTime)}
        </span>
      </>
    );
  }
  return <span className="font-medium text-text-primary">{formatTime(scheduledTime)}</span>;
}
