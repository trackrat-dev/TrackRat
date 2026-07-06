import { Station, FavoriteStation, TripPair } from '../types';
import { getStationByCode } from '../data/stations';

// Which route slot a tapped station should land in.
export type StationSlot = 'from' | 'to';

// Fill the one empty slot; when both are already set the caller must ask the user.
export type SlotDecision =
  | { action: 'fill'; slot: StationSlot }
  | { action: 'choose' };

// Slot-filling rule shared by the favorites grid and the quick-search list:
// empty From -> From, else empty To -> To, else let the user choose.
export function resolveStationSlot(params: {
  hasDeparture: boolean;
  hasDestination: boolean;
}): SlotDecision {
  if (!params.hasDeparture) return { action: 'fill', slot: 'from' };
  if (!params.hasDestination) return { action: 'fill', slot: 'to' };
  return { action: 'choose' };
}

// Why a station appears in the picker's "Your stations" section (drives its icon).
export type QuickStationRole = 'home' | 'work' | 'favorite' | 'recent';

export interface QuickStation {
  station: Station;
  role: QuickStationRole;
}

// Build the personalized header list shown above the raw system groups:
// Home, Work, favorites, then recent stations (deduped, most-recent-first),
// each resolved to a full Station so line chips and system names render.
export function buildQuickStations(params: {
  homeStation: Station | null;
  workStation: Station | null;
  favoriteStations: FavoriteStation[];
  recentTrips: TripPair[];
  maxRecents?: number;
}): QuickStation[] {
  const { homeStation, workStation, favoriteStations, recentTrips, maxRecents = 5 } = params;
  const out: QuickStation[] = [];
  const seen = new Set<string>();

  const add = (station: Station | null | undefined, role: QuickStationRole): boolean => {
    if (!station || seen.has(station.code)) return false;
    seen.add(station.code);
    out.push({ station, role });
    return true;
  };

  if (homeStation) add(getStationByCode(homeStation.code) ?? homeStation, 'home');
  if (workStation) add(getStationByCode(workStation.code) ?? workStation, 'work');
  for (const favorite of favoriteStations) add(getStationByCode(favorite.id), 'favorite');

  let recents = 0;
  for (const trip of recentTrips) {
    for (const code of [trip.departureCode, trip.destinationCode]) {
      if (recents >= maxRecents) break;
      if (add(getStationByCode(code), 'recent')) recents++;
    }
    if (recents >= maxRecents) break;
  }

  return out;
}

// Station names that occur more than once in a list — the only case where a row
// needs its system name shown to stay unambiguous once codes are dropped.
export function collidingStationNames(stations: Station[]): Set<string> {
  const counts = new Map<string, number>();
  for (const station of stations) {
    counts.set(station.name, (counts.get(station.name) ?? 0) + 1);
  }
  const collisions = new Set<string>();
  for (const [name, count] of counts) {
    if (count > 1) collisions.add(name);
  }
  return collisions;
}
