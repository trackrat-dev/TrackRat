import { create } from 'zustand';
import { Station, TripPair, FavoriteStation } from '../types';
import { storageService } from '../services/storage';

interface AppState {
  // Journey Selection
  selectedDeparture: Station | null;
  selectedDestination: Station | null;

  // User Preferences
  recentTrips: TripPair[];
  favoriteStations: FavoriteStation[];

  // Actions
  setDeparture: (station: Station | null) => void;
  setDestination: (station: Station | null) => void;
  setRoute: (from: Station, to: Station) => void;
  clearRoute: () => void;

  // Recent Trips
  addRecentTrip: (from: Station, to: Station) => void;
  loadRecentTrips: () => void;

  // Favorites
  addFavorite: (station: Station) => void;
  removeFavorite: (stationId: string) => void;
  loadFavorites: () => void;
  isFavorite: (stationId: string) => boolean;
}

export const useAppStore = create<AppState>((set, get) => ({
  // Initial State
  selectedDeparture: null,
  selectedDestination: null,
  recentTrips: [],
  favoriteStations: [],

  // Actions
  setDeparture: (station) => {
    set({ selectedDeparture: station });
  },

  setDestination: (station) => {
    set({ selectedDestination: station });
  },

  setRoute: (from, to) => {
    set({
      selectedDeparture: from,
      selectedDestination: to,
    });
    storageService.saveLastRoute(
      { code: from.code, name: from.name },
      { code: to.code, name: to.name }
    );
  },

  clearRoute: () => {
    set({
      selectedDeparture: null,
      selectedDestination: null,
    });
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

  isFavorite: (stationId) => {
    return storageService.isFavorite(stationId);
  },
}));
