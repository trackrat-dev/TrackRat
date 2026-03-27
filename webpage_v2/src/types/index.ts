// Core Types

export type TransitSystem = 'NJT' | 'AMTRAK' | 'PATH' | 'PATCO' | 'LIRR' | 'MNR' | 'SUBWAY' | 'METRA' | 'WMATA' | 'BART';

export interface Station {
  code: string;
  name: string;
  system?: TransitSystem;
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
  data_source: 'NJT' | 'AMTRAK' | 'PATH' | 'PATCO' | 'LIRR' | 'MNR' | 'SUBWAY' | 'METRA' | 'WMATA' | 'BART';
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
  updated_arrival?: string;
  updated_departure?: string;
  actual_arrival?: string;
  actual_departure?: string;
  predicted_arrival?: string;
  predicted_arrival_samples?: number;
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
  data_source: 'NJT' | 'AMTRAK' | 'PATH' | 'PATCO' | 'LIRR' | 'MNR' | 'SUBWAY' | 'METRA' | 'WMATA' | 'BART';
  observation_type: 'OBSERVED' | 'SCHEDULED';
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

// Operations Summary Types

export interface OperationsSummaryResponse {
  headline: string;
  body: string;
  scope: 'network' | 'route' | 'train';
  time_window_minutes: number;
  data_freshness_seconds: number;
  generated_at: string;
}

// Track Prediction Types

export interface PlatformPrediction {
  platform_probabilities: Record<string, number>;
  primary_prediction: string;
  confidence: number;
  top_3: string[];
  model_version: string;
  station_code: string;
  train_id: string;
}

// Trip Search Types (supports direct + transfer connections)

export interface TripLeg {
  train_id: string;
  journey_date: string;
  line: LineInfo;
  data_source: TransitSystem;
  destination: string;
  boarding: StationTiming;
  alighting: StationTiming;
  observation_type?: string;
  is_cancelled: boolean;
  train_position?: {
    last_departed_station_code?: string;
    at_station_code?: string | null;
    next_station_code?: string;
  };
}

export interface TransferInfo {
  from_station: StationInfo;
  to_station: StationInfo;
  walk_minutes: number;
  same_station: boolean;
}

export interface TripOption {
  legs: TripLeg[];
  transfers: TransferInfo[];
  departure_time: string;
  arrival_time: string;
  total_duration_minutes: number;
  is_direct: boolean;
}

export interface TripSearchResponse {
  trips: TripOption[];
  metadata: {
    from_station: { code: string; name: string };
    to_station: { code: string; name: string };
    count: number;
    search_type: string;
    generated_at: string;
  };
}
