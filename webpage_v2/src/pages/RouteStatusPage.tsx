import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { RouteHistoryResponse, OperationsSummaryResponse } from '../types';
import { apiService } from '../services/api';
import { getStationByCode } from '../data/stations';
import { Skeleton } from '../components/Skeleton';
import { ErrorMessage } from '../components/ErrorMessage';
import { ServiceAlertBanner } from '../components/ServiceAlertBanner';
import { UpcomingTrains } from '../components/UpcomingTrains';

type Period = '1h' | '6h' | '24h' | '7d' | '30d' | '90d';

const PERIODS: { value: Period; label: string }[] = [
  { value: '1h', label: '1h' },
  { value: '6h', label: '6h' },
  { value: '24h', label: '24h' },
  { value: '7d', label: '7d' },
  { value: '30d', label: '30d' },
  { value: '90d', label: '90d' },
];

function periodToApiParams(period: Period): { days?: number; hours?: number } {
  switch (period) {
    case '1h': return { hours: 1 };
    case '6h': return { hours: 6 };
    case '24h': return { hours: 24 };
    case '7d': return { days: 7 };
    case '30d': return { days: 30 };
    case '90d': return { days: 90 };
  }
}

function periodLabel(period: Period): string {
  const p = periodToApiParams(period);
  if (p.hours) return `${p.hours} hour${p.hours > 1 ? 's' : ''}`;
  return `${p.days} days`;
}

