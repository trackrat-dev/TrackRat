import { Train, TripOption } from '../types';

/**
 * Convert a direct (single-leg) TripOption from `/trips/search` into the `Train`
 * shape that `TrainCard` and the departures list render. Only the first leg is
 * used, so callers must filter to `is_direct` trips first.
 */
export function tripLegToTrain(trip: TripOption): Train {
  const leg = trip.legs[0];
  return {
    train_id: leg.train_id,
    journey_date: leg.journey_date,
    line: leg.line,
    destination: leg.destination,
    departure: leg.boarding,
    arrival: leg.alighting,
    train_position: leg.train_position,
    data_freshness: { last_updated: '', age_seconds: 0, update_count: 0, collection_method: null },
    data_source: leg.data_source,
    observation_type: (leg.observation_type as 'OBSERVED' | 'SCHEDULED') || 'OBSERVED',
    is_cancelled: leg.is_cancelled,
  };
}
