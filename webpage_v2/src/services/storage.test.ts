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
    storageService.saveViewedTrainTrip({
      train_id: '3515',
      journey_date: '2026-04-01',
      line: { code: 'NEC', name: 'Northeast Corridor', color: '#f60' },
      route: {
        origin: 'Trenton',
        destination: 'New York Penn Station',
        origin_code: 'TR',
        destination_code: 'NY',
      },
      stops: [
        {
          station: { code: 'TR', name: 'Trenton' },
          stop_sequence: 1,
          scheduled_departure: '2026-04-01T08:00:00-04:00',
          has_departed_station: false,
        },
        {
          station: { code: 'NY', name: 'New York Penn Station' },
          stop_sequence: 2,
          scheduled_arrival: '2026-04-01T09:00:00-04:00',
          has_departed_station: false,
        },
      ],
      data_freshness: { last_updated: '2026-04-01T07:55:00-04:00', age_seconds: 0, update_count: 1, collection_method: null },
      data_source: 'NJT',
      observation_type: 'OBSERVED',
      is_cancelled: false,
      is_completed: false,
    });

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
