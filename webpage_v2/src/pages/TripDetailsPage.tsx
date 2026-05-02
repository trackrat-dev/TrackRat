import { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { TripOption, TripLeg, TrainDetails } from '../types';
import { apiService } from '../services/api';
import { usePolling } from '../utils/usePolling';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { StopCard } from '../components/StopCard';
import { ServiceAlertBanner } from '../components/ServiceAlertBanner';
import { TransferIndicator } from '../components/TransferTripCard';
import { formatTime } from '../utils/date';
import { buildTrainUrl, parseTripParam } from '../utils/routes';
import { storageService } from '../services/storage';

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

function LegDetail({ leg, train, loading, navigate }: { leg: TripLeg; train: TrainDetails | null; loading: boolean; navigate: ReturnType<typeof useNavigate> }) {
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
              onClick={() => navigate(buildTrainUrl({
                trainId: leg.train_id,
                from: leg.boarding.code,
                to: leg.alighting.code,
                date: leg.journey_date,
                dataSource: leg.data_source,
              }))}
              className="text-xs text-accent hover:text-accent/80 font-medium whitespace-nowrap"
            >
              Full train →
            </button>
          </div>
        </div>

        {train?.data_freshness?.last_updated && (
          <div className="text-xs text-text-muted mt-2">
            {train.data_source} • Updated at {formatTime(train.data_freshness.last_updated)}
          </div>
        )}
      </div>

      {/* Service alerts */}
      <ServiceAlertBanner
        dataSource={leg.data_source}
        routeIds={leg.line?.code ? [leg.line.code] : undefined}
      />

      {/* Stops */}
      {train == null && loading ? (
        <div className="mb-4">
          <LoadingSpinner />
        </div>
      ) : train == null ? (
        <div className="mb-4 p-4 bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl text-center text-text-muted text-sm">
          Could not load stops for this leg.
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
  const [searchParams] = useSearchParams();
  const trip = parseTripParam(searchParams.get('trip'))
    ?? (location.state as { trip?: TripOption } | null)?.trip
    ?? null;

  const [legDetails, setLegDetails] = useState<(TrainDetails | null)[]>([]);
  const [loading, setLoading] = useState(true);

  // Stable dependency for useEffect
  const legIds = trip?.legs
    .map(l => `${l.train_id}:${l.journey_date}:${l.data_source}:${l.boarding.code}:${l.alighting.code}`)
    .join(',') ?? '';

  useEffect(() => {
    if (!trip) return;
    storageService.saveViewedTripOption(trip);
    // Persist view history once per trip identity, not on every poll.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [legIds]);

  const fetchAllLegDetails = useCallback(async (signal?: AbortSignal) => {
    if (!trip) return;
    const results = await Promise.all(
      trip.legs.map(leg =>
        apiService.getTrainDetails(
          leg.train_id,
          leg.journey_date,
          {
            dataSource: leg.data_source,
            fromStation: leg.boarding.code,
            signal,
          }
        )
          .then(res => res.train)
          .catch((err) => {
            if (err instanceof DOMException && err.name === 'AbortError') throw err;
            return null;
          })
      )
    );
    setLegDetails(results);
    setLoading(false);
    // legIds captures all reactive bits of the legs; including `trip` directly
    // would needlessly re-fire on equal-but-different references.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [legIds]);

  usePolling(fetchAllLegDetails, [legIds], { enabled: !!trip });

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
          <span>{trip.legs.length} trains • {trip.transfers.length} transfer{trip.transfers.length !== 1 ? 's' : ''}</span>
        </div>
      </div>

      {loading && legDetails.length === 0 ? (
        <LoadingSpinner />
      ) : (
        trip.legs.map((leg, i) => (
          <div key={`${leg.train_id}-${i}`}>
            <LegDetail leg={leg} train={legDetails[i] ?? null} loading={loading} navigate={navigate} />
            {i < trip.transfers.length && (
              <TransferIndicator transfer={trip.transfers[i]} variant="detail" />
            )}
          </div>
        ))
      )}
    </div>
  );
}
