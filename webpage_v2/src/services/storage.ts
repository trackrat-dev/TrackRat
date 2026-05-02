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

const STORAGE_VERSION = 1;

function evictOldest<T>(arr: T[]): T[] {
  return arr.slice(0, Math.ceil(arr.length * 0.75));
}

class StorageService {
  private readData<T>(key: string): T | null {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object' && typeof parsed.v === 'number' && 'data' in parsed) {
        return parsed.data as T;
      }
      return parsed as T;
    } catch {
      try { localStorage.removeItem(key); } catch { /* storage inaccessible */ }
      return null;
    }
  }

  private writeData<T>(key: string, data: T, onQuotaExceeded?: (data: T) => T): void {
    try {
      localStorage.setItem(key, JSON.stringify({ v: STORAGE_VERSION, data }));
    } catch (err) {
      if (err instanceof DOMException && err.name === 'QuotaExceededError' && onQuotaExceeded) {
        try {
          localStorage.setItem(key, JSON.stringify({ v: STORAGE_VERSION, data: onQuotaExceeded(data) }));
          return;
        } catch { /* retry failed — storage fully unavailable */ }
      }
    }
  }

  // Recent Trips
  getRecentTrips(): TripPair[] {
    const trips = this.readData<TripPair[]>(RECENT_TRIPS_KEY);
    if (!Array.isArray(trips)) return [];
    return trips.map((trip) => ({
      ...trip,
      lastUsed: new Date(trip.lastUsed),
    }));
  }

  saveRecentTrip(trip: Omit<TripPair, 'id' | 'lastUsed'>): void {
    const trips = this.getRecentTrips();

    const existingIndex = trips.findIndex(
      t => t.departureCode === trip.departureCode && t.destinationCode === trip.destinationCode
    );

    const newTrip: TripPair = {
      id: `${trip.departureCode}-${trip.destinationCode}`,
      ...trip,
      lastUsed: new Date(),
    };

    if (existingIndex >= 0) {
      trips[existingIndex] = newTrip;
    } else {
      trips.unshift(newTrip);
    }

    const trimmedTrips = trips.slice(0, MAX_RECENT_TRIPS);
    trimmedTrips.sort((a, b) => b.lastUsed.getTime() - a.lastUsed.getTime());

    this.writeData(RECENT_TRIPS_KEY, trimmedTrips, evictOldest);
  }

  // Favorite Routes
  getFavoriteRoutes(): TripPair[] {
    const routes = this.readData<TripPair[]>(FAVORITE_ROUTES_KEY);
    if (!Array.isArray(routes)) return [];
    return routes.map((route) => ({
      ...route,
      lastUsed: new Date(route.lastUsed),
    }));
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

    this.writeData(FAVORITE_ROUTES_KEY, updatedRoutes, evictOldest);
  }

  removeFavoriteRoute(routeId: string): void {
    const routes = this.getFavoriteRoutes();
    const filtered = routes.filter(route => route.id !== routeId);
    this.writeData(FAVORITE_ROUTES_KEY, filtered);
  }

  // Favorite Stations
  getFavoriteStations(): FavoriteStation[] {
    const favorites = this.readData<FavoriteStation[]>(FAVORITES_KEY);
    if (!Array.isArray(favorites)) return [];
    return favorites.map((fav) => ({
      ...fav,
      addedDate: new Date(fav.addedDate),
    }));
  }

  addFavoriteStation(station: Omit<FavoriteStation, 'addedDate'>): void {
    const favorites = this.getFavoriteStations();
    if (favorites.some(f => f.id === station.id)) return;

    const newFavorite: FavoriteStation = {
      ...station,
      addedDate: new Date(),
    };

    favorites.unshift(newFavorite);
    this.writeData(FAVORITES_KEY, favorites, evictOldest);
  }

  removeFavoriteStation(stationId: string): void {
    const favorites = this.getFavoriteStations();
    const filtered = favorites.filter(f => f.id !== stationId);
    this.writeData(FAVORITES_KEY, filtered);
  }

  // Last Selected Route
  getLastRoute(): { from: { code: string; name: string }; to: { code: string; name: string } } | null {
    return this.readData(LAST_ROUTE_KEY);
  }

  saveLastRoute(from: { code: string; name: string }, to: { code: string; name: string }): void {
    this.writeData(LAST_ROUTE_KEY, { from, to });
  }

  // Preferred Transit Systems
  getPreferredSystems(): TransitSystem[] {
    const systems = this.readData<TransitSystem[]>(SYSTEMS_KEY);
    return Array.isArray(systems) ? systems : [];
  }

  savePreferredSystems(systems: TransitSystem[]): void {
    this.writeData(SYSTEMS_KEY, systems);
  }

  // Commute Profile
  getHomeStation(): Station | null {
    return this.readData<Station>(HOME_STATION_KEY);
  }

  setHomeStation(station: Station | null): void {
    if (station) {
      this.writeData(HOME_STATION_KEY, station);
      return;
    }
    localStorage.removeItem(HOME_STATION_KEY);
  }

  getWorkStation(): Station | null {
    return this.readData<Station>(WORK_STATION_KEY);
  }

  setWorkStation(station: Station | null): void {
    if (station) {
      this.writeData(WORK_STATION_KEY, station);
      return;
    }
    localStorage.removeItem(WORK_STATION_KEY);
  }

  // Trip History
  getTripHistory(): TripHistoryEntry[] {
    const entries = this.readData<TripHistoryEntry[]>(TRIP_HISTORY_KEY);
    if (!Array.isArray(entries)) return [];
    return entries.map((entry) => ({
      ...entry,
      viewedAt: new Date(entry.viewedAt),
    }));
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

  private saveTripHistoryEntry(entry: Omit<TripHistoryEntry, 'viewedAt'>): void {
    const entries = this.getTripHistory();
    const updatedEntries = [
      {
        ...entry,
        viewedAt: new Date(),
      },
      ...entries.filter((existing) => existing.id !== entry.id),
    ].slice(0, MAX_TRIP_HISTORY);

    this.writeData(TRIP_HISTORY_KEY, updatedEntries, evictOldest);
  }
}

export const storageService = new StorageService();

function getDurationMinutes(start: string | null, end: string | null): number | null {
  if (!start || !end) return null;

  const durationMs = new Date(end).getTime() - new Date(start).getTime();
  if (Number.isNaN(durationMs) || durationMs < 0) return null;

  return Math.round(durationMs / 60000);
}
