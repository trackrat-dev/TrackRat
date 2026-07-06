import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { TripOption, TripLeg, TransferInfo, StationTiming, TrainDetails, Stop } from '../types';
import { apiService } from '../services/api';
import { usePolling } from '../utils/usePolling';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { StopCard } from '../components/StopCard';
import { ServiceAlertBanner } from '../components/ServiceAlertBanner';
import { TransferIndicator } from '../components/TransferTripCard';
import { formatTime } from '../utils/date';
import { buildTrainUrl, parseTripParam, parseTripLegsParam, TripDescriptor, TripLegDescriptor } from '../utils/routes';
import { getStationByCode, SYSTEM_NAMES } from '../data/stations';
import { storageService } from '../services/storage';

/** Line color for a leg whose train aged out of retention (matches UpcomingTrains). */
const FALLBACK_LINE_COLOR = '#CC5500';

/** The per-leg fetch inputs, normalized from either a full trip or a descriptor. */
interface FetchLeg {
  trainId: string;
  date: string;
  dataSource: string;
  boardingCode: string;
  alightingCode: string;
}

/**
 * True when two station codes refer to the same physical station, resolving
 * cross-system aliases (e.g. PATH `PNK` ↔ NJT `NP`) so a shared URL's boarding
 * code still matches the stop code returned by `getTrainDetails`.
 */
function codesMatch(a: string, b: string): boolean {
  if (a.toUpperCase() === b.toUpperCase()) return true;
  const canonicalA = getStationByCode(a)?.code;
  const canonicalB = getStationByCode(b)?.code;
  return canonicalA != null && canonicalB != null && canonicalA === canonicalB;
}

/** Filter stops to the boarding→alighting range for a leg */
function filterStopsForLeg(
  train: TrainDetails,
  boardingCode: string,
  alightingCode: string
) {
  const stops = train.stops;
  const fromIdx = stops.findIndex(s => codesMatch(s.station.code, boardingCode));
  const toIdx = stops.findIndex(s => codesMatch(s.station.code, alightingCode));

  if (fromIdx !== -1 && toIdx !== -1 && fromIdx <= toIdx) {
    return {
      stops: stops.slice(fromIdx, toIdx + 1),
      hasPreviousStops: fromIdx > 0,
      hasLaterStops: toIdx < stops.length - 1,
    };
  }
  return { stops, hasPreviousStops: false, hasLaterStops: false };
}

/**
 * Reconstruct a full `TripOption` from a compact URL descriptor plus the
 * per-leg `getTrainDetails` responses. A leg whose train 404'd (`null`) yields
 * a degraded leg (name from the static station list, no timings) so the page
 * still renders and shows that leg's error state instead of crashing.
 */
function buildTripFromDescriptor(
  descriptor: TripDescriptor,
  legDetails: (TrainDetails | null)[]
): TripOption {
  const legs = descriptor.legs.map((descLeg, i) =>
    buildLeg(descLeg, descriptor.date, legDetails[i] ?? null)
  );

  const transfers: TransferInfo[] = [];
  for (let i = 0; i < legs.length - 1; i++) {
    const walkMinutes = descriptor.walkMinutes[i] ?? 0;
    transfers.push({
      from_station: { code: legs[i].alighting.code, name: legs[i].alighting.name },
      to_station: { code: legs[i + 1].boarding.code, name: legs[i + 1].boarding.name },
      walk_minutes: walkMinutes,
      same_station: walkMinutes === 0,
    });
  }

  const departureTime = bestTime(legs[0]?.boarding);
  const arrivalTime = bestTime(legs[legs.length - 1]?.alighting);

  return {
    legs,
    transfers,
    departure_time: departureTime,
    arrival_time: arrivalTime,
    total_duration_minutes: tripDurationMinutes(departureTime, arrivalTime),
    is_direct: legs.length === 1,
  };
}

function buildLeg(descLeg: TripLegDescriptor, date: string, train: TrainDetails | null): TripLeg {
  const boardingStop = train ? findStop(train, descLeg.boardingCode) : undefined;
  const alightingStop = train ? findStop(train, descLeg.alightingCode) : undefined;

  return {
    train_id: descLeg.trainId,
    journey_date: date,
    data_source: descLeg.dataSource,
    line: train?.line ?? {
      code: '',
      name: SYSTEM_NAMES[descLeg.dataSource] ?? descLeg.dataSource,
      color: FALLBACK_LINE_COLOR,
    },
    destination: train?.route.destination ?? '',
    boarding: stationTiming(descLeg.boardingCode, boardingStop, 'departure'),
    alighting: stationTiming(descLeg.alightingCode, alightingStop, 'arrival'),
    is_cancelled: train?.is_cancelled ?? false,
    train_position: train?.train_position,
  };
}

function findStop(train: TrainDetails, code: string): Stop | undefined {
  return train.stops.find(s => codesMatch(s.station.code, code));
}

/** Build a `StationTiming` from a stop, using its departure or arrival times. */
function stationTiming(code: string, stop: Stop | undefined, edge: 'departure' | 'arrival'): StationTiming {
  const scheduled = edge === 'departure' ? stop?.scheduled_departure : stop?.scheduled_arrival;
  const updated = edge === 'departure' ? stop?.updated_departure : stop?.updated_arrival;
  const actual = edge === 'departure' ? stop?.actual_departure : stop?.actual_arrival;
  return {
    code,
    name: stop?.station.name ?? getStationByCode(code)?.name ?? code,
    scheduled_time: scheduled ?? '',
    updated_time: updated ?? null,
    actual_time: actual ?? null,
    track: stop?.track ?? null,
  };
}

