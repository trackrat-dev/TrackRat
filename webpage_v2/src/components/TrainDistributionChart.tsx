import { Link } from 'react-router-dom';
import { TrainDelaySummary } from '../types';

const DELAY_CATEGORIES = [
  { key: 'on_time', label: 'On time', color: 'bg-success', textColor: 'text-success' },
  { key: 'slight_delay', label: '5-15m', color: 'bg-warning/70', textColor: 'text-warning' },
  { key: 'delayed', label: '15m+', color: 'bg-warning', textColor: 'text-warning' },
  { key: 'cancelled', label: 'Cancelled', color: 'bg-text-muted', textColor: 'text-text-muted' },
] as const;

const HEADWAY_CATEGORIES = [
  { key: '0-5', label: '0-5m', color: 'bg-success', textColor: 'text-success' },
  { key: '5-10', label: '5-10m', color: 'bg-success/70', textColor: 'text-success' },
  { key: '10-20', label: '10-20m', color: 'bg-warning/70', textColor: 'text-warning' },
  { key: '20+', label: '20m+', color: 'bg-error/70', textColor: 'text-error' },
] as const;

const MAX_PILLS = 5;

// Systems that use headway-based frequency charts
const FREQUENCY_SYSTEMS = new Set(['PATH', 'SUBWAY', 'PATCO', 'BART', 'MBTA']);

interface Props {
  trainsByCategory: Record<string, TrainDelaySummary[]> | null;
  trainsByHeadway: Record<string, TrainDelaySummary[]> | null;
  dataSource?: string;
  from?: string;
  to?: string;
}

export function TrainDistributionChart({ trainsByCategory, trainsByHeadway, dataSource, from, to }: Props) {
  const useFrequency = dataSource && FREQUENCY_SYSTEMS.has(dataSource) && trainsByHeadway;
  const categories = useFrequency ? HEADWAY_CATEGORIES : DELAY_CATEGORIES;
  const data = useFrequency ? trainsByHeadway! : trainsByCategory;

  if (!data) return null;

  const totalTrains = Object.values(data).reduce((sum, trains) => sum + trains.length, 0);
  if (totalTrains === 0) return null;

  return (
    <div className="mt-3">
      {/* Bar chart */}
      <div className="flex h-3 rounded-full overflow-hidden mb-3">
        {categories.map(cat => {
          const trains = data[cat.key] || [];
          const pct = (trains.length / totalTrains) * 100;
          if (pct === 0) return null;
          return (
            <div
              key={cat.key}
              className={cat.color}
              style={{ width: `${pct}%` }}
              title={`${cat.label}: ${trains.length} trains (${Math.round(pct)}%)`}
            />
          );
        })}
      </div>

      {/* Columns with train pills */}
      <div className="grid grid-cols-4 gap-2">
        {categories.map(cat => {
          const trains = data[cat.key] || [];
          if (trains.length === 0) {
            return (
              <div key={cat.key} className="text-center">
                <div className="text-[10px] text-text-muted mb-1">{cat.label}</div>
                <div className="text-xs text-text-muted">—</div>
              </div>
            );
          }
          const overflow = trains.length - MAX_PILLS;
          return (
            <div key={cat.key} className="text-center">
              <div className="text-[10px] text-text-muted mb-1">
                {cat.label} ({trains.length})
              </div>
              <div className="flex flex-col gap-1 items-center">
                {trains.slice(0, MAX_PILLS).map(train => (
                  <TrainPill
                    key={train.train_id}
                    train={train}
                    textColor={cat.textColor}
                    from={from}
                    to={to}
                  />
                ))}
                {overflow > 0 && (
                  <span className="text-[10px] text-text-muted">+{overflow} more</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TrainPill({ train, textColor, from, to }: {
  train: TrainDelaySummary;
  textColor: string;
  from?: string;
  to?: string;
}) {
  const label = formatTrainLabel(train.train_id);
  const href = from && to
    ? `/train/${encodeURIComponent(train.train_id)}/${from}/${to}`
    : `/train/${encodeURIComponent(train.train_id)}`;

  return (
    <Link
      to={href}
      className={`text-[10px] font-medium ${textColor} bg-surface/80 border border-text-muted/15 rounded-full px-2 py-0.5 hover:bg-surface transition-colors truncate max-w-full`}
      title={`${train.train_id} — ${train.delay_minutes.toFixed(0)}m delay`}
    >
      {label}
    </Link>
  );
}

function formatTrainLabel(trainId: string): string {
  // Truncate long IDs (subway, PATH, etc.) to last meaningful segment
  if (trainId.length > 10) {
    const parts = trainId.split('_');
    return parts.length > 1 ? parts[parts.length - 1].slice(0, 8) : trainId.slice(0, 8);
  }
  return trainId;
}
