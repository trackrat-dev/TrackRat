import { create } from 'zustand';
import { Station, TripPair, FavoriteStation, TransitSystem } from '../types';
import { storageService } from '../services/storage';

interface AppState {
  // Journey Selection
  selectedDeparture: Station | null;
  selectedDestination: Station | null;

  // User Preferences
  recentTrips: TripPair[];
  favoriteStations: FavoriteStation[];
  preferredSystems: TransitSystem[];

  // Actions
  setDeparture: (station: Station | null) => void;
  setDestination: (station: Station | null) => void;
  loadLastRoute: () => void;

  // Recent Trips
  addRecentTrip: (from: Station, to: Station) => void;
  loadRecentTrips: () => void;

  // Favorites
  addFavorite: (station: Station) => void;
  removeFavorite: (stationId: string) => void;
  loadFavorites: () => void;

  // System Preferences
  toggleSystem: (system: TransitSystem) => void;
  loadPreferredSystems: () => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  // Initial State
  selectedDeparture: null,
  selectedDestination: null,
  recentTrips: [],
  favoriteStations: [],
  preferredSystems: [],

  // Actions
  setDeparture: (station) => {
    set({ selectedDeparture: station });
    const dest = get().selectedDestination;
    if (station && dest) {
      storageService.saveLastRoute(
        { code: station.code, name: station.name },
        { code: dest.code, name: dest.name }
      );
    }
  },

  setDestination: (station) => {
    set({ selectedDestination: station });
    const dep = get().selectedDeparture;
    if (dep && station) {
      storageService.saveLastRoute(
        { code: dep.code, name: dep.name },
        { code: station.code, name: station.name }
      );
    }
  },

  loadLastRoute: () => {
    const { selectedDeparture, selectedDestination } = get();
    // Only restore if no selections already made
    if (selectedDeparture || selectedDestination) return;

    const lastRoute = storageService.getLastRoute();
    if (lastRoute) {
      set({
        selectedDeparture: { code: lastRoute.from.code, name: lastRoute.from.name },
        selectedDestination: { code: lastRoute.to.code, name: lastRoute.to.name },
      });
    }
  },

  // Recent Trips
  addRecentTrip: (from, to) => {
    storageService.saveRecentTrip({
      departureCode: from.code,
      departureName: from.name,
      destinationCode: to.code,
      destinationName: to.name,
    });
    get().loadRecentTrips();
  },

  loadRecentTrips: () => {
    const trips = storageService.getRecentTrips();
    set({ recentTrips: trips });
  },

  // Favorites
  addFavorite: (station) => {
    storageService.addFavoriteStation({
      id: station.code,
      name: station.name,
    });
    get().loadFavorites();
  },

  removeFavorite: (stationId) => {
    storageService.removeFavoriteStation(stationId);
    get().loadFavorites();
  },

  loadFavorites: () => {
    const favorites = storageService.getFavoriteStations();
    set({ favoriteStations: favorites });
  },

  // System Preferences
  toggleSystem: (system) => {
    const current = get().preferredSystems;
    const updated = current.includes(system)
      ? current.filter(s => s !== system)
      : [...current, system];
    set({ preferredSystems: updated });
    storageService.savePreferredSystems(updated);
  },

  loadPreferredSystems: () => {
    const systems = storageService.getPreferredSystems();
    set({ preferredSystems: systems });
  },
}));
