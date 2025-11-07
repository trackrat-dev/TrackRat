import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { TrainDetails } from '../types';
import { apiService } from '../services/api';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { StopCard } from '../components/StopCard';
import { TrackPredictionBar } from '../components/TrackPredictionBar';
import { formatTimeAgo, getTodayDateString } from '../utils/date';

export function TrainDetailsPage() {
  const { trainId, from, to } = useParams<{ trainId: string; from?: string; to?: string }>();
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

  // Filter stops based on user's journey (from/to params)
  // Must be called before early returns to maintain hook order
  const { displayableStops, hasPreviousStops, hasLaterStops } = useMemo(() => {
    if (!train || !from || !to) {
      return {
        displayableStops: train?.stops || [],
        hasPreviousStops: false,
        hasLaterStops: false
      };
    }

    const stops = train.stops;

    // Find origin station index by station code (case-insensitive)
    const originIndex = stops.findIndex(
      stop => stop.station.code.toUpperCase() === from.toUpperCase()
    );

    // Find destination station index by station code (case-insensitive)
    const destinationIndex = stops.findIndex(
      stop => stop.station.code.toUpperCase() === to.toUpperCase()
    );

    // If both indices found and valid, filter to inclusive range
    if (originIndex !== -1 && destinationIndex !== -1 && originIndex <= destinationIndex) {
      return {
        displayableStops: stops.slice(originIndex, destinationIndex + 1),
        hasPreviousStops: originIndex > 0,
        hasLaterStops: destinationIndex < stops.length - 1
      };
    }

    // Fallback: show all stops
    return {
      displayableStops: stops,
      hasPreviousStops: false,
      hasLaterStops: false
    };
  }, [train, from, to]);

  if (!trainId) {
    return <ErrorMessage message="Invalid train ID" onRetry={() => navigate('/')} />;
  }

  if (loading && !train) {
    return <LoadingSpinner />;
  }

  if (error || !train) {
    return <ErrorMessage message={error || 'Train not found'} onRetry={fetchTrainDetails} />;
  }

  // Check if we should show track predictions
  // Show for NY Penn departures without track assignment
  const originStop = train.stops.find(s => s.station.code === train.route.origin_code);
  const shouldShowPredictions =
    train.route.origin_code === 'NY' &&  // Only NY Penn
    !originStop?.track &&                 // No track assigned
    !train.is_cancelled;                  // Not cancelled

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <button
          onClick={() => navigate(-1)}
          className="text-accent hover:text-accent/80 mb-4 flex items-center gap-2 font-semibold"
        >
          ← Back
        </button>
      </div>

      <div className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-6 mb-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-3xl font-bold text-text-primary">Train {train.train_id}</h2>
            <div className="text-text-muted mt-1">{train.line.name}</div>
          </div>
          {train.is_cancelled && (
            <span className="px-3 py-1 bg-error/20 text-error rounded-full text-sm font-semibold">
              Cancelled
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <div className="text-sm text-text-muted">Origin</div>
            <div className="font-semibold text-text-primary">{train.route.origin}</div>
          </div>
          <div>
            <div className="text-sm text-text-muted">Destination</div>
            <div className="font-semibold text-text-primary">{train.route.destination}</div>
          </div>
        </div>

        <div className="flex items-center justify-between text-sm">
          <div className="text-text-muted">
            {lastUpdated && `Updated ${formatTimeAgo(lastUpdated.toISOString())}`}
          </div>
          <div className="text-text-muted">{train.data_source}</div>
        </div>
      </div>

      <button
        onClick={fetchTrainDetails}
        disabled={loading}
        className="w-full mb-6 py-3 bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl font-semibold hover:bg-surface transition-all disabled:opacity-50 text-text-primary"
      >
        {loading ? 'Refreshing...' : '🔄 Refresh'}
      </button>

      {/* Track predictions for NY Penn Station */}
      {shouldShowPredictions && (
        <div className="mb-6">
          <TrackPredictionBar
            trainId={train.train_id}
            originStationCode={train.route.origin_code}
            journeyDate={train.journey_date}
          />
        </div>
      )}

      <h3 className="text-xl font-semibold mb-4 text-text-primary">Stops</h3>

      {hasPreviousStops && (
        <div className="mb-3 p-4 bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl text-center text-text-muted text-sm">
          Train has previous stops
        </div>
      )}

      <div className="space-y-3">
        {displayableStops.map((stop) => (
          <StopCard key={`${stop.station.code}-${stop.stop_sequence}`} stop={stop} />
        ))}
      </div>

      {hasLaterStops && (
        <div className="mt-3 p-4 bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl text-center text-text-muted text-sm">
          Train has later stops
        </div>
      )}
    </div>
  );
}
