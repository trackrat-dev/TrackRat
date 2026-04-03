import { TransitSystem, TripOption } from '../types';

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

export function buildTripUrl(trip: TripOption): string {
  const searchParams = new URLSearchParams({
    trip: JSON.stringify(trip),
  });
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
