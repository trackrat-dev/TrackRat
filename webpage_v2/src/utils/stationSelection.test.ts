import { describe, it, expect } from 'vitest';
import {
  resolveStationSlot,
  buildQuickStations,
  collidingStationNames,
} from './stationSelection';
import { getStationByCode } from '../data/stations';
import { FavoriteStation, Station, TripPair } from '../types';

function favorite(id: string): FavoriteStation {
  return { id, name: getStationByCode(id)?.name ?? id, addedDate: new Date() };
}

function trip(departureCode: string, destinationCode: string, lastUsed: Date): TripPair {
  return {
    id: `${departureCode}-${destinationCode}`,
    departureCode,
    departureName: getStationByCode(departureCode)?.name ?? departureCode,
    destinationCode,
    destinationName: getStationByCode(destinationCode)?.name ?? destinationCode,
    lastUsed,
  };
}

describe('resolveStationSlot', () => {
  it('fills From when From is empty (both slots empty)', () => {
    expect(resolveStationSlot({ hasDeparture: false, hasDestination: false }))
      .toEqual({ action: 'fill', slot: 'from' });
  });

  it('fills From when only To is set', () => {
    // From is still the empty slot, so a tap should fill From — this is the
    // interaction the old handler made impossible once a route was half-built.
    expect(resolveStationSlot({ hasDeparture: false, hasDestination: true }))
      .toEqual({ action: 'fill', slot: 'from' });
  });

  it('fills To when From is set and To is empty', () => {
    expect(resolveStationSlot({ hasDeparture: true, hasDestination: false }))
      .toEqual({ action: 'fill', slot: 'to' });
  });

  it('asks the user to choose when both slots are set', () => {
    expect(resolveStationSlot({ hasDeparture: true, hasDestination: true }))
      .toEqual({ action: 'choose' });
  });
});

describe('buildQuickStations', () => {
  const home = getStationByCode('NY')!;
  const work = getStationByCode('NP')!;

  it('returns nothing when the user has no saved stations or trips', () => {
    expect(buildQuickStations({
      homeStation: null,
      workStation: null,
      favoriteStations: [],
      recentTrips: [],
    })).toEqual([]);
  });

  it('orders Home, then Work, then favorites, then recents', () => {
    const result = buildQuickStations({
      homeStation: home,
      workStation: work,
      favoriteStations: [favorite('HB')],
      recentTrips: [trip('SE', 'MP', new Date('2026-01-02'))],
    });
    expect(result.map((q) => q.role)).toEqual(['home', 'work', 'favorite', 'recent', 'recent']);
    expect(result.map((q) => q.station.code)).toEqual(['NY', 'NP', 'HB', 'SE', 'MP']);
  });

  it('dedupes a station already shown as Home/Work/favorite out of recents', () => {
    const result = buildQuickStations({
      homeStation: home,       // NY
      workStation: work,       // NP
      favoriteStations: [favorite('HB')],
      // Recent trip re-uses NY (home) and TR; NY must not reappear as a recent.
      recentTrips: [trip('NY', 'TR', new Date('2026-01-02'))],
    });
    const codes = result.map((q) => q.station.code);
    expect(codes).toEqual(['NY', 'NP', 'HB', 'TR']);
    expect(codes.filter((c) => c === 'NY')).toHaveLength(1);
  });

  it('caps recents at maxRecents, taking most-recent trips first', () => {
    const result = buildQuickStations({
      homeStation: null,
      workStation: null,
      favoriteStations: [],
      recentTrips: [
        trip('NY', 'NP', new Date('2026-01-05')),
        trip('HB', 'SE', new Date('2026-01-04')),
        trip('MP', 'TR', new Date('2026-01-03')),
      ],
      maxRecents: 3,
    });
    // Flattened departure/destination order, capped at 3: NY, NP, HB.
    expect(result.map((q) => q.station.code)).toEqual(['NY', 'NP', 'HB']);
    expect(result.every((q) => q.role === 'recent')).toBe(true);
  });

  it('skips codes that no longer resolve to a station', () => {
    const result = buildQuickStations({
      homeStation: null,
      workStation: null,
      favoriteStations: [{ id: 'NOT_A_REAL_CODE', name: 'Ghost', addedDate: new Date() }],
      recentTrips: [],
    });
    expect(result).toEqual([]);
  });
});

describe('collidingStationNames', () => {
  it('returns names that appear more than once', () => {
    const stations: Station[] = [
      { code: 'A1', name: 'Union', system: 'NJT' },
      { code: 'A2', name: 'Union', system: 'AMTRAK' },
      { code: 'B1', name: 'Newark', system: 'NJT' },
    ];
    const collisions = collidingStationNames(stations);
    expect(collisions.has('Union')).toBe(true);
    expect(collisions.has('Newark')).toBe(false);
    expect(collisions.size).toBe(1);
  });

  it('returns an empty set when all names are unique', () => {
    const stations: Station[] = [
      { code: 'A1', name: 'Alpha' },
      { code: 'B1', name: 'Beta' },
    ];
    expect(collidingStationNames(stations).size).toBe(0);
  });
});
