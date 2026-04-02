import { Station, TripPair } from '../types';

export interface SuggestedRoute {
  departure: Station;
  destination: Station;
  reason: string;
}

interface SuggestionInput {
  homeStation: Station | null;
  workStation: Station | null;
  recentTrips: TripPair[];
  now?: Date;
}

const RECENT_ROUTE_WINDOW_MS = 20 * 60 * 1000;

export function getSuggestedRoute({
  homeStation,
  workStation,
  recentTrips,
  now = new Date(),
}: SuggestionInput): SuggestedRoute | null {
  const latestTrip = recentTrips[0];
  if (latestTrip) {
    const lastUsed = latestTrip.lastUsed instanceof Date
      ? latestTrip.lastUsed
      : new Date(latestTrip.lastUsed);

    if (now.getTime() - lastUsed.getTime() <= RECENT_ROUTE_WINDOW_MS) {
      return {
        departure: { code: latestTrip.departureCode, name: latestTrip.departureName },
        destination: { code: latestTrip.destinationCode, name: latestTrip.destinationName },
        reason: 'Continue your recent trip',
      };
    }
  }

  if (!homeStation || !workStation) return null;

  const hour = now.getHours();
  const isWeekday = now.getDay() >= 1 && now.getDay() <= 5;
  if (!isWeekday) return null;

  if (hour >= 5 && hour < 11) {
    return {
      departure: homeStation,
      destination: workStation,
      reason: 'Morning commute',
    };
  }

  if (hour >= 15 && hour < 21) {
    return {
      departure: workStation,
      destination: homeStation,
      reason: 'Evening commute',
    };
  }

  return null;
}
