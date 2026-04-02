import { describe, expect, it } from 'vitest';
import { TripPair } from '../types';
import { getSuggestedRoute } from './ratsense';

const homeStation = { code: 'OG', name: 'Orange' };
const workStation = { code: 'NY', name: 'New York Penn Station' };

function trip(overrides: Partial<TripPair> = {}): TripPair {
  return {
    id: 'OG-NY',
    departureCode: 'OG',
    departureName: 'Orange',
    destinationCode: 'NY',
    destinationName: 'New York Penn Station',
    lastUsed: new Date('2026-04-01T08:45:00-04:00'),
    ...overrides,
  };
}

describe('getSuggestedRoute', () => {
  it('prefers a very recent trip', () => {
    const suggestion = getSuggestedRoute({
      homeStation,
      workStation,
      recentTrips: [trip()],
      now: new Date('2026-04-01T08:55:00-04:00'),
    });

    expect(suggestion?.reason).toBe('Continue your recent trip');
    expect(suggestion?.departure.code).toBe('OG');
    expect(suggestion?.destination.code).toBe('NY');
  });

  it('suggests home to work in the morning', () => {
    const suggestion = getSuggestedRoute({
      homeStation,
      workStation,
      recentTrips: [],
      now: new Date('2026-04-01T08:30:00-04:00'),
    });

    expect(suggestion?.reason).toBe('Morning commute');
    expect(suggestion?.departure.code).toBe('OG');
    expect(suggestion?.destination.code).toBe('NY');
  });

  it('suggests work to home in the evening', () => {
    const suggestion = getSuggestedRoute({
      homeStation,
      workStation,
      recentTrips: [],
      now: new Date('2026-04-01T18:00:00-04:00'),
    });

    expect(suggestion?.reason).toBe('Evening commute');
    expect(suggestion?.departure.code).toBe('NY');
    expect(suggestion?.destination.code).toBe('OG');
  });
});
