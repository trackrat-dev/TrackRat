import { describe, it, expect, beforeEach } from 'vitest';
import { useAppStore } from './appStore';
import { Station } from '../types';

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
    favoriteStations: [],
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
    expect(stored.from.code).toBe('NY');
    expect(stored.to.code).toBe('NP');
  });

  it('does not save last route when only departure set', () => {
    useAppStore.getState().setDeparture(NY);

    expect(localStorage.getItem('trackrat:lastRoute')).toBeNull();
  });

  it('saves when departure set after destination', () => {
    useAppStore.getState().setDestination(NP);
    useAppStore.getState().setDeparture(NY);

    const stored = JSON.parse(localStorage.getItem('trackrat:lastRoute') || 'null');
    expect(stored.from.code).toBe('NY');
    expect(stored.to.code).toBe('NP');
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
