import { TrainDetails, TripHistoryEntry, TripOption, TripPair, FavoriteStation, TransitSystem, Station } from '../types';
import { buildTrainUrl, buildTripUrl } from '../utils/routes';

const RECENT_TRIPS_KEY = 'trackrat:recentTrips';
const FAVORITE_ROUTES_KEY = 'trackrat:favoriteRoutes';
const FAVORITES_KEY = 'trackrat:favorites';
const LAST_ROUTE_KEY = 'trackrat:lastRoute';
const SYSTEMS_KEY = 'trackrat:systems';
const HOME_STATION_KEY = 'trackrat:homeStation';
const WORK_STATION_KEY = 'trackrat:workStation';
const TRIP_HISTORY_KEY = 'trackrat:tripHistory';

const MAX_RECENT_TRIPS = 10;
const MAX_FAVORITE_ROUTES = 10;
const MAX_TRIP_HISTORY = 50;

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

  // Favorite Routes
  getFavoriteRoutes(): TripPair[] {
    try {
      const data = localStorage.getItem(FAVORITE_ROUTES_KEY);
      if (!data) return [];
      const routes = JSON.parse(data);
      return routes.map((route: TripPair) => ({
        ...route,
        lastUsed: new Date(route.lastUsed),
      }));
    } catch {
      return [];
    }
  }

  saveFavoriteRoute(route: Omit<TripPair, 'id' | 'lastUsed'>): void {
    const routes = this.getFavoriteRoutes();
    const routeId = `${route.departureCode}-${route.destinationCode}`;
    const updatedRoutes = [
      {
        id: routeId,
        ...route,
        lastUsed: new Date(),
      },
      ...routes.filter(existing => existing.id !== routeId),
    ].slice(0, MAX_FAVORITE_ROUTES);

    localStorage.setItem(FAVORITE_ROUTES_KEY, JSON.stringify(updatedRoutes));
  }

  removeFavoriteRoute(routeId: string): void {
    const routes = this.getFavoriteRoutes();
    const filtered = routes.filter(route => route.id !== routeId);
    localStorage.setItem(FAVORITE_ROUTES_KEY, JSON.stringify(filtered));
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

  // Commute Profile
  getHomeStation(): Station | null {
    return this.getStoredStation(HOME_STATION_KEY);
  }

  setHomeStation(station: Station | null): void {
    this.setStoredStation(HOME_STATION_KEY, station);
  }

  getWorkStation(): Station | null {
    return this.getStoredStation(WORK_STATION_KEY);
  }

  setWorkStation(station: Station | null): void {
    this.setStoredStation(WORK_STATION_KEY, station);
  }

  // Trip History
  getTripHistory(): TripHistoryEntry[] {
    try {
      const data = localStorage.getItem(TRIP_HISTORY_KEY);
      if (!data) return [];
      const entries = JSON.parse(data);
      return entries.map((entry: TripHistoryEntry) => ({
        ...entry,
        viewedAt: new Date(entry.viewedAt),
      }));
    } catch {
      return [];
    }
  }

  saveViewedTrainTrip(train: TrainDetails, routeContext?: { fromCode?: string; toCode?: string }): void {
    const departureCode = routeContext?.fromCode || train.route.origin_code;
    const destinationCode = routeContext?.toCode || train.route.destination_code;
    const departureStop = train.stops.find((stop) => stop.station.code === departureCode);
    const destinationStop = train.stops.find((stop) => stop.station.code === destinationCode);

    this.saveTripHistoryEntry({
      id: `train:${train.train_id}:${train.journey_date}:${departureCode}:${destinationCode}`,
      kind: 'train',
      href: buildTrainUrl({
        trainId: train.train_id,
        from: departureCode,
        to: destinationCode,
        date: train.journey_date,
        dataSource: train.data_source,
      }),
      departureCode,
      departureName: departureStop?.station.name || train.route.origin,
      destinationCode,
      destinationName: destinationStop?.station.name || train.route.destination,
      lineName: train.line.name,
      dataSource: train.data_source,
      trainId: train.train_id,
      journeyDate: train.journey_date,
      scheduledDeparture: departureStop?.scheduled_departure || null,
      scheduledArrival: destinationStop?.scheduled_arrival || null,
      totalDurationMinutes: getDurationMinutes(
        departureStop?.scheduled_departure || null,
        destinationStop?.scheduled_arrival || null
      ),
      transferCount: 0,
    });
  }

  saveViewedTripOption(trip: TripOption): void {
    const firstLeg = trip.legs[0];
    const lastLeg = trip.legs[trip.legs.length - 1];
    if (!firstLeg || !lastLeg) return;

    this.saveTripHistoryEntry({
      id: `trip:${firstLeg.boarding.code}:${lastLeg.alighting.code}:${trip.departure_time}:${trip.arrival_time}:${trip.legs.map((leg) => `${leg.train_id}:${leg.journey_date}`).join('|')}`,
      kind: 'trip',
      href: buildTripUrl(trip),
      departureCode: firstLeg.boarding.code,
      departureName: firstLeg.boarding.name,
      destinationCode: lastLeg.alighting.code,
      destinationName: lastLeg.alighting.name,
      lineName: trip.legs.length === 1 ? firstLeg.line.name : `${firstLeg.line.name} + ${trip.legs.length - 1} more`,
      dataSource: trip.legs.length === 1 ? firstLeg.data_source : null,
      trainId: trip.legs.length === 1 ? firstLeg.train_id : null,
      journeyDate: firstLeg.journey_date,
      scheduledDeparture: trip.departure_time,
      scheduledArrival: trip.arrival_time,
      totalDurationMinutes: trip.total_duration_minutes,
      transferCount: trip.transfers.length,
    });
  }

  private getStoredStation(key: string): Station | null {
    try {
      const data = localStorage.getItem(key);
      return data ? JSON.parse(data) : null;
    } catch {
      return null;
    }
  }

  private setStoredStation(key: string, station: Station | null): void {
    if (station) {
      localStorage.setItem(key, JSON.stringify(station));
      return;
    }
    localStorage.removeItem(key);
  }

  private saveTripHistoryEntry(entry: Omit<TripHistoryEntry, 'viewedAt'>): void {
    try {
      const entries = this.getTripHistory();
      const updatedEntries = [
        {
          ...entry,
          viewedAt: new Date(),
        },
        ...entries.filter((existing) => existing.id !== entry.id),
      ].slice(0, MAX_TRIP_HISTORY);

      localStorage.setItem(TRIP_HISTORY_KEY, JSON.stringify(updatedEntries));
    } catch {
      // Ignore localStorage errors so trip viewing still works
    }
  }
}

export const storageService = new StorageService();

function getDurationMinutes(start: string | null, end: string | null): number | null {
  if (!start || !end) return null;

  const durationMs = new Date(end).getTime() - new Date(start).getTime();
  if (Number.isNaN(durationMs) || durationMs < 0) return null;

  return Math.round(durationMs / 60000);
}
