import { describe, expect, it } from 'vitest';
import { TripOption } from '../types';
import { buildRouteStatusUrl, buildTrainUrl, buildTripUrl, parseTripParam } from './routes';

describe('buildTrainUrl', () => {
  it('builds a route-scoped train URL with query params', () => {
    expect(buildTrainUrl({
      trainId: '3515',
      from: 'TR',
      to: 'NY',
      date: '2025-03-28',
      dataSource: 'NJT',
    })).toBe('/train/3515/TR/NY?date=2025-03-28&data_source=NJT');
  });

  it('builds a minimal train URL when context is absent', () => {
    expect(buildTrainUrl({ trainId: 'A174' })).toBe('/train/A174');
  });

  it('preserves partial route context in query params', () => {
    expect(buildTrainUrl({
      trainId: '3515',
      from: 'TR',
      date: '2025-03-28',
    })).toBe('/train/3515?from=TR&date=2025-03-28');
  });
});

describe('trip URL helpers', () => {
  const trip: TripOption = {
    legs: [
      {
        train_id: '3515',
        journey_date: '2025-03-28',
        line: { code: 'NEC', name: 'Northeast Corridor', color: '#cc5500' },
        data_source: 'NJT',
        destination: 'New York',
        boarding: {
          code: 'TR',
          name: 'Trenton',
          scheduled_time: '2025-03-28T08:00:00-04:00',
        },
        alighting: {
          code: 'SEC',
          name: 'Secaucus',
          scheduled_time: '2025-03-28T08:50:00-04:00',
        },
        is_cancelled: false,
      },
      {
        train_id: 'A174',
        journey_date: '2025-03-28',
        line: { code: 'AMT', name: 'Amtrak', color: '#1f3a93' },
        data_source: 'AMTRAK',
        destination: 'Boston',
        boarding: {
          code: 'SEC',
          name: 'Secaucus',
          scheduled_time: '2025-03-28T09:00:00-04:00',
        },
        alighting: {
          code: 'NYP',
          name: 'New York Penn Station',
          scheduled_time: '2025-03-28T09:15:00-04:00',
        },
        is_cancelled: false,
      },
    ],
    transfers: [
      {
        from_station: { code: 'SEC', name: 'Secaucus' },
        to_station: { code: 'SEC', name: 'Secaucus' },
        walk_minutes: 0,
        same_station: true,
      },
    ],
    departure_time: '2025-03-28T08:00:00-04:00',
    arrival_time: '2025-03-28T09:15:00-04:00',
    total_duration_minutes: 75,
    is_direct: false,
  };

  it('round-trips trip data through the URL query string', () => {
    const url = buildTripUrl(trip);
    const query = url.split('?')[1];
    const params = new URLSearchParams(query);

    expect(parseTripParam(params.get('trip'))).toEqual(trip);
  });

  it('returns null for invalid trip payloads', () => {
    expect(parseTripParam('not-json')).toBeNull();
  });
});

describe('buildRouteStatusUrl', () => {
  it('builds a route status URL with explicit data source context', () => {
    expect(buildRouteStatusUrl({
      from: 'NY',
      to: 'NHV',
      dataSource: 'AMTRAK',
    })).toBe('/route/NY/NHV?data_source=AMTRAK');
  });

  it('builds a route status URL without query params when context is absent', () => {
    expect(buildRouteStatusUrl({
      from: 'NY',
      to: 'NP',
    })).toBe('/route/NY/NP');
  });
});
