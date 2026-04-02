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
const COMMUTE_TIME_ZONE = 'America/New_York';

function getCommuteParts(now: Date): { hour: number; weekday: number } {
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone: COMMUTE_TIME_ZONE,
    hour: 'numeric',
    hour12: false,
    weekday: 'short',
  });
  const parts = formatter.formatToParts(now);
  const hour = Number(parts.find((part) => part.type === 'hour')?.value ?? Number.NaN);
  const weekdayLabel = parts.find((part) => part.type === 'weekday')?.value;
  const weekdayMap: Record<string, number> = {
    Sun: 0,
    Mon: 1,
    Tue: 2,
    Wed: 3,
    Thu: 4,
    Fri: 5,
    Sat: 6,
  };

  return {
    hour,
    weekday: weekdayLabel ? weekdayMap[weekdayLabel] ?? -1 : -1,
  };
}

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

  const { hour, weekday } = getCommuteParts(now);
  const isWeekday = weekday >= 1 && weekday <= 5;
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