export function RouteStatusPage() {
  const { from, to } = useParams<{ from: string; to: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [history, setHistory] = useState<RouteHistoryResponse | null>(null);
  const [summary, setSummary] = useState<OperationsSummaryResponse | null>(null);
  const [period, setPeriod] = useState<Period>('24h');
  // initialLoading: page has never had data (shows skeleton once).
  // refreshing: a period change / reload is in flight while data stays mounted.
  const [initialLoading, setInitialLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fromStation = from ? getStationByCode(from) : null;
  const toStation = to ? getStationByCode(to) : null;
  const dataSource = searchParams.get('data_source') || fromStation?.system || toStation?.system || 'NJT';

  const loadData = useCallback(() => {
    if (!from || !to) return;

    setRefreshing(true);
    setError(null);

    const { days, hours } = periodToApiParams(period);
    Promise.all([
      apiService.getRouteHistory(from, to, dataSource, days, hours),
      apiService.getRouteSummary(from, to),
    ])
      .then(([historyRes, summaryRes]) => {
        setHistory(historyRes);
        setSummary(summaryRes);
      })
      .catch(err => {
        setError(err instanceof Error ? err.message : 'Failed to load route status');
      })
      .finally(() => {
        setInitialLoading(false);
        setRefreshing(false);
      });
  }, [from, to, period, dataSource]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (!from || !to || !fromStation || !toStation) {
    return <ErrorMessage message="Invalid route" onRetry={() => navigate('/departures')} />;
  }

  const stats = history?.aggregate_stats;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <button
          onClick={() => navigate(`/trains/${from}/${to}`)}
          className="text-accent hover:text-accent/80 mb-4 flex items-center gap-2 font-semibold"
        >
          ← Back to departures
        </button>
        <h2 className="text-2xl font-bold text-text-primary text-center">
          Route Status
        </h2>
        <p className="text-sm text-text-muted text-center mt-1">
          {fromStation.name} → {toStation.name}
        </p>
        <p className="text-xs text-text-muted text-center mt-1">
          {dataSource} route context
        </p>
      </div>

      {/* Service alerts */}
      <ServiceAlertBanner dataSource={dataSource} />

      {/* Operations summary */}
      {summary && (
        <div className="mb-4 bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4">
          <div className="text-sm font-medium text-text-primary mb-1">{summary.headline}</div>
          <p className="text-xs text-text-muted whitespace-pre-line">{summary.body}</p>
        </div>
      )}

      {/* Upcoming trains */}
      <UpcomingTrains from={from} to={to} />

      {/* Period selector */}
      <div className="flex items-center gap-2 mb-4">
        <div className="flex-1 flex gap-1.5">
          {PERIODS.map(p => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={`flex-1 py-2 rounded-xl text-xs font-semibold transition-colors ${
                period === p.value
                  ? 'bg-accent text-white'
                  : 'bg-surface/50 border border-text-muted/20 text-text-secondary hover:bg-surface'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        {/* Reserved slot keeps the button row width stable whether or not the spinner shows */}
        <div className="w-4 flex items-center justify-center" role="status" aria-label={refreshing ? 'Refreshing route status' : undefined}>
          {refreshing && !initialLoading && (
            <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" aria-hidden="true" />
          )}
        </div>
      </div>

      {/* Refresh error: keep prior stats mounted, surface the failure inline */}
      {error && stats && !initialLoading && (
        <div className="mb-4 text-center text-xs text-error">⚠️ {error} — showing last loaded data</div>
      )}

      {initialLoading ? (
        <RouteStatsSkeleton />
      ) : error && !stats ? (
        <ErrorMessage message={error} onRetry={loadData} />
      ) : stats ? (
        <div className={`space-y-4 transition-opacity ${refreshing ? 'opacity-60 pointer-events-none' : ''}`}>
          {/* Key metrics */}
          <div className="grid grid-cols-3 gap-3">
            <MetricCard
              label={stats.on_time_source === 'departure' ? 'Dep on time' : 'On time'}
              value={stats.on_time_percentage != null ? `${Math.round(stats.on_time_percentage)}%` : 'N/A'}
              color={stats.on_time_percentage != null && stats.on_time_percentage >= 80 ? 'success' : stats.on_time_percentage != null && stats.on_time_percentage >= 60 ? 'warning' : 'error'}
            />
            <MetricCard
              label="Avg delay"
              value={stats.average_delay_minutes != null ? `${stats.average_delay_minutes.toFixed(1)}m` : 'N/A'}
              color="text-primary"
            />
            <MetricCard
              label="Cancelled"
              value={`${stats.cancellation_rate.toFixed(1)}%`}
              color={stats.cancellation_rate > 5 ? 'error' : 'text-primary'}
            />
          </div>

          {/* Delay breakdown */}
          {stats.delay_breakdown && (
            <div className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4">
              <h4 className="text-sm font-semibold text-text-primary mb-3">Delay Breakdown</h4>
              <div className="flex h-4 rounded-full overflow-hidden mb-2">
                <div className="bg-success" style={{ width: `${stats.delay_breakdown.on_time}%` }} />
                <div className="bg-warning/70" style={{ width: `${stats.delay_breakdown.slight}%` }} />
                <div className="bg-warning" style={{ width: `${stats.delay_breakdown.significant}%` }} />
                <div className="bg-error" style={{ width: `${stats.delay_breakdown.major}%` }} />
              </div>
              <div className="grid grid-cols-4 gap-1 text-center">
                <div className="text-[10px] text-text-muted">On time<br />{stats.delay_breakdown.on_time.toFixed(0)}%</div>
                <div className="text-[10px] text-text-muted">5-15m<br />{stats.delay_breakdown.slight.toFixed(0)}%</div>
                <div className="text-[10px] text-text-muted">15-30m<br />{stats.delay_breakdown.significant.toFixed(0)}%</div>
                <div className="text-[10px] text-text-muted">30m+<br />{stats.delay_breakdown.major.toFixed(0)}%</div>
              </div>
            </div>
          )}

          {/* Track usage at origin */}
          {Object.keys(stats.track_usage_at_origin).length > 0 && (
            <div className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4">
              <h4 className="text-sm font-semibold text-text-primary mb-3">Track Usage at {fromStation.name}</h4>
              <div className="flex h-4 rounded-full overflow-hidden mb-2">
                {Object.entries(stats.track_usage_at_origin)
                  .sort((a, b) => b[1] - a[1])
                  .map(([track, pct]) => (
                    <div
                      key={track}
                      className="bg-accent/70 border-r border-background/50 last:border-r-0 flex items-center justify-center"
                      style={{ width: `${pct}%`, minWidth: pct > 3 ? undefined : '2px' }}
                      title={`Track ${track}: ${pct.toFixed(0)}%`}
                    >
                      {pct > 10 && <span className="text-[10px] text-white font-medium">{track}</span>}
                    </div>
                  ))}
              </div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(stats.track_usage_at_origin)
                  .sort((a, b) => b[1] - a[1])
                  .map(([track, pct]) => (
                    <span key={track} className="text-[10px] text-text-muted">
                      Tk {track}: {pct.toFixed(0)}%
                    </span>
                  ))}
              </div>
            </div>
          )}

          {/* Data info */}
          <div className="text-xs text-text-muted text-center mt-2">
            {history?.route.total_trains} trains over {periodLabel(period)}
          </div>
        </div>
      ) : (
        <div className="text-center py-12 text-text-muted">
          No historical data available for this route
        </div>
      )}
    </div>
  );
}

/** Layout-matched placeholder for the metrics area (3 metric cards + delay breakdown). */
function RouteStatsSkeleton() {
  return (
    <div className="space-y-4" role="status" aria-label="Loading route status" aria-busy="true">
      <div className="grid grid-cols-3 gap-3">
        {[0, 1, 2].map(i => (
          <div key={i} className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-xl p-3 text-center space-y-2">
            <Skeleton className="h-6 w-12 mx-auto" />
            <Skeleton className="h-3 w-16 mx-auto" />
          </div>
        ))}
      </div>
      <div className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4 space-y-3">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-4 w-full rounded-full" />
        <div className="grid grid-cols-4 gap-1">
          {[0, 1, 2, 3].map(i => (
            <Skeleton key={i} className="h-6 w-full" />
          ))}
        </div>
      </div>
      <span className="sr-only">Loading route status</span>
    </div>
  );
}

function MetricCard({ label, value, color }: { label: string; value: string; color: string }) {
  const colorClass = color === 'success' ? 'text-success' : color === 'warning' ? 'text-warning' : color === 'error' ? 'text-error' : 'text-text-primary';
  return (
    <div className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-xl p-3 text-center">
      <div className={`text-xl font-bold ${colorClass}`}>{value}</div>
      <div className="text-xs text-text-muted mt-0.5">{label}</div>
    </div>
  );
}
