import { describe, it, expect, beforeEach, vi } from 'vitest';
import { storageService } from './storage';
import { TrainDetails } from '../types';

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

function makeMinimalTrain(id: string, fromCode = 'A', toCode = 'B'): TrainDetails {
  return {
    train_id: id,
    journey_date: '2026-04-01',
    line: { code: 'NEC', name: 'Northeast Corridor', color: '#f60' },
    route: { origin: 'Station A', destination: 'Station B', origin_code: fromCode, destination_code: toCode },
    stops: [
      { station: { code: fromCode, name: 'Station A' }, stop_sequence: 1, scheduled_departure: '2026-04-01T08:00:00-04:00', has_departed_station: false },
      { station: { code: toCode, name: 'Station B' }, stop_sequence: 2, scheduled_arrival: '2026-04-01T09:00:00-04:00', has_departed_station: false },
    ],
    data_freshness: { last_updated: '2026-04-01T07:55:00-04:00', age_seconds: 0, update_count: 1, collection_method: null },
    data_source: 'NJT',
    observation_type: 'OBSERVED',
    is_cancelled: false,
    is_completed: false,
  } as TrainDetails;
}

describe('Recent Trips', () => {
  it('returns empty array when no trips stored', () => {
    expect(storageService.getRecentTrips()).toEqual([]);
  });

  it('saves and retrieves a trip', () => {
    storageService.saveRecentTrip({
      departureCode: 'NY',
      departureName: 'New York Penn Station',
      destinationCode: 'NP',
      destinationName: 'Newark Penn Station',
    });

    const trips = storageService.getRecentTrips();
    expect(trips).toHaveLength(1);
    expect(trips[0].departureCode).toBe('NY');
    expect(trips[0].destinationCode).toBe('NP');
    expect(trips[0].id).toBe('NY-NP');
    expect(trips[0].lastUsed).toBeInstanceOf(Date);
  });

  it('updates existing trip instead of duplicating', () => {
    const trip = {
      departureCode: 'NY',
      departureName: 'New York Penn Station',
      destinationCode: 'NP',
      destinationName: 'Newark Penn Station',
    };

    storageService.saveRecentTrip(trip);
    storageService.saveRecentTrip(trip);

    const trips = storageService.getRecentTrips();
    expect(trips).toHaveLength(1);
  });

  it('limits to 10 trips', () => {
    for (let i = 0; i < 15; i++) {
      storageService.saveRecentTrip({
        departureCode: `FROM${i}`,
        departureName: `Station ${i}`,
        destinationCode: `TO${i}`,
        destinationName: `Destination ${i}`,
      });
    }

    const trips = storageService.getRecentTrips();
    expect(trips).toHaveLength(10);
  });

  it('sorts by most recently used', () => {
    storageService.saveRecentTrip({
      departureCode: 'A',
      departureName: 'Station A',
      destinationCode: 'B',
      destinationName: 'Station B',
    });

    // Small delay to ensure different timestamps
    storageService.saveRecentTrip({
      departureCode: 'C',
      departureName: 'Station C',
      destinationCode: 'D',
      destinationName: 'Station D',
    });

    const trips = storageService.getRecentTrips();
    // Most recent should be first
    expect(trips[0].departureCode).toBe('C');
  });

  it('returns empty array on corrupted localStorage data', () => {
    localStorage.setItem('trackrat:recentTrips', 'not-json');

    expect(storageService.getRecentTrips()).toEqual([]);
  });
});

describe('Favorite Stations', () => {
  it('returns empty array when no favorites stored', () => {
    expect(storageService.getFavoriteStations()).toEqual([]);
  });

  it('adds and retrieves a favorite', () => {
    storageService.addFavoriteStation({ id: 'NY', name: 'New York Penn Station' });

    const favs = storageService.getFavoriteStations();
    expect(favs).toHaveLength(1);
    expect(favs[0].id).toBe('NY');
    expect(favs[0].name).toBe('New York Penn Station');
    expect(favs[0].addedDate).toBeInstanceOf(Date);
  });

  it('prevents duplicate favorites', () => {
    storageService.addFavoriteStation({ id: 'NY', name: 'New York Penn Station' });
    storageService.addFavoriteStation({ id: 'NY', name: 'New York Penn Station' });

    expect(storageService.getFavoriteStations()).toHaveLength(1);
  });

  it('removes a favorite by station ID', () => {
    storageService.addFavoriteStation({ id: 'NY', name: 'New York Penn Station' });
    storageService.addFavoriteStation({ id: 'NP', name: 'Newark Penn Station' });

    storageService.removeFavoriteStation('NY');

    const favs = storageService.getFavoriteStations();
    expect(favs).toHaveLength(1);
    expect(favs[0].id).toBe('NP');
  });

  it('handles removing non-existent favorite gracefully', () => {
    storageService.addFavoriteStation({ id: 'NY', name: 'New York Penn Station' });
    storageService.removeFavoriteStation('NONEXISTENT');

    expect(storageService.getFavoriteStations()).toHaveLength(1);
  });

  it('returns empty array on corrupted localStorage data', () => {
    localStorage.setItem('trackrat:favorites', '{invalid');

    expect(storageService.getFavoriteStations()).toEqual([]);
  });
});

