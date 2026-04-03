import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { TripHistoryEntry } from '../types';
import { storageService } from '../services/storage';
import { formatTime } from '../utils/date';

export function TripHistoryPage() {
  const [history, setHistory] = useState<TripHistoryEntry[]>([]);

  useEffect(() => {
    setHistory(storageService.getTripHistory());
  }, []);

  const stats = useMemo(() => {
    const uniqueRoutes = new Set(history.map((entry) => `${entry.departureCode}-${entry.destinationCode}`)).size;
    const uniqueSystems = new Set(history.map((entry) => entry.dataSource || 'MIXED')).size;
    const routeCounts = new Map<string, { label: string; count: number }>();

    history.forEach((entry) => {
      const key = `${entry.departureCode}-${entry.destinationCode}`;
      const current = routeCounts.get(key);
      if (current) {
        current.count += 1;
        return;
      }
      routeCounts.set(key, {
        label: `${entry.departureName} → ${entry.destinationName}`,
        count: 1,
      });
    });

    const topRoute = [...routeCounts.values()].sort((left, right) => right.count - left.count)[0] || null;

    return {
      totalTrips: history.length,
      uniqueRoutes,
      uniqueSystems,
      topRoute,
    };
  }, [history]);

  const groupedHistory = useMemo(() => {
    const formatter = new Intl.DateTimeFormat('en-US', {
      month: 'long',
      year: 'numeric',
    });

    const grouped = new Map<string, TripHistoryEntry[]>();
    history.forEach((entry) => {
      const label = formatter.format(entry.viewedAt);
      const existing = grouped.get(label);
      if (existing) {
        existing.push(entry);
        return;
      }
      grouped.set(label, [entry]);
    });

    return [...grouped.entries()];
  }, [history]);

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-text-primary text-center">Trip History</h2>
        <p className="text-sm text-text-muted text-center mt-2">
          Trips you open on the web are saved here for quick replay.
        </p>
      </div>

      {history.length === 0 ? (
        <div className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-10 text-center">
          <div className="text-4xl mb-3">🚆</div>
          <div className="text-lg font-semibold text-text-primary">No trips saved yet</div>
          <div className="text-sm text-text-muted mt-2">
            Open a train or transfer trip and it will show up here.
          </div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
            <StatCard label="Trips viewed" value={String(stats.totalTrips)} />
            <StatCard label="Unique routes" value={String(stats.uniqueRoutes)} />
            <StatCard label="Systems used" value={String(stats.uniqueSystems)} />
          </div>

          {stats.topRoute && (
            <div className="mb-6 bg-accent/10 border border-accent/30 rounded-2xl p-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-accent mb-1">
                Most viewed route
              </div>
              <div className="text-lg font-semibold text-text-primary">
                {stats.topRoute.label}
              </div>
              <div className="text-sm text-text-muted mt-1">
                Opened {stats.topRoute.count} times
              </div>
            </div>
          )}

          <div className="space-y-6">
            {groupedHistory.map(([month, entries]) => (
              <div key={month}>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-lg font-semibold text-text-primary">{month}</h3>
                  <div className="text-sm text-text-muted">{entries.length} trip{entries.length !== 1 ? 's' : ''}</div>
                </div>
                <div className="space-y-3">
                  {entries.map((entry) => (
                    <Link
                      key={entry.id}
                      to={entry.href}
                      className="block bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4 hover:bg-surface transition-all"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="font-semibold text-text-primary">
                            {entry.departureName} → {entry.destinationName}
                          </div>
                          <div className="text-sm text-text-muted mt-1">
                            {entry.lineName || 'Trip'}{entry.trainId ? ` • Train ${entry.trainId}` : ''}
                          </div>
                          <div className="text-sm text-text-muted mt-1">
                            {entry.scheduledDeparture ? formatTime(entry.scheduledDeparture) : 'Unknown time'}
                            {entry.scheduledArrival ? ` → ${formatTime(entry.scheduledArrival)}` : ''}
                            {entry.totalDurationMinutes != null ? ` • ${formatDuration(entry.totalDurationMinutes)}` : ''}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                            {entry.dataSource || 'Mixed'}
                          </div>
                          <div className="text-sm text-text-muted mt-1">
                            {entry.transferCount > 0 ? `${entry.transferCount} transfer${entry.transferCount !== 1 ? 's' : ''}` : 'Direct'}
                          </div>
                          <div className="text-sm text-text-muted mt-1">
                            Viewed {entry.viewedAt.toLocaleDateString()} {entry.viewedAt.toLocaleTimeString([], {
                              hour: 'numeric',
                              minute: '2-digit',
                            })}
                          </div>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4 text-center">
      <div className="text-2xl font-bold text-text-primary">{value}</div>
      <div className="text-sm text-text-muted mt-1">{label}</div>
    </div>
  );
}

function formatDuration(totalMinutes: number) {
  if (totalMinutes < 60) return `${totalMinutes} min`;
  return `${Math.floor(totalMinutes / 60)}h ${totalMinutes % 60}m`;
}
