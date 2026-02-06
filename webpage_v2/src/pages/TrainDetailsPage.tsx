import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { TrainDetails } from '../types';
import { apiService } from '../services/api';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { StopCard } from '../components/StopCard';
import { TrackPredictionBar } from '../components/TrackPredictionBar';
import { ShareButton } from '../components/ShareButton';
import { getTodayDateString } from '../utils/date';
import { buildTrainShareData } from '../utils/share';

export function TrainDetailsPage() {
  const { trainId, from: fromPath, to: toPath } = useParams<{ trainId: string; from?: string; to?: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  // Merge path params with query params for iOS universal link compatibility
  // Path params take priority: /train/123/NY/NP, query params as fallback: /train/123?from=NY&to=NP
  const from = fromPath || searchParams.get('from') || undefined;
  const to = toPath || searchParams.get('to') || undefined;

  const [train, setTrain] = useState<TrainDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTrainDetails = async () => {
    if (!trainId) return;

    try {
      setError(null);
      const response = await apiService.getTrainDetails(trainId, getTodayDateString());
      setTrain(response.train);
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

  // Attempt iOS deep link on mobile Safari — try to open in native app
  useEffect(() => {
    const isIOS = /iPhone|iPad|iPod/.test(navigator.userAgent);
    if (!isIOS || !trainId) return;

    const deepLinkUrl = `trackrat://train/${trainId}${from ? `?from=${from}` : ''}${to ? `${from ? '&' : '?'}to=${to}` : ''}`;
    const iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    iframe.src = deepLinkUrl;
    document.body.appendChild(iframe);

    // Clean up iframe after attempt
    const timeout = setTimeout(() => {
      document.body.removeChild(iframe);
    }, 2000);

    return () => {
      clearTimeout(timeout);
      if (iframe.parentNode) {
        document.body.removeChild(iframe);
      }
    };
  }, [trainId, from, to]);

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
    return <ErrorMessage message="Invalid train ID" onRetry={() => navigate('/departures')} />;
  }

  if (loading && !train) {
    return <LoadingSpinner />;
  }

  if (error || !train) {
    return <ErrorMessage message={error || 'Train not found'} onRetry={fetchTrainDetails} />;
  }

  // Stations that support track predictions (backend has ml_enabled: true for these)
  const supportedStations = new Set(['NY', 'NP', 'ND', 'HB', 'MP', 'ST', 'TR', 'PH', 'DV', 'DN', 'PL', 'LB', 'JA', 'JAM', 'GCT']);

  // Check if we should show track predictions
  // Show for supported station departures without track assignment
  const originStop = train.stops.find(s => s.station.code === train.route.origin_code);
  const shouldShowPredictions =
    supportedStations.has(train.route.origin_code) &&  // Supported station
    !originStop?.track &&                               // No track assigned
    !train.is_cancelled;                                // Not cancelled

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
          <div className="flex-1">
            <h2 className="text-3xl font-bold text-text-primary">Train {train.train_id}</h2>
            <div className="text-text-muted mt-1">{train.line.name}</div>
          </div>
          <div className="flex items-center gap-3">
            <ShareButton
              shareData={buildTrainShareData({
                trainId: train.train_id,
                origin: train.route.origin,
                destination: train.route.destination,
                from: from,
                to: to,
              })}
            />
            {train.is_cancelled && (
              <span className="px-3 py-1 bg-error/20 text-error rounded-full text-sm font-semibold">
                Cancelled
              </span>
            )}
          </div>
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

        <div className="text-sm text-text-muted">{train.data_source}</div>
      </div>

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
          <StopCard
            key={`${stop.station.code}-${stop.stop_sequence}`}
            stop={stop}
            isOrigin={from ? stop.station.code.toUpperCase() === from.toUpperCase() : false}
            isDestination={to ? stop.station.code.toUpperCase() === to.toUpperCase() : false}
          />
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
