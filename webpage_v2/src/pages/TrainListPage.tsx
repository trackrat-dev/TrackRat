import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Train, OperationsSummaryResponse } from '../types';
import { apiService } from '../services/api';
import { useAppStore } from '../store/appStore';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { TrainCard } from '../components/TrainCard';
import { getStationByCode } from '../data/stations';
import { formatTimeAgo } from '../utils/date';

export function TrainListPage() {
  const { from, to } = useParams<{ from: string; to: string }>();
  const navigate = useNavigate();
  const { addRecentTrip } = useAppStore();

  const [trains, setTrains] = useState<Train[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [trainFilter, setTrainFilter] = useState('');
  const [summary, setSummary] = useState<OperationsSummaryResponse | null>(null);
  const [summaryExpanded, setSummaryExpanded] = useState(false);

  const fromStation = from ? getStationByCode(from) : null;
  const toStation = to ? getStationByCode(to) : null;

  // Check if train has already departed from the origin station
  const hasTrainDeparted = (train: Train): boolean => {
    const now = new Date();
    const departureTimeStr = train.departure.actual_time || train.departure.updated_time || train.departure.scheduled_time;
    if (!departureTimeStr) return false;
    const departureTime = new Date(departureTimeStr);
    // 1 minute buffer (matching iOS implementation)
    const departureWithBuffer = new Date(departureTime.getTime() + 60 * 1000);
    return departureWithBuffer < now;
  };

  const fetchTrains = async () => {
    if (!from || !to) return;

    try {
      setError(null);
      const response = await apiService.getDepartures(from, to);

      // Sort: upcoming trains first, then departed trains
      const sorted = [...response.departures].sort((a, b) => {
        const aDeparted = hasTrainDeparted(a);
        const bDeparted = hasTrainDeparted(b);
        if (aDeparted !== bDeparted) return aDeparted ? 1 : -1;
        return 0; // preserve API order within each group
      });

      setTrains(sorted);
      setLastUpdated(new Date());
      setLoading(false);

      // Save to recent trips
      if (fromStation && toStation) {
        addRecentTrip(fromStation, toStation);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load trains');
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTrains();

    // Fetch summary once on mount (not polled)
    if (from && to) {
      apiService.getRouteSummary(from, to).then(setSummary);
    }

    // Poll departures every 30 seconds
    const interval = setInterval(fetchTrains, 30000);
    return () => clearInterval(interval);
  }, [from, to]);

  const filteredTrains = useMemo(() => {
    if (!trainFilter.trim()) return trains;
    const q = trainFilter.trim().toLowerCase();
    return trains.filter(t => t.train_id.toLowerCase().includes(q));
  }, [trains, trainFilter]);

  if (!from || !to || !fromStation || !toStation) {
    return (
      <ErrorMessage
        message="Invalid route"
        onRetry={() => navigate('/departures')}
      />
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <button
          onClick={() => navigate('/departures')}
          className="text-accent hover:text-accent/80 mb-4 flex items-center gap-2 font-semibold"
        >
          ← Back
        </button>
        <h2 className="text-2xl font-bold text-text-primary">
          {fromStation.name} → {toStation.name}
        </h2>
        {lastUpdated && (
          <div className="text-sm text-text-muted mt-2">
            Updated {formatTimeAgo(lastUpdated.toISOString())}
          </div>
        )}
      </div>

      {summary && (
        <button
          onClick={() => setSummaryExpanded(!summaryExpanded)}
          className="w-full mb-4 bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl p-4 text-left transition-all hover:bg-surface"
        >
          <div className="flex items-center justify-between">
            <div className="text-sm font-medium text-text-primary">{summary.headline}</div>
            <span className="text-text-muted text-xs ml-2">{summaryExpanded ? '▲' : '▼'}</span>
          </div>
          {summaryExpanded && (
            <div className="mt-3 text-sm text-text-muted whitespace-pre-line">{summary.body}</div>
          )}
        </button>
      )}

      <div className="flex gap-2 mb-4">
        <button
          onClick={fetchTrains}
          disabled={loading}
          className="py-3 px-4 bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl font-semibold hover:bg-surface transition-all disabled:opacity-50 text-text-primary"
        >
          {loading ? '...' : '🔄'}
        </button>
        <div className="flex-1 relative">
          <input
            type="text"
            value={trainFilter}
            onChange={(e) => setTrainFilter(e.target.value)}
            placeholder="Filter by train #"
            className="w-full px-4 py-3 bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-accent"
          />
          {trainFilter && (
            <button
              onClick={() => setTrainFilter('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
            >
              ×
            </button>
          )}
        </div>
      </div>

      {loading && trains.length === 0 ? (
        <LoadingSpinner />
      ) : error ? (
        <ErrorMessage message={error} onRetry={fetchTrains} />
      ) : filteredTrains.length === 0 ? (
        <div className="text-center py-12 text-text-muted">
          {trainFilter ? 'No matching trains' : 'No trains found for this route'}
        </div>
      ) : (
        <div className="space-y-3">
          {filteredTrains.map((train, index) => (
            <TrainCard
              key={`${train.train_id}-${index}`}
              train={train}
              onClick={() => navigate(`/train/${train.train_id}/${from}/${to}`)}
              from={from}
              to={to}
              departed={hasTrainDeparted(train)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