describe('Favorite Routes', () => {
  it('adds and retrieves a favorite route', () => {
    storageService.saveFavoriteRoute({
      departureCode: 'NY',
      departureName: 'New York Penn Station',
      destinationCode: 'NP',
      destinationName: 'Newark Penn Station',
    });

    const routes = storageService.getFavoriteRoutes();
    expect(routes).toHaveLength(1);
    expect(routes[0].departureCode).toBe('NY');
    expect(routes[0].destinationCode).toBe('NP');
  });

  it('removes a favorite route', () => {
    storageService.saveFavoriteRoute({
      departureCode: 'NY',
      departureName: 'New York Penn Station',
      destinationCode: 'NP',
      destinationName: 'Newark Penn Station',
    });

    storageService.removeFavoriteRoute('NY-NP');

    expect(storageService.getFavoriteRoutes()).toEqual([]);
  });

  it('limits to 10 favorite routes', () => {
    for (let i = 0; i < 15; i++) {
      storageService.saveFavoriteRoute({
        departureCode: `FROM${i}`,
        departureName: `Station ${i}`,
        destinationCode: `TO${i}`,
        destinationName: `Destination ${i}`,
      });
    }

    expect(storageService.getFavoriteRoutes()).toHaveLength(10);
  });
});

describe('Commute Profile', () => {
  it('stores and retrieves home and work stations', () => {
    storageService.setHomeStation({ code: 'NY', name: 'New York Penn Station' });
    storageService.setWorkStation({ code: 'NP', name: 'Newark Penn Station' });

    expect(storageService.getHomeStation()?.code).toBe('NY');
    expect(storageService.getWorkStation()?.code).toBe('NP');
  });

  it('clears stored home and work stations', () => {
    storageService.setHomeStation({ code: 'NY', name: 'New York Penn Station' });
    storageService.setWorkStation({ code: 'NP', name: 'Newark Penn Station' });

    storageService.setHomeStation(null);
    storageService.setWorkStation(null);

    expect(storageService.getHomeStation()).toBeNull();
    expect(storageService.getWorkStation()).toBeNull();
  });
});

