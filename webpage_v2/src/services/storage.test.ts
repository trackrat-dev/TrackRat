import { describe, it, expect, beforeEach } from 'vitest';
import { storageService } from './storage';

beforeEach(() => {
  localStorage.clear();
});

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
