import { describe, expect, it } from 'vitest';
import { TripOption } from '../types';
import { buildDeparturesUrl, buildRouteStatusUrl, buildTrainUrl, buildTripUrl, parseLineCodes, parseTripLegsParam, parseTripParam } from './routes';

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

  const paramsOf = (url: string) => new URLSearchParams(url.split('?')[1]);

  it('builds a compact, self-contained trip URL', () => {
    const url = buildTripUrl(trip);
    const params = paramsOf(url);

    expect(url.startsWith('/trip?')).toBe(true);
    expect(url.length).toBeLessThan(200);
    expect(params.get('date')).toBe('2025-03-28');
    expect(params.get('legs')).toBe('NJT:3515:TR:SEC,AMTRAK:A174:SEC:NYP');
    expect(params.get('walk')).toBe('0');
  });

  it('round-trips a trip through the compact legs format', () => {
    expect(parseTripLegsParam(paramsOf(buildTripUrl(trip)))).toEqual({
      date: '2025-03-28',
      legs: [
        { dataSource: 'NJT', trainId: '3515', boardingCode: 'TR', alightingCode: 'SEC' },
        { dataSource: 'AMTRAK', trainId: 'A174', boardingCode: 'SEC', alightingCode: 'NYP' },
      ],
      walkMinutes: [0],
    });
  });

  it('encodes and parses one walk value per transfer junction', () => {
    const walkedTrip: TripOption = {
      ...trip,
      transfers: [{ ...trip.transfers[0], walk_minutes: 7, same_station: false }],
    };
    expect(paramsOf(buildTripUrl(walkedTrip)).get('walk')).toBe('7');

    const twoTransfers = new URLSearchParams(
      'date=2025-03-28&legs=NJT:1:A:B,PATH:2:B:C,AMTRAK:3:C:D&walk=0,7'
    );
    expect(parseTripLegsParam(twoTransfers)?.walkMinutes).toEqual([0, 7]);
  });

  it('parses a direct (single-leg) trip with no walk param', () => {
    const single = new URLSearchParams('date=2025-03-28&legs=NJT:3515:TR:NYP');
    expect(parseTripLegsParam(single)).toEqual({
      date: '2025-03-28',
      legs: [{ dataSource: 'NJT', trainId: '3515', boardingCode: 'TR', alightingCode: 'NYP' }],
      walkMinutes: [],
    });
  });

  it('returns null for malformed compact legs', () => {
    // Missing date / missing legs
    expect(parseTripLegsParam(new URLSearchParams('legs=NJT:3515:TR:SEC'))).toBeNull();
    expect(parseTripLegsParam(new URLSearchParams('date=2025-03-28'))).toBeNull();
    // Wrong field count in a leg
    expect(parseTripLegsParam(new URLSearchParams('date=2025-03-28&legs=NJT:3515:TR'))).toBeNull();
    expect(parseTripLegsParam(new URLSearchParams('date=2025-03-28&legs=NJT:3515:TR:SEC:EXTRA'))).toBeNull();
    // Empty field in a leg
    expect(parseTripLegsParam(new URLSearchParams('date=2025-03-28&legs=NJT::TR:SEC'))).toBeNull();
    // Walk count does not match transfer count
    expect(parseTripLegsParam(new URLSearchParams('date=2025-03-28&legs=NJT:1:A:B,PATH:2:B:C&walk=0,1'))).toBeNull();
    expect(parseTripLegsParam(new URLSearchParams('date=2025-03-28&legs=NJT:1:A:B,PATH:2:B:C'))).toBeNull();
    // Non-numeric / negative walk
    expect(parseTripLegsParam(new URLSearchParams('date=2025-03-28&legs=NJT:1:A:B,PATH:2:B:C&walk=x'))).toBeNull();
    expect(parseTripLegsParam(new URLSearchParams('date=2025-03-28&legs=NJT:1:A:B,PATH:2:B:C&walk=-1'))).toBeNull();
    // Walk present on a single-leg (zero-transfer) trip
    expect(parseTripLegsParam(new URLSearchParams('date=2025-03-28&legs=NJT:3515:TR:NYP&walk=3'))).toBeNull();
  });

  it('still parses legacy ?trip=<JSON> links', () => {
    const legacyUrl = `/trip?trip=${encodeURIComponent(JSON.stringify(trip))}`;
    expect(parseTripParam(paramsOf(legacyUrl).get('trip'))).toEqual(trip);
  });

  it('returns null for invalid legacy trip payloads', () => {
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

describe('buildDeparturesUrl', () => {
  // Unscoped links must stay byte-identical to the path every other caller
  // already produces, or ordinary station-pair boards would start taking the
  // line-scoped code path (issue #1625).
  it('builds the plain station-pair path when no scope is given', () => {
    expect(buildDeparturesUrl({ from: 'TR', to: 'NY' })).toBe('/trains/TR/NY');
  });

  it('omits the query entirely for an empty lines array', () => {
    expect(buildDeparturesUrl({ from: 'HB', to: 'SF', lines: [] })).toBe('/trains/HB/SF');
  });

  it('carries line codes and data source so the scope survives reload and sharing', () => {
    expect(buildDeparturesUrl({
      from: 'HB',
      to: 'SF',
      dataSource: 'NJT',
      lines: ['MA', 'Ma'],
    })).toBe('/trains/HB/SF?data_source=NJT&lines=MA%2CMa');
  });

  it('distinguishes two lines that share the same terminal stations', () => {
    const main = buildDeparturesUrl({ from: 'HB', to: 'SF', dataSource: 'NJT', lines: ['MA', 'Ma'] });
    const bergen = buildDeparturesUrl({ from: 'HB', to: 'SF', dataSource: 'NJT', lines: ['BE', 'Be'] });
    expect(main).not.toBe(bergen);
  });

  it('emits a scope-only query when the data source is unknown', () => {
    expect(buildDeparturesUrl({ from: 'HB', to: 'SF', lines: ['MA'] }))
      .toBe('/trains/HB/SF?lines=MA');
  });

  it('percent-encodes station codes', () => {
    expect(buildDeparturesUrl({ from: 'A/B', to: 'NY' })).toBe('/trains/A%2FB/NY');
  });

  it('round-trips through parseLineCodes', () => {
    // The URL is only useful if the page can read back exactly what the link
    // wrote — encoding the comma and re-splitting it must be lossless.
    const url = buildDeparturesUrl({ from: 'HB', to: 'SF', dataSource: 'NJT', lines: ['MA', 'Ma'] });
    const params = new URLSearchParams(url.split('?')[1]);
    expect(parseLineCodes(params.get('lines'))).toEqual(['MA', 'Ma']);
    expect(params.get('data_source')).toBe('NJT');
  });
});

describe('parseLineCodes', () => {
  it('splits a comma-separated value', () => {
    expect(parseLineCodes('MA,Ma')).toEqual(['MA', 'Ma']);
  });

  it('trims surrounding whitespace on each code', () => {
    expect(parseLineCodes(' MA , Ma ')).toEqual(['MA', 'Ma']);
  });

  // An empty or blank param must read as "no filter", not as a filter on the
  // empty string — the latter would be sent to the API and match nothing.
  it.each([
    ['empty string', ''],
    ['only commas', ',,'],
    ['only whitespace', '  '],
    ['null', null],
    ['undefined', undefined],
  ])('returns no codes for %s', (_label, raw) => {
    expect(parseLineCodes(raw)).toEqual([]);
  });

  it('drops blank entries but keeps the real ones', () => {
    expect(parseLineCodes('MA,,Ma,')).toEqual(['MA', 'Ma']);
  });
});
