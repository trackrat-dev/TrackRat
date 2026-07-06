import { TransitSystem, TripOption } from '../types';

/** One leg of a trip, in the minimal form a shareable URL can carry. */
export interface TripLegDescriptor {
  dataSource: TransitSystem;
  trainId: string;
  boardingCode: string;
  alightingCode: string;
}

/**
 * The compact, self-contained description of a transfer trip parsed from a
 * `/trip?date&legs&walk` URL. Everything else (times, line, stops, station
 * names) is re-fetched per leg via `getTrainDetails`.
 */
export interface TripDescriptor {
  date: string;
  legs: TripLegDescriptor[];
  /** Walk minutes per transfer junction; length is `legs.length - 1`. */
  walkMinutes: number[];
}

export interface TrainRouteParams {
  trainId: string;
  from?: string;
  to?: string;
  date?: string;
  dataSource?: string;
}

export interface RouteStatusParams {
  from: string;
  to: string;
  dataSource?: TransitSystem | string;
}

export function buildTrainUrl({
  trainId,
  from,
  to,
  date,
  dataSource,
}: TrainRouteParams): string {
  const path = from && to
    ? `/train/${encodeURIComponent(trainId)}/${encodeURIComponent(from)}/${encodeURIComponent(to)}`
    : `/train/${encodeURIComponent(trainId)}`;

  const searchParams = new URLSearchParams();
  if (!(from && to)) {
    if (from) searchParams.set('from', from);
    if (to) searchParams.set('to', to);
  }
  if (date) searchParams.set('date', date);
  if (dataSource) searchParams.set('data_source', dataSource);

  const query = searchParams.toString();
  return query ? `${path}?${query}` : path;
}

/**
 * Emit a compact, shareable trip URL: one `legs` param (comma-separated legs,
 * each `dataSource:trainId:boardingCode:alightingCode`), a single `date`, and a
 * `walk` param of per-transfer walk minutes. `URLSearchParams` percent-encodes
 * the `:`/`,` structural delimiters and any exotic field chars (subway train
 * IDs contain spaces/`+`/`/`); `parseTripLegsParam` reverses it exactly. Every
 * field is re-derivable from `getTrainDetails` except the walk minutes.
 */
export function buildTripUrl(trip: TripOption): string {
  const legs = trip.legs
    .map(leg => `${leg.data_source}:${leg.train_id}:${leg.boarding.code}:${leg.alighting.code}`)
    .join(',');

  const searchParams = new URLSearchParams({
    date: trip.legs[0]?.journey_date ?? '',
    legs,
  });
  if (trip.transfers.length > 0) {
    searchParams.set('walk', trip.transfers.map(t => t.walk_minutes).join(','));
  }
  return `/trip?${searchParams.toString()}`;
}

export function buildRouteStatusUrl({
  from,
  to,
  dataSource,
}: RouteStatusParams): string {
  const path = `/route/${encodeURIComponent(from)}/${encodeURIComponent(to)}`;
  if (!dataSource) return path;

  const searchParams = new URLSearchParams({
    data_source: dataSource,
  });
  return `${path}?${searchParams.toString()}`;
}

/**
 * Parse the compact `/trip?date&legs&walk` format produced by `buildTripUrl`.
 * Returns null for any missing or malformed input so callers can fall back to
 * `location.state` or the legacy param.
 */
export function parseTripLegsParam(params: URLSearchParams): TripDescriptor | null {
  const date = params.get('date');
  const legsRaw = params.get('legs');
  if (!date || !legsRaw) return null;

  const legs: TripLegDescriptor[] = [];
  for (const legStr of legsRaw.split(',')) {
    const parts = legStr.split(':');
    if (parts.length !== 4) return null;
    const [dataSource, trainId, boardingCode, alightingCode] = parts;
    if (!dataSource || !trainId || !boardingCode || !alightingCode) return null;
    legs.push({ dataSource: dataSource as TransitSystem, trainId, boardingCode, alightingCode });
  }
  if (legs.length === 0) return null;

  const walkMinutes = parseWalkMinutes(params.get('walk'), legs.length - 1);
  if (walkMinutes === null) return null;

  return { date, legs, walkMinutes };
}

/** Parse `walk` into exactly `expected` non-negative numbers, else null. */
function parseWalkMinutes(raw: string | null, expected: number): number[] | null {
  if (expected === 0) return raw ? null : [];
  if (!raw) return null;

  const parts = raw.split(',');
  if (parts.length !== expected) return null;

  const minutes: number[] = [];
  for (const part of parts) {
    const value = Number(part);
    if (part === '' || !Number.isFinite(value) || value < 0) return null;
    minutes.push(value);
  }
  return minutes;
}

/**
 * Parse the legacy `?trip=<JSON>` format. Read-only: nothing generates this
 * format anymore, but previously shared links and older localStorage history
 * entries still carry it.
 */
export function parseTripParam(value: string | null): TripOption | null {
  if (!value) return null;

  try {
    const parsed = JSON.parse(value) as TripOption;
    if (!Array.isArray(parsed.legs) || !Array.isArray(parsed.transfers)) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}
