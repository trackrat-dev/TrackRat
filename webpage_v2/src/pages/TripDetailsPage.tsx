import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { TripOption, TripLeg, TrainDetails, TransferInfo } from '../types';
import { apiService } from '../services/api';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { StopCard } from '../components/StopCard';
import { ServiceAlertBanner } from '../components/ServiceAlertBanner';
import { formatTime, formatTimeAgo, getTodayDateString } from '../utils/date';

/** Filter stops to the boarding→alighting range for a leg */
function filterStopsForLeg(
  train: TrainDetails,
  boardingCode: string,
  alightingCode: string
) {
  const stops = train.stops;
  const fromIdx = stops.findIndex(s => s.station.code.toUpperCase() === boardingCode.toUpperCase());
  const toIdx = stops.findIndex(s => s.station.code.toUpperCase() === alightingCode.toUpperCase());

  if (fromIdx !== -1 && toIdx !== -1 && fromIdx <= toIdx) {
    return {
      stops: stops.slice(fromIdx, toIdx + 1),
      hasPreviousStops: fromIdx > 0,
      hasLaterStops: toIdx < stops.length - 1,
    };
  }
  return { stops, hasPreviousStops: false, hasLaterStops: false };
}

function TransferIndicator({ transfer }: { transfer: TransferInfo }) {
  const walkDescription = transfer.same_station
    ? 'Same station'
    : transfer.walk_minutes <= 1
    ? 'Short walk'
    : `${transfer.walk_minutes} min walk`;

  return (
    <div className="flex items-center gap-3 px-4 py-4 my-2">
      <div className="flex flex-col items-center gap-0.5">
        <div className="w-px h-3 bg-text-muted/30" />
        <span className="text-text-muted/50 text-sm">
          {transfer.same_station ? '↓' : '🚶'}
        </span>
        <div className="w-px h-3 bg-text-muted/30" />
      </div>
      <div>
        <span className="text-sm font-medium text-text-muted">Transfer</span>
        <span className="text-sm text-text-muted/70 ml-2">
          {walkDescription}
          {!transfer.same_station && ` to ${transfer.to_station.name}`}
        </span>
      </div>
    </div>
  );
}

function LegDetail({ leg, train, navigate }: { leg: TripLeg; train: TrainDetails | null; navigate: ReturnType<typeof useNavigate> }) {
  const legStops = useMemo(() => {
    if (!train) return null;
    return filterStopsForLeg(train, leg.boarding.code, leg.alighting.code);
  }, [train, leg.boarding.code, leg.alighting.code]);

  return (
    <div>
      {/* Leg header */}
      <div className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4 mb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className="w-1.5 h-10 rounded-full"
              style={{ backgroundColor: leg.line.color }}
            />
            <div>
              <div className="font-semibold text-text-primary">
                {leg.line.name}
                {!leg.is_cancelled && train && (
                  <span className="text-text-muted font-normal ml-2">
                    Train {train.observation_type === 'SCHEDULED' ? 'TBD' : train.train_id}
                  </span>
                )}
              </div>
              <div className="text-sm text-text-muted">
                {leg.boarding.name} → {leg.alighting.name}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {leg.is_cancelled && (
              <span className="px-2 py-0.5 bg-error/20 text-error rounded text-xs font-semibold">
                Cancelled
              </span>
            )}
            <button
              onClick={() => navigate(`/train/${leg.train_id}/${leg.boarding.code}/${leg.alighting.code}`)}
              className="text-xs text-accent hover:text-accent/80 font-medium whitespace-nowrap"
            >
              Full train →
            </button>
          </div>
        </div>

        {train?.data_freshness?.last_updated && (
          <div className="text-xs text-text-muted mt-2">
            {train.data_source} • Updated {formatTimeAgo(train.data_freshness.last_updated)}
          </div>
        )}
      </div>

      {/* Service alerts */}
      <ServiceAlertBanner
        dataSource={leg.data_source}
        routeIds={leg.line?.code ? [leg.line.code] : undefined}
      />

      {/* Stops */}
      {!train ? (
        <div className="mb-4">
          <LoadingSpinner />
        </div>
      ) : legStops ? (
        <>
          {legStops.hasPreviousStops && (
            <div className="mb-3 p-3 bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl text-center text-text-muted text-sm">
              Train has previous stops
            </div>
          )}
          <div className="space-y-3 mb-4">
            {legStops.stops.map(stop => (
              <StopCard
                key={`${leg.train_id}-${stop.station.code}-${stop.stop_sequence}`}
                stop={stop}
                isOrigin={stop.station.code.toUpperCase() === leg.boarding.code.toUpperCase()}
                isDestination={stop.station.code.toUpperCase() === leg.alighting.code.toUpperCase()}
              />
            ))}
          </div>
          {legStops.hasLaterStops && (
            <div className="mb-4 p-3 bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl text-center text-text-muted text-sm">
              Train has later stops
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}

export function TripDetailsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const trip = (location.state as { trip?: TripOption })?.trip;

  const [legDetails, setLegDetails] = useState<(TrainDetails | null)[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Stable dependency for useEffect — derived before hooks to avoid conditional hook calls
  const legIds = trip?.legs.map(l => l.train_id).join(',') ?? '';

  useEffect(() => {
    if (!trip) return;

    const fetchAllLegDetails = async () => {
      try {
        setError(null);
        const results = await Promise.all(
          trip.legs.map(leg =>
            apiService.getTrainDetails(leg.train_id, getTodayDateString())
              .then(res => res.train)
              .catch(() => null)
          )
        );
        setLegDetails(results);
        setLoading(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load trip details');
        setLoading(false);
      }
    };

    fetchAllLegDetails();
    const interval = setInterval(fetchAllLegDetails, 30000);
    return () => clearInterval(interval);
  }, [legIds]);

  // Early returns after all hooks
  if (!trip) {
    return (
      <div className="max-w-4xl mx-auto">
        <ErrorMessage
          message="Trip details not available. Please search for your trip again."
          onRetry={() => navigate('/departures')}
        />
      </div>
    );
  }

  const durationDisplay = trip.total_duration_minutes < 60
    ? `${trip.total_duration_minutes} min`
    : `${Math.floor(trip.total_duration_minutes / 60)}h ${trip.total_duration_minutes % 60}m`;

  const firstLeg = trip.legs[0];
  const lastLeg = trip.legs[trip.legs.length - 1];

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

      {/* Trip header */}
      <div className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-6 mb-6">
        <h2 className="text-2xl font-bold text-text-primary">
          {firstLeg.boarding.name} → {lastLeg.alighting.name}
        </h2>
        <div className="flex items-center gap-4 mt-2 text-sm text-text-muted">
          <span>{durationDisplay}</span>
          <span>{formatTime(trip.departure_time)} → {formatTime(trip.arrival_time)}</span>
          <span>{trip.legs.length} trains • {trip.transfers.length} transfer{trip.transfers.length > 1 ? 's' : ''}</span>
        </div>
      </div>

      {loading && legDetails.every(d => d === null) ? (
        <LoadingSpinner />
      ) : error && legDetails.every(d => d === null) ? (
        <ErrorMessage message={error} onRetry={() => window.location.reload()} />
      ) : (
        trip.legs.map((leg, i) => (
          <div key={leg.train_id}>
            <LegDetail leg={leg} train={legDetails[i] ?? null} navigate={navigate} />
            {i < trip.transfers.length && (
              <TransferIndicator transfer={trip.transfers[i]} />
            )}
          </div>
        ))
      )}
    </div>
  );
}
