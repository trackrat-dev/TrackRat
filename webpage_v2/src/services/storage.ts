import { TripPair, FavoriteStation, TransitSystem } from '../types';

const RECENT_TRIPS_KEY = 'trackrat:recentTrips';
const FAVORITES_KEY = 'trackrat:favorites';
const LAST_ROUTE_KEY = 'trackrat:lastRoute';
const SYSTEMS_KEY = 'trackrat:systems';

const MAX_RECENT_TRIPS = 10;

class StorageService {
  // Recent Trips
  getRecentTrips(): TripPair[] {
    try {
      const data = localStorage.getItem(RECENT_TRIPS_KEY);
      if (!data) return [];
      const trips = JSON.parse(data);
      return trips.map((trip: TripPair) => ({
        ...trip,
        lastUsed: new Date(trip.lastUsed),
      }));
    } catch {
      return [];
    }
  }

  saveRecentTrip(trip: Omit<TripPair, 'id' | 'lastUsed'>): void {
    const trips = this.getRecentTrips();

    // Check if trip already exists
    const existingIndex = trips.findIndex(
      t => t.departureCode === trip.departureCode && t.destinationCode === trip.destinationCode
    );

    const newTrip: TripPair = {
      id: `${trip.departureCode}-${trip.destinationCode}`,
      ...trip,
      lastUsed: new Date(),
    };

    if (existingIndex >= 0) {
      // Update existing trip
      trips[existingIndex] = newTrip;
    } else {
      // Add new trip at the beginning
      trips.unshift(newTrip);
    }

    // Keep only MAX_RECENT_TRIPS
    const trimmedTrips = trips.slice(0, MAX_RECENT_TRIPS);

    // Sort by lastUsed (most recent first)
    trimmedTrips.sort((a, b) => b.lastUsed.getTime() - a.lastUsed.getTime());

    localStorage.setItem(RECENT_TRIPS_KEY, JSON.stringify(trimmedTrips));
  }

  // Favorite Stations
  getFavoriteStations(): FavoriteStation[] {
    try {
      const data = localStorage.getItem(FAVORITES_KEY);
      if (!data) return [];
      const favorites = JSON.parse(data);
      return favorites.map((fav: FavoriteStation) => ({
        ...fav,
        addedDate: new Date(fav.addedDate),
      }));
    } catch {
      return [];
    }
  }

  addFavoriteStation(station: Omit<FavoriteStation, 'addedDate'>): void {
    const favorites = this.getFavoriteStations();

    // Check if already exists
    if (favorites.some(f => f.id === station.id)) {
      return;
    }

    const newFavorite: FavoriteStation = {
      ...station,
      addedDate: new Date(),
    };

    favorites.push(newFavorite);
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(favorites));
  }

  removeFavoriteStation(stationId: string): void {
    const favorites = this.getFavoriteStations();
    const filtered = favorites.filter(f => f.id !== stationId);
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(filtered));
  }

  // Last Selected Route
  getLastRoute(): { from: { code: string; name: string }; to: { code: string; name: string } } | null {
    try {
      const data = localStorage.getItem(LAST_ROUTE_KEY);
      return data ? JSON.parse(data) : null;
    } catch {
      return null;
    }
  }

  saveLastRoute(from: { code: string; name: string }, to: { code: string; name: string }): void {
    localStorage.setItem(LAST_ROUTE_KEY, JSON.stringify({ from, to }));
  }

  // Preferred Transit Systems
  getPreferredSystems(): TransitSystem[] {
    try {
      const data = localStorage.getItem(SYSTEMS_KEY);
      return data ? JSON.parse(data) : [];
    } catch {
      return [];
    }
  }

  savePreferredSystems(systems: TransitSystem[]): void {
    localStorage.setItem(SYSTEMS_KEY, JSON.stringify(systems));
  }
}

export const storageService = new StorageService();
