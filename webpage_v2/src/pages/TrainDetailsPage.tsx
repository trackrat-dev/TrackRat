import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { TrainDetails, StationPredictionSupport } from '../types';
import { apiService } from '../services/api';
import { usePolling } from '../utils/usePolling';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { StopCard } from '../components/StopCard';
import { TrackPredictionBar } from '../components/TrackPredictionBar';
import { ShareButton } from '../components/ShareButton';
import { DelayForecastCard } from '../components/DelayForecastCard';
import { ServiceAlertBanner } from '../components/ServiceAlertBanner';
import { HistoricalPerformance } from '../components/HistoricalPerformance';
import { SimilarTrainsPanel } from '../components/SimilarTrainsPanel';
import { storageService } from '../services/storage';
import { getTodayDateString, formatTime, isToday, formatDate } from '../utils/date';
import { buildTrainShareData } from '../utils/share';

export function TrainDetailsPage() {
  const { trainId, from: fromPath, to: toPath } = useParams<{ trainId: string; from?: string; to?: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  // Merge path params with query params for iOS universal link compatibility
  // Path params take priority: /train/123/NY/NP, query params as fallback: /train/123?from=NY&to=NP
  const from = fromPath || searchParams.get('from') || undefined;
  const to = toPath || searchParams.get('to') || undefined;
  const journeyDate = searchParams.get('date') || undefined;
  const dataSource = searchParams.get('data_source') || undefined;

  const [train, setTrain] = useState<TrainDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [supportedStations, setSupportedStations] = useState<StationPredictionSupport[]>([]);
  const savedHistoryKeyRef = useRef<string | null>(null);

  const fetchTrainDetails = useCallback(async (signal?: AbortSignal) => {
    if (!trainId) return;

    try {
      const response = await apiService.getTrainDetails(
        trainId,
        journeyDate || getTodayDateString(),
        {
          dataSource,
          fromStation: from,
          signal,
        }
      );
      setTrain(response.train);
      setError(null);
      setLoading(false);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      setError(err instanceof Error ? err.message : 'Failed to load train details');
      setLoading(false);
    }
  }, [trainId, journeyDate, dataSource, from]);

  usePolling(fetchTrainDetails, [trainId, journeyDate, dataSource, from]);

  // Fetch supported stations for track predictions (once, cached by API service)
  useEffect(() => {
    apiService.getSupportedStations()
      .then(res => setSupportedStations(res.stations))
      .catch(() => {}); // Fail silently — predictions are optional
  }, []);

  // Attempt iOS deep link on mobile Safari — try to open in native app
  useEffect(() => {
    const isIOS = /iPhone|iPad|iPod/.test(navigator.userAgent);
    if (!isIOS || !trainId) return;

    const deepLinkParams = new URLSearchParams();
    if (journeyDate) deepLinkParams.set('date', journeyDate);
    if (from) deepLinkParams.set('from', from);
    if (to) deepLinkParams.set('to', to);
    if (dataSource) deepLinkParams.set('data_source', dataSource);
    const deepLinkQuery = deepLinkParams.toString();
    const deepLinkUrl = `trackrat://train/${trainId}${deepLinkQuery ? `?${deepLinkQuery}` : ''}`;
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
  }, [trainId, from, to, journeyDate, dataSource]);

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

  useEffect(() => {
    if (!train) return;

    const historyKey = `${train.train_id}:${train.journey_date}:${from || train.route.origin_code}:${to || train.route.destination_code}`;
    if (savedHistoryKeyRef.current === historyKey) return;

    storageService.saveViewedTrainTrip(train, {
      fromCode: from,
      toCode: to,
    });
    savedHistoryKeyRef.current = historyKey;
  }, [train, from, to]);

  if (!trainId) {
    return <ErrorMessage message="Invalid train ID" onRetry={() => navigate('/departures')} />;
  }

  if (loading && !train) {
    return <LoadingSpinner />;
  }

  if (error || !train) {
    return <ErrorMessage message={error || 'Train not found'} onRetry={() => fetchTrainDetails()} />;
  }

  // Check if we should show track predictions
  // Use the user's boarding station (from route params), not the train's origin
  const predictionStationCode = from?.toUpperCase() || train.route.origin_code;
  const predictionStop = train.stops.find(s => s.station.code === predictionStationCode);
  const stationSupported = supportedStations.some(
    s => s.code === predictionStationCode && s.predictions_available
  );
  const shouldShowPredictions =
    stationSupported &&              // Supported station (from API)
    !predictionStop?.track &&        // No track assigned
    !predictionStop?.has_departed_station && // Train hasn't left user's origin
    !train.is_cancelled;             // Not cancelled

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
            <h2 className="text-3xl font-bold text-text-primary">Train {train.observation_type === 'SCHEDULED' ? 'TBD' : train.train_id}</h2>
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
                journeyDate: train.journey_date,
                dataSource: train.data_source,
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

        <div className="flex items-center gap-3 text-sm text-text-muted">
          <span>{train.data_source}</span>
          {!isToday(train.journey_date) && (
            <span className="px-2 py-0.5 bg-warning/20 text-warning rounded text-xs font-medium">
              {formatDate(train.journey_date)}
            </span>
          )}
          {train.data_freshness?.last_updated && (
            <span>Updated at {formatTime(train.data_freshness.last_updated)}</span>
          )}
        </div>
      </div>

      {/* Service alerts for this train's system */}
      <ServiceAlertBanner
        dataSource={train.data_source}
        routeIds={train.line?.code ? [train.line.code] : undefined}
      />

      {/* Track predictions */}
      {shouldShowPredictions && (
        <div className="mb-6">
          <TrackPredictionBar
            trainId={train.train_id}
            originStationCode={predictionStationCode}
            journeyDate={train.journey_date}
          />
        </div>
      )}

      {/* Delay forecast */}
      {!train.is_cancelled && (
        <div className="mb-6">
          <DelayForecastCard
            trainId={train.train_id}
            stationCode={predictionStationCode}
            journeyDate={train.journey_date}
          />
        </div>
      )}

      {/* Similar trains panel — only before departure from user's origin */}
      {from && to && !predictionStop?.has_departed_station && (
        <SimilarTrainsPanel
          trainId={train.train_id}
          from={from.toUpperCase()}
          to={to.toUpperCase()}
          dataSource={train.data_source}
        />
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
            currentLine={train.data_source === 'SUBWAY' ? train.line.code : undefined}
          />
        ))}
      </div>

      {hasLaterStops && (
        <div className="mt-3 p-4 bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl text-center text-text-muted text-sm">
          Train has later stops
        </div>
      )}

      {/* Historical performance */}
      <div className="mt-6">
        <HistoricalPerformance
          trainId={train.train_id}
          fromStation={from?.toUpperCase()}
          toStation={to?.toUpperCase()}
        />
      </div>
    </div>
  );
}
