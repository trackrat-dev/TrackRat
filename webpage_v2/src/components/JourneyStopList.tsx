import { ReactNode, useState } from 'react';
import { Stop } from '../types';

interface JourneyStopListProps {
  stops: Stop[];
  /** Boarding and alighting indices into `stops`; null shows every stop. */
  journeyRange: [number, number] | null;
  renderStop: (stop: Stop) => ReactNode;
}

const toggleClass =
  'w-full p-3 bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl text-center text-text-muted text-sm hover:text-text-primary transition-colors';

/**
 * A train's stops trimmed to the rider's journey, with "previous" / "later"
 * toggles that reveal the trimmed ends (issue #1840).
 */
export function JourneyStopList({ stops, journeyRange, renderStop }: JourneyStopListProps) {
  const [showPrevious, setShowPrevious] = useState(false);
  const [showLater, setShowLater] = useState(false);
  const [start, end] = journeyRange ?? [0, stops.length - 1];
  const visibleStops = stops.slice(showPrevious ? 0 : start, showLater ? stops.length : end + 1);

  return (
    <>
      {start > 0 && (
        <button type="button" className={`mb-3 ${toggleClass}`} onClick={() => setShowPrevious(!showPrevious)}>
          {showPrevious ? 'Hide previous stops' : 'Train has previous stops'}
        </button>
      )}
      <div className="space-y-3">{visibleStops.map(renderStop)}</div>
      {end < stops.length - 1 && (
        <button type="button" className={`mt-3 ${toggleClass}`} onClick={() => setShowLater(!showLater)}>
          {showLater ? 'Hide later stops' : 'Train has later stops'}
        </button>
      )}
    </>
  );
}