describe('Trip History', () => {
  it('stores viewed trains with replay links', () => {
    storageService.saveViewedTrainTrip(makeMinimalTrain('3515', 'TR', 'NY'));

    const history = storageService.getTripHistory();
    expect(history).toHaveLength(1);
    expect(history[0].href).toContain('/train/3515/TR/NY');
    expect(history[0].viewedAt).toBeInstanceOf(Date);
  });

  it('stores viewed transfer trips with replay links', () => {
    storageService.saveViewedTripOption({
      legs: [
        {
          train_id: '3515',
          journey_date: '2026-04-01',
          line: { code: 'NEC', name: 'Northeast Corridor', color: '#f60' },
          data_source: 'NJT',
          destination: 'Secaucus',
          boarding: {
            code: 'TR',
            name: 'Trenton',
            scheduled_time: '2026-04-01T08:00:00-04:00',
          },
          alighting: {
            code: 'SEC',
            name: 'Secaucus',
            scheduled_time: '2026-04-01T08:50:00-04:00',
          },
          is_cancelled: false,
        },
        {
          train_id: 'A174',
          journey_date: '2026-04-01',
          line: { code: 'AMT', name: 'Amtrak', color: '#1f3a93' },
          data_source: 'AMTRAK',
          destination: 'New York Penn Station',
          boarding: {
            code: 'SEC',
            name: 'Secaucus',
            scheduled_time: '2026-04-01T09:00:00-04:00',
          },
          alighting: {
            code: 'NY',
            name: 'New York Penn Station',
            scheduled_time: '2026-04-01T09:15:00-04:00',
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
      departure_time: '2026-04-01T08:00:00-04:00',
      arrival_time: '2026-04-01T09:15:00-04:00',
      total_duration_minutes: 75,
      is_direct: false,
    });

    const history = storageService.getTripHistory();
    expect(history).toHaveLength(1);
    expect(history[0].kind).toBe('trip');
    expect(history[0].href).toContain('/trip?trip=');
  });

  it('limits to 50 entries', () => {
    for (let i = 0; i < 55; i++) {
      storageService.saveViewedTrainTrip(makeMinimalTrain(`train${i}`));
    }

    expect(storageService.getTripHistory()).toHaveLength(50);
  });

  it('deduplicates by id, keeping most recent view', () => {
    storageService.saveViewedTrainTrip(makeMinimalTrain('3515'));
    storageService.saveViewedTrainTrip(makeMinimalTrain('9999'));
    storageService.saveViewedTrainTrip(makeMinimalTrain('3515'));

    const history = storageService.getTripHistory();
    expect(history).toHaveLength(2);
    expect(history[0].trainId).toBe('3515');
  });
});

describe('Last Route', () => {
  it('returns null when no last route stored', () => {
    expect(storageService.getLastRoute()).toBeNull();
  });

  it('saves and retrieves last route', () => {
    const from = { code: 'NY', name: 'New York Penn Station' };
    const to = { code: 'NP', name: 'Newark Penn Station' };

    storageService.saveLastRoute(from, to);

    const route = storageService.getLastRoute();
    expect(route).toEqual({ from, to });
  });

  it('overwrites previous last route', () => {
    storageService.saveLastRoute(
      { code: 'NY', name: 'New York' },
      { code: 'NP', name: 'Newark' }
    );
    storageService.saveLastRoute(
      { code: 'HB', name: 'Hoboken' },
      { code: 'NY', name: 'New York' }
    );

    const route = storageService.getLastRoute();
    expect(route?.from.code).toBe('HB');
    expect(route?.to.code).toBe('NY');
  });

  it('returns null on corrupted localStorage data', () => {
    localStorage.setItem('trackrat:lastRoute', 'broken');

    expect(storageService.getLastRoute()).toBeNull();
  });
});

describe('Preferred Systems', () => {
  it('returns empty array when no systems stored', () => {
    expect(storageService.getPreferredSystems()).toEqual([]);
  });

  it('saves and retrieves preferred systems', () => {
    storageService.savePreferredSystems(['NJT', 'AMTRAK', 'PATH']);

    const systems = storageService.getPreferredSystems();
    expect(systems).toEqual(['NJT', 'AMTRAK', 'PATH']);
  });

  it('overwrites previous systems', () => {
    storageService.savePreferredSystems(['NJT']);
    storageService.savePreferredSystems(['AMTRAK', 'PATH']);

    expect(storageService.getPreferredSystems()).toEqual(['AMTRAK', 'PATH']);
  });

  it('returns empty array on corrupted data', () => {
    localStorage.setItem('trackrat:systems', '{{bad');

    expect(storageService.getPreferredSystems()).toEqual([]);
  });
});

describe('Schema versioning', () => {
  it('reads legacy unversioned recent trips', () => {
    localStorage.setItem('trackrat:recentTrips', JSON.stringify([
      {
        id: 'NY-NP',
        departureCode: 'NY',
        departureName: 'New York Penn Station',
        destinationCode: 'NP',
        destinationName: 'Newark Penn Station',
        lastUsed: '2026-01-15T00:00:00.000Z',
      },
    ]));

    const trips = storageService.getRecentTrips();
    expect(trips).toHaveLength(1);
    expect(trips[0].departureCode).toBe('NY');
    expect(trips[0].lastUsed).toBeInstanceOf(Date);
  });

  it('reads legacy unversioned last route', () => {
    localStorage.setItem('trackrat:lastRoute', JSON.stringify({
      from: { code: 'NY', name: 'New York' },
      to: { code: 'NP', name: 'Newark' },
    }));

    const route = storageService.getLastRoute();
    expect(route?.from.code).toBe('NY');
    expect(route?.to.code).toBe('NP');
  });

  it('reads legacy unversioned preferred systems', () => {
    localStorage.setItem('trackrat:systems', JSON.stringify(['NJT', 'PATH']));

    expect(storageService.getPreferredSystems()).toEqual(['NJT', 'PATH']);
  });

  it('reads legacy unversioned home station', () => {
    localStorage.setItem('trackrat:homeStation', JSON.stringify({
      code: 'NY',
      name: 'New York Penn Station',
    }));

    expect(storageService.getHomeStation()?.code).toBe('NY');
  });

  it('reads versioned data correctly', () => {
    localStorage.setItem('trackrat:recentTrips', JSON.stringify({
      v: 1,
      data: [{
        id: 'NY-NP',
        departureCode: 'NY',
        departureName: 'New York Penn Station',
        destinationCode: 'NP',
        destinationName: 'Newark Penn Station',
        lastUsed: '2026-01-15T00:00:00.000Z',
      }],
    }));

    const trips = storageService.getRecentTrips();
    expect(trips).toHaveLength(1);
    expect(trips[0].departureCode).toBe('NY');
  });

  it('writes versioned envelope on save', () => {
    storageService.saveLastRoute(
      { code: 'NY', name: 'New York' },
      { code: 'NP', name: 'Newark' }
    );

    const raw = JSON.parse(localStorage.getItem('trackrat:lastRoute')!);
    expect(raw.v).toBe(1);
    expect(raw.data.from.code).toBe('NY');
    expect(raw.data.to.code).toBe('NP');
  });

  it('clears corrupted data and returns null', () => {
    localStorage.setItem('trackrat:lastRoute', 'not-valid-json!!!');

    const route = storageService.getLastRoute();
    expect(route).toBeNull();
    expect(localStorage.getItem('trackrat:lastRoute')).toBeNull();
  });

  it('clears corrupted data and returns empty array for list keys', () => {
    localStorage.setItem('trackrat:recentTrips', '\x00\x01binary');

    const trips = storageService.getRecentTrips();
    expect(trips).toEqual([]);
    expect(localStorage.getItem('trackrat:recentTrips')).toBeNull();
  });
});

describe('QuotaExceededError handling', () => {
  it('evicts oldest entries on quota exceeded for list keys', () => {
    for (let i = 0; i < 8; i++) {
      storageService.saveRecentTrip({
        departureCode: `FROM${i}`,
        departureName: `Station ${i}`,
        destinationCode: `TO${i}`,
        destinationName: `Destination ${i}`,
      });
    }
    expect(storageService.getRecentTrips()).toHaveLength(8);

    let callCount = 0;
    const originalSetItem = localStorage.setItem.bind(localStorage);
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation((key: string, value: string) => {
      callCount++;
      if (callCount === 1) {
        throw new DOMException('quota exceeded', 'QuotaExceededError');
      }
      originalSetItem(key, value);
    });

    storageService.saveRecentTrip({
      departureCode: 'NEW',
      departureName: 'New Station',
      destinationCode: 'DEST',
      destinationName: 'New Dest',
    });

    vi.restoreAllMocks();
    const trips = storageService.getRecentTrips();
    expect(trips.length).toBeGreaterThan(0);
    expect(trips.length).toBeLessThanOrEqual(8);
  });

  it('fails silently on quota exceeded for singleton keys', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('quota exceeded', 'QuotaExceededError');
    });

    expect(() => {
      storageService.saveLastRoute(
        { code: 'NY', name: 'New York' },
        { code: 'NP', name: 'Newark' }
      );
    }).not.toThrow();

    expect(() => {
      storageService.savePreferredSystems(['NJT', 'AMTRAK']);
    }).not.toThrow();

    expect(() => {
      storageService.setHomeStation({ code: 'NY', name: 'New York' });
    }).not.toThrow();
  });

  it('fails silently on quota exceeded for trip history', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('quota exceeded', 'QuotaExceededError');
    });

    expect(() => {
      storageService.saveViewedTrainTrip(makeMinimalTrain('3515'));
    }).not.toThrow();
  });

  it('fails silently when both initial write and eviction retry fail', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('quota exceeded', 'QuotaExceededError');
    });

    expect(() => {
      for (let i = 0; i < 5; i++) {
        storageService.saveRecentTrip({
          departureCode: `FROM${i}`,
          departureName: `Station ${i}`,
          destinationCode: `TO${i}`,
          destinationName: `Destination ${i}`,
        });
      }
    }).not.toThrow();
  });

  it('handles non-quota DOMException errors silently', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('security error', 'SecurityError');
    });

    expect(() => {
      storageService.saveLastRoute(
        { code: 'NY', name: 'New York' },
        { code: 'NP', name: 'Newark' }
      );
    }).not.toThrow();
  });
});
