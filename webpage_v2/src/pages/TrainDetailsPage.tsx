import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { TrainDetails } from '../types';
import { apiService } from '../services/api';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { StopCard } from '../components/StopCard';
import { formatTimeAgo, getTodayDateString } from '../utils/date';

export function TrainDetailsPage() {
  const { trainId } = useParams<{ trainId: string }>();
  const navigate = useNavigate();

  const [train, setTrain] = useState<TrainDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchTrainDetails = async () => {
    if (!trainId) return;

    try {
      setError(null);
      const response = await apiService.getTrainDetails(trainId, getTodayDateString());
      setTrain(response.train);
      setLastUpdated(new Date());
      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load train details');
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTrainDetails();

    // Poll every 30 seconds
    const interval = setInterval(fetchTrainDetails, 30000);
    return () => clearInterval(interval);
  }, [trainId]);

  if (!trainId) {
    return <ErrorMessage message="Invalid train ID" onRetry={() => navigate('/')} />;
  }

  if (loading && !train) {
    return <LoadingSpinner />;
  }

  if (error || !train) {
    return <ErrorMessage message={error || 'Train not found'} onRetry={fetchTrainDetails} />;
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <button
          onClick={() => navigate(-1)}
          className="text-accent hover:text-accent/80 mb-4 flex items-center gap-2"
        >
          ← Back
        </button>
      </div>

      <div className="bg-surface/70 backdrop-blur-xl border border-white/10 rounded-2xl p-6 mb-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-3xl font-bold">Train {train.train_id}</h2>
            <div className="text-white/60 mt-1">{train.line.name}</div>
          </div>
          {train.is_cancelled && (
            <span className="px-3 py-1 bg-error/20 text-error rounded-full text-sm font-semibold">
              Cancelled
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <div className="text-sm text-white/60">Origin</div>
            <div className="font-semibold">{train.route.origin}</div>
          </div>
          <div>
            <div className="text-sm text-white/60">Destination</div>
            <div className="font-semibold">{train.route.destination}</div>
          </div>
        </div>

        <div className="flex items-center justify-between text-sm">
          <div className="text-white/60">
            {lastUpdated && `Updated ${formatTimeAgo(lastUpdated.toISOString())}`}
          </div>
          <div className="text-white/60">{train.data_source}</div>
        </div>
      </div>

      <button
        onClick={fetchTrainDetails}
        disabled={loading}
        className="w-full mb-6 py-3 bg-surface/50 backdrop-blur-xl border border-white/10 rounded-xl font-semibold hover:bg-white/5 transition-all disabled:opacity-50"
      >
        {loading ? 'Refreshing...' : '🔄 Refresh'}
      </button>

      <h3 className="text-xl font-semibold mb-4">Stops</h3>
      <div className="space-y-3">
        {train.stops.map((stop) => (
          <StopCard key={`${stop.station.code}-${stop.stop_sequence}`} stop={stop} />
        ))}
      </div>
    </div>
  );
}
