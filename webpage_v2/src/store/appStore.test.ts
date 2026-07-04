import { describe, it, expect, beforeEach } from 'vitest';
import { useAppStore } from './appStore';
import { Station, TransitSystem } from '../types';
import { storageService } from '../services/storage';

const NY: Station = { code: 'NY', name: 'New York Penn Station' };
const NP: Station = { code: 'NP', name: 'Newark Penn Station' };
const HB: Station = { code: 'HB', name: 'Hoboken' };

beforeEach(() => {
  localStorage.clear();
  // Reset Zustand store to initial state
  useAppStore.setState({
    selectedDeparture: null,
    selectedDestination: null,
    recentTrips: [],
    favoriteRoutes: [],
    favoriteStations: [],
    preferredSystems: [],
    homeStation: null,
    workStation: null,
  });
});

describe('station selection', () => {
  it('sets departure station', () => {
    useAppStore.getState().setDeparture(NY);
    expect(useAppStore.getState().selectedDeparture).toEqual(NY);
  });

  it('sets destination station', () => {
    useAppStore.getState().setDestination(NP);
    expect(useAppStore.getState().selectedDestination).toEqual(NP);
  });

  it('clears departure when set to null', () => {
    useAppStore.getState().setDeparture(NY);
    useAppStore.getState().setDeparture(null);
    expect(useAppStore.getState().selectedDeparture).toBeNull();
  });

  it('saves last route to localStorage when both stations set', () => {
    useAppStore.getState().setDeparture(NY);
    useAppStore.getState().setDestination(NP);

    const stored = JSON.parse(localStorage.getItem('trackrat:lastRoute') || 'null');
    expect(stored.data.from.code).toBe('NY');
    expect(stored.data.to.code).toBe('NP');
  });

  it('does not save last route when only departure set', () => {
    useAppStore.getState().setDeparture(NY);

    expect(localStorage.getItem('trackrat:lastRoute')).toBeNull();
  });

  it('saves when departure set after destination', () => {
    useAppStore.getState().setDestination(NP);
    useAppStore.getState().setDeparture(NY);

    const stored = JSON.parse(localStorage.getItem('trackrat:lastRoute') || 'null');
    expect(stored.data.from.code).toBe('NY');
    expect(stored.data.to.code).toBe('NP');
  });
});

describe('loadLastRoute', () => {
  it('restores last route from localStorage', () => {
    localStorage.setItem('trackrat:lastRoute', JSON.stringify({
      from: { code: 'NY', name: 'New York Penn Station' },
      to: { code: 'NP', name: 'Newark Penn Station' },
    }));

    useAppStore.getState().loadLastRoute();

    expect(useAppStore.getState().selectedDeparture?.code).toBe('NY');
    expect(useAppStore.getState().selectedDestination?.code).toBe('NP');
  });

  it('does not restore if departure already selected', () => {
    localStorage.setItem('trackrat:lastRoute', JSON.stringify({
      from: { code: 'NY', name: 'New York' },
      to: { code: 'NP', name: 'Newark' },
    }));

    useAppStore.getState().setDeparture(HB);
    useAppStore.getState().loadLastRoute();

    // Should keep HB, not restore NY
    expect(useAppStore.getState().selectedDeparture?.code).toBe('HB');
  });

  it('does nothing when no last route stored', () => {
    useAppStore.getState().loadLastRoute();

    expect(useAppStore.getState().selectedDeparture).toBeNull();
    expect(useAppStore.getState().selectedDestination).toBeNull();
  });
});

describe('recent trips', () => {
  it('adds a trip and loads into state', () => {
    useAppStore.getState().addRecentTrip(NY, NP);

    const trips = useAppStore.getState().recentTrips;
    expect(trips).toHaveLength(1);
    expect(trips[0].departureCode).toBe('NY');
    expect(trips[0].destinationCode).toBe('NP');
  });

  it('loadRecentTrips syncs from localStorage', () => {
    // Manually write to localStorage
    localStorage.setItem('trackrat:recentTrips', JSON.stringify([
      { id: 'NY-NP', departureCode: 'NY', departureName: 'New York', destinationCode: 'NP', destinationName: 'Newark', lastUsed: new Date().toISOString() },
    ]));

    useAppStore.getState().loadRecentTrips();

    expect(useAppStore.getState().recentTrips).toHaveLength(1);
  });
});

describe('favorites', () => {
  it('adds a favorite and loads into state', () => {
    useAppStore.getState().addFavorite(NY);

    const favs = useAppStore.getState().favoriteStations;
    expect(favs).toHaveLength(1);
    expect(favs[0].id).toBe('NY');
    expect(favs[0].name).toBe('New York Penn Station');
  });

  it('removes a favorite', () => {
    useAppStore.getState().addFavorite(NY);
    useAppStore.getState().addFavorite(NP);
    useAppStore.getState().removeFavorite('NY');

    const favs = useAppStore.getState().favoriteStations;
    expect(favs).toHaveLength(1);
    expect(favs[0].id).toBe('NP');
  });

  it('loadFavorites syncs from localStorage', () => {
    localStorage.setItem('trackrat:favorites', JSON.stringify([
      { id: 'HB', name: 'Hoboken', addedDate: new Date().toISOString() },
    ]));

    useAppStore.getState().loadFavorites();

    expect(useAppStore.getState().favoriteStations).toHaveLength(1);
    expect(useAppStore.getState().favoriteStations[0].id).toBe('HB');
  });
});

describe('favorite routes and commute profile', () => {
  it('adds a favorite route and loads it into state', () => {
    useAppStore.getState().addFavoriteRoute(NY, NP);

    const routes = useAppStore.getState().favoriteRoutes;
    expect(routes).toHaveLength(1);
    expect(routes[0].departureCode).toBe('NY');
    expect(routes[0].destinationCode).toBe('NP');
  });

  it('stores home and work stations', () => {
    useAppStore.getState().setHomeStation(NY);
    useAppStore.getState().setWorkStation(NP);

    expect(useAppStore.getState().homeStation?.code).toBe('NY');
    expect(useAppStore.getState().workStation?.code).toBe('NP');
  });

  it('treats empty preferred systems as all-on when toggling a chip', () => {
    useAppStore.getState().toggleSystem('NJT');

    expect(useAppStore.getState().preferredSystems).not.toContain('NJT');
    expect(useAppStore.getState().preferredSystems).toContain('AMTRAK');
  });

  it('never reintroduces a disabled system when toggling from the all-on default', () => {
    // Empty preferredSystems = all-on; the materialized baseline must exclude
    // disabled systems so toggling can't resurface one.
    useAppStore.getState().toggleSystem('NJT');
    const result = useAppStore.getState().preferredSystems;
    for (const disabled of ['BART', 'WMATA', 'MBTA', 'METRA'] as TransitSystem[]) {
      expect(result).not.toContain(disabled);
    }
  });

  it('strips disabled systems from a persisted selection on load', () => {
    storageService.savePreferredSystems(
      ['NJT', 'BART', 'SUBWAY', 'WMATA'] as TransitSystem[],
    );
    useAppStore.getState().loadPreferredSystems();
    expect(useAppStore.getState().preferredSystems).toEqual(['NJT', 'SUBWAY']);
  });
});
