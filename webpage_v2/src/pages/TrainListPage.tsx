import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Train } from '../types';
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

  const fromStation = from ? getStationByCode(from) : null;
  const toStation = to ? getStationByCode(to) : null;

  // Check if train has already departed from the origin station
  const hasTrainDeparted = (train: Train): boolean => {
    const now = new Date();

    // Get departure time (prefer actual, fallback to scheduled)
    const departureTimeStr = train.departure.actual_time || train.departure.scheduled_time;

    if (!departureTimeStr) {
      // If no departure time, don't filter out (safe default)
      return false;
    }

    const departureTime = new Date(departureTimeStr);

    // Add 1 minute buffer to account for delays (matching iOS implementation)
    const departureWithBuffer = new Date(departureTime.getTime() + 60 * 1000);

    return departureWithBuffer < now;
  };

  const fetchTrains = async () => {
    if (!from || !to) return;

    try {
      setError(null);
      const response = await apiService.getDepartures(from, to);

      // Filter out trains that have already departed from the origin station
      const upcomingTrains = response.departures.filter(train => !hasTrainDeparted(train));

      setTrains(upcomingTrains);
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

    // Poll every 30 seconds
    const interval = setInterval(fetchTrains, 30000);
    return () => clearInterval(interval);
  }, [from, to]);

  if (!from || !to || !fromStation || !toStation) {
    return (
      <ErrorMessage
        message="Invalid route"
        onRetry={() => navigate('/')}
      />
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <button
          onClick={() => navigate('/')}
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

      <button
        onClick={fetchTrains}
        disabled={loading}
        className="w-full mb-4 py-3 bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl font-semibold hover:bg-surface transition-all disabled:opacity-50 text-text-primary"
      >
        {loading ? 'Refreshing...' : '🔄 Refresh'}
      </button>

      {loading && trains.length === 0 ? (
        <LoadingSpinner />
      ) : error ? (
        <ErrorMessage message={error} onRetry={fetchTrains} />
      ) : trains.length === 0 ? (
        <div className="text-center py-12 text-text-muted">
          No trains found for this route
        </div>
      ) : (
        <div className="space-y-3">
          {trains.map((train, index) => (
            <TrainCard
              key={`${train.train_id}-${index}`}
              train={train}
              onClick={() => navigate(`/train/${train.train_id}/${from}/${to}`)}
              from={from}
              to={to}
            />
          ))}
        </div>
      )}
    </div>
  );
}
