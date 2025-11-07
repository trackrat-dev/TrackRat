// Core Types

export interface Station {
  code: string;
  name: string;
  coordinates?: {
    lat: number;
    lon: number;
  };
}

export interface TripPair {
  id: string;
  departureCode: string;
  departureName: string;
  destinationCode: string;
  destinationName: string;
  lastUsed: Date;
}

export interface FavoriteStation {
  id: string; // Station code
  name: string;
  addedDate: Date;
}

// API Response Types

export interface LineInfo {
  code: string;
  name: string;
  color: string;
}

export interface StationTiming {
  code: string;
  name: string;
  scheduled_time: string;
  updated_time?: string | null;
  actual_time?: string | null;
  track?: string | null;
}

export interface Train {
  train_id: string;
  journey_date: string;
  line: LineInfo;
  destination: string;
  departure: StationTiming;
  arrival: StationTiming;
  train_position?: {
    last_departed_station_code?: string;
    at_station_code?: string | null;
    next_station_code?: string;
    between_stations?: boolean;
  };
  data_freshness: DataFreshness;
  data_source: 'NJT' | 'AMTRAK';
  observation_type: 'OBSERVED' | 'SCHEDULED';
  is_cancelled: boolean;
}

export interface DeparturesResponse {
  departures: Train[];
  metadata: {
    from_station: {
      code: string;
      name: string;
    };
    to_station: {
      code: string;
      name: string;
    };
    count: number;
    generated_at: string;
  };
}

export interface StationInfo {
  code: string;
  name: string;
}

export interface Stop {
  station: StationInfo;
  stop_sequence: number;
  scheduled_arrival?: string;
  scheduled_departure?: string;
  actual_arrival?: string;
  actual_departure?: string;
  track?: string;
  track_assigned_at?: string;
  has_departed_station: boolean;
}

export interface TrainRoute {
  origin: string;
  destination: string;
  origin_code: string;
  destination_code: string;
}

export interface TrainDetails {
  train_id: string;
  journey_date: string;
  line: LineInfo;
  route: TrainRoute;
  train_position?: {
    last_departed_station_code?: string;
    at_station_code?: string | null;
    next_station_code?: string;
    between_stations?: boolean;
  };
  stops: Stop[];
  data_freshness: DataFreshness;
  data_source: 'NJT' | 'AMTRAK';
  is_cancelled: boolean;
  is_completed: boolean;
}

export interface TrainDetailsResponse {
  train: TrainDetails;
}

export interface DataFreshness {
  last_updated: string;
  age_seconds: number;
  update_count: number;
  collection_method: string | null;
}

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  version: string;
  environment: string;
}

// UI State Types

export type TrainStatus =
  | 'scheduled'
  | 'boarding'
  | 'departed'
  | 'delayed'
  | 'approaching'
  | 'arrived'
  | 'cancelled';

export interface UITrainCard extends Train {
  status: TrainStatus;
  delayMinutes: number;
}
