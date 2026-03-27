import { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import { TrainHistoryStatistics } from '../types';

interface HistoricalPerformanceProps {
  trainId: string;
  fromStation?: string;
  toStation?: string;
}

export function HistoricalPerformance({ trainId, fromStation, toStation }: HistoricalPerformanceProps) {
  const [stats, setStats] = useState<TrainHistoryStatistics | null>(null);
  const [trackDistribution, setTrackDistribution] = useState<Record<string, number>>({});
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    apiService.getTrainHistory(trainId, 365, fromStation, toStation)
      .then(res => {
        if (!res || res.statistics.total_journeys < 5) return;
        setStats(res.statistics);

        // Calculate track distribution from journeys at origin
        if (fromStation && res.journeys.length > 0) {
          const trackCounts: Record<string, number> = {};
          let total = 0;
          for (const j of res.journeys) {
            const track = j.track_assignments[fromStation];
            if (track) {
              trackCounts[track] = (trackCounts[track] || 0) + 1;
              total++;
            }
          }
          if (total > 0) {
            const dist: Record<string, number> = {};
            for (const [track, count] of Object.entries(trackCounts)) {
              dist[track] = Math.round((count / total) * 100);
            }
            setTrackDistribution(dist);
          }
        }
      })
      .catch(() => {});
  }, [trainId, fromStation, toStation]);

  if (!stats) return null;

  const onTimePct = Math.round(stats.on_time_percentage);
  const avgDelay = stats.average_delay_minutes.toFixed(1);
  const cancellationRate = stats.cancellation_rate.toFixed(1);
  const sortedTracks = Object.entries(trackDistribution).sort((a, b) => b[1] - a[1]);

  return (
    <div className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-4 flex items-center justify-between text-left"
      >
        <div>
          <h4 className="text-sm font-semibold text-text-primary">Historical Performance</h4>
          <p className="text-xs text-text-muted mt-0.5">
            Based on {stats.total_journeys} trips over the past year
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-lg font-bold ${onTimePct >= 80 ? 'text-success' : onTimePct >= 60 ? 'text-warning' : 'text-error'}`}>
            {onTimePct}%
          </span>
          <span className="text-text-muted text-xs">{expanded ? '▲' : '▼'}</span>
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-text-muted/10 pt-3 space-y-3">
          {/* Key metrics */}
          <div className="grid grid-cols-3 gap-3">
            <div className="text-center">
              <div className={`text-lg font-bold ${onTimePct >= 80 ? 'text-success' : onTimePct >= 60 ? 'text-warning' : 'text-error'}`}>
                {onTimePct}%
              </div>
              <div className="text-xs text-text-muted">On time</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-text-primary">{avgDelay}m</div>
              <div className="text-xs text-text-muted">Avg delay</div>
            </div>
            <div className="text-center">
              <div className={`text-lg font-bold ${Number(cancellationRate) > 5 ? 'text-error' : 'text-text-primary'}`}>
                {cancellationRate}%
              </div>
              <div className="text-xs text-text-muted">Cancelled</div>
            </div>
          </div>

          {/* Track distribution */}
          {sortedTracks.length > 0 && (
            <div>
              <div className="text-xs font-medium text-text-muted mb-2">Track distribution</div>
              <div className="flex h-4 rounded-full overflow-hidden">
                {sortedTracks.map(([track, pct]) => (
                  <div
                    key={track}
                    className="bg-accent/70 border-r border-background/50 last:border-r-0 flex items-center justify-center"
                    style={{ width: `${pct}%`, minWidth: pct > 5 ? undefined : '2px' }}
                    title={`Track ${track}: ${pct}%`}
                  >
                    {pct > 12 && <span className="text-[10px] text-white font-medium">{track}</span>}
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap gap-2 mt-1.5">
                {sortedTracks.map(([track, pct]) => (
                  <span key={track} className="text-[10px] text-text-muted">
                    Tk {track}: {pct}%
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