function bestTime(timing?: StationTiming): string {
  return timing?.actual_time || timing?.updated_time || timing?.scheduled_time || '';
}

function tripDurationMinutes(start: string, end: string): number {
  if (!start || !end) return 0;
  const ms = new Date(end).getTime() - new Date(start).getTime();
  return Number.isFinite(ms) && ms > 0 ? Math.round(ms / 60000) : 0;
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
                isOrigin={codesMatch(stop.station.code, leg.boarding.code)}
                isDestination={codesMatch(stop.station.code, leg.alighting.code)}
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
  const legsParam = searchParams.get('legs');
  const dateParam = searchParams.get('date');
  const walkParam = searchParams.get('walk');
  const tripParam = searchParams.get('trip');

  // A full TripOption is available instantly when we arrived via in-app
  // navigation (location.state) or a legacy `?trip=<JSON>` link. Otherwise we
  // reconstruct it from the compact `?legs=` descriptor after fetching each leg.
  const initialTrip = useMemo<TripOption | null>(
    () => (location.state as { trip?: TripOption } | null)?.trip
      ?? parseTripParam(tripParam)
      ?? null,
    [location.state, tripParam]
  );

  const descriptor = useMemo<TripDescriptor | null>(
    () => (initialTrip ? null : parseTripLegsParam(searchParams)),
    // Re-parse only when the raw compact params change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [initialTrip, legsParam, dateParam, walkParam]
  );

  // Normalize whichever source we have into a flat per-leg fetch list.
  const fetchLegs = useMemo<FetchLeg[]>(() => {
    if (initialTrip) {
      return initialTrip.legs.map(l => ({
        trainId: l.train_id,
        date: l.journey_date,
        dataSource: l.data_source,
        boardingCode: l.boarding.code,
        alightingCode: l.alighting.code,
      }));
    }
    if (descriptor) {
      return descriptor.legs.map(l => ({
        trainId: l.trainId,
        date: descriptor.date,
        dataSource: l.dataSource,
        boardingCode: l.boardingCode,
        alightingCode: l.alightingCode,
      }));
    }
    return [];
  }, [initialTrip, descriptor]);

  // Results are keyed by the leg identity they belong to so that navigating
  // straight from one trip to another never renders stale legs against the new
  // trip: `loading` is simply "results for the current legs haven't arrived".
  const [legDetails, setLegDetails] = useState<{ key: string; trains: (TrainDetails | null)[] }>({ key: '', trains: [] });

  // Stable dependency for useEffect / useCallback
  const legIds = fetchLegs
    .map(l => `${l.trainId}:${l.date}:${l.dataSource}:${l.boardingCode}:${l.alightingCode}`)
    .join(',');

  const fetchAllLegDetails = useCallback(async (signal?: AbortSignal) => {
    if (fetchLegs.length === 0) return;
    const results = await Promise.all(
      fetchLegs.map(leg =>
        apiService.getTrainDetails(
          leg.trainId,
          leg.date,
          {
            dataSource: leg.dataSource,
            fromStation: leg.boardingCode,
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
    setLegDetails({ key: legIds, trains: results });
    // legIds captures all reactive bits of the legs; including `fetchLegs`
    // directly would needlessly re-fire on equal-but-different references.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [legIds]);

  usePolling(fetchAllLegDetails, [legIds], { enabled: fetchLegs.length > 0 });

  // The trip we render: the full option when we have one, else reconstructed
  // from the compact descriptor once every leg's details have resolved. Results
  // are only trusted when their key matches the legs we're currently showing, so
  // navigating straight to another trip never mixes in the previous one's legs.
  const trip = useMemo<TripOption | null>(() => {
    if (initialTrip) return initialTrip;
    if (descriptor && legDetails.key === legIds && legDetails.trains.length === descriptor.legs.length) {
      return buildTripFromDescriptor(descriptor, legDetails.trains);
    }
    return null;
  }, [initialTrip, descriptor, legDetails, legIds]);

  // Persist view history once per trip identity, once the trip resolves.
  const savedLegIds = useRef('');
  useEffect(() => {
    if (!trip || !legIds || savedLegIds.current === legIds) return;
    savedLegIds.current = legIds;
    storageService.saveViewedTripOption(trip);
  }, [trip, legIds]);

  // Early returns after all hooks
  if (fetchLegs.length === 0) {
    return (
      <div className="max-w-4xl mx-auto">
        <ErrorMessage
          message="Trip details not available. Please search for your trip again."
          onRetry={() => navigate('/departures')}
        />
      </div>
    );
  }

  // Compact descriptor: hold the loading state until the reconstruction is ready.
  if (!trip) {
    return (
      <div className="max-w-4xl mx-auto">
        <LoadingSpinner />
      </div>
    );
  }

  // Per-leg results for the trip on screen; empty (and `loading`) while a
  // freshly-changed set of legs is still being fetched.
  const loading = legDetails.key !== legIds;
  const trains = loading ? [] : legDetails.trains;

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

      {loading ? (
        <LoadingSpinner />
      ) : (
        trip.legs.map((leg, i) => (
          <div key={`${leg.train_id}-${i}`}>
            <LegDetail leg={leg} train={trains[i] ?? null} loading={loading} navigate={navigate} />
            {i < trip.transfers.length && (
              <TransferIndicator transfer={trip.transfers[i]} variant="detail" />
            )}
          </div>
        ))
      )}
    </div>
  );
}
