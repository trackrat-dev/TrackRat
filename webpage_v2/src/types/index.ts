// Core Types

export type TransitSystem = 'NJT' | 'AMTRAK' | 'PATH' | 'PATCO' | 'LIRR' | 'MNR' | 'SUBWAY' | 'METRA' | 'WMATA' | 'BART' | 'MBTA';

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

export interface TripHistoryEntry {
  id: string;
  kind: 'train' | 'trip';
  href: string;
  departureCode: string;
  departureName: string;
  destinationCode: string;
  destinationName: string;
  lineName: string | null;
  dataSource: TransitSystem | null;
  trainId: string | null;
  journeyDate: string | null;
  scheduledDeparture: string | null;
  scheduledArrival: string | null;
  totalDurationMinutes: number | null;
  transferCount: number;
  viewedAt: Date;
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
  data_source: 'NJT' | 'AMTRAK' | 'PATH' | 'PATCO' | 'LIRR' | 'MNR' | 'SUBWAY' | 'METRA' | 'WMATA' | 'BART' | 'MBTA';
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
  data_source: 'NJT' | 'AMTRAK' | 'PATH' | 'PATCO' | 'LIRR' | 'MNR' | 'SUBWAY' | 'METRA' | 'WMATA' | 'BART' | 'MBTA';
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

export interface TrainDelaySummary {
  train_id: string;
  delay_minutes: number;
  category: 'on_time' | 'slight_delay' | 'delayed' | 'cancelled';
  scheduled_departure: string;
}

export interface SummaryMetrics {
  on_time_percentage: number | null;
  average_delay_minutes: number | null;
  cancellation_count: number | null;
  train_count: number | null;
  trains_by_category: Record<string, TrainDelaySummary[]> | null;
  trains_by_headway: Record<string, TrainDelaySummary[]> | null;
}

export interface OperationsSummaryResponse {
  headline: string;
  body: string;
  scope: 'network' | 'route' | 'train';
  time_window_minutes: number;
  data_freshness_seconds: number;
  generated_at: string;
  metrics: SummaryMetrics | null;
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

// Supported Stations Types

export interface StationPredictionSupport {
  code: string;
  name: string;
  predictions_available: boolean;
  track_count: number | null;
}

export interface SupportedStationsResponse {
  stations: StationPredictionSupport[];
  total_predictions_enabled: number;
}

// Congestion Types

export type CongestionLevel = 'normal' | 'moderate' | 'heavy' | 'severe';

export interface SegmentCongestion {
  from_station: string;
  to_station: string;
  from_station_name: string;
  to_station_name: string;
  data_source: string;
  congestion_level: CongestionLevel;
  congestion_factor: number;
  average_delay_minutes: number;
  sample_count: number;
  baseline_minutes: number;
  current_average_minutes: number;
  cancellation_count: number;
  cancellation_rate: number;
  train_count: number | null;
  baseline_train_count: number | null;
  frequency_factor: number | null;
  frequency_level: 'healthy' | 'moderate' | 'reduced' | 'severe' | null;
}

export interface CongestionResponse {
  aggregated_segments: SegmentCongestion[];
  generated_at: string;
  time_window_hours: number;
}

// Train History Types

export interface HistoricalJourney {
  journey_date: string;
  scheduled_departure: string;
  actual_departure: string | null;
  scheduled_arrival: string | null;
  actual_arrival: string | null;
  delay_minutes: number;
  was_cancelled: boolean;
  track_assignments: Record<string, string | null>;
}

export interface TrainHistoryStatistics {
  total_journeys: number;
  on_time_percentage: number;
  average_delay_minutes: number;
  cancellation_rate: number;
}

export interface TrainHistoryResponse {
  train_id: string;
  journeys: HistoricalJourney[];
  statistics: TrainHistoryStatistics;
  data_source: string | null;
}

// Route History Types

export interface DelayBreakdown {
  on_time: number;
  slight: number;
  significant: number;
  major: number;
}

export interface AggregateStats {
  on_time_percentage: number | null;
  on_time_source: 'arrival' | 'departure' | null;
  average_delay_minutes: number | null;
  average_departure_delay_minutes: number;
  cancellation_rate: number;
  delay_breakdown: DelayBreakdown | null;
  track_usage_at_origin: Record<string, number>;
}

export interface RouteHistoryResponse {
  route: {
    from_station: string;
    to_station: string;
    total_trains: number;
    data_source: string;
    baseline_train_count: number | null;
  };
  aggregate_stats: AggregateStats;
  highlighted_train: {
    train_id: string;
    on_time_percentage: number | null;
    on_time_source: 'arrival' | 'departure' | null;
    average_delay_minutes: number | null;
    average_departure_delay_minutes: number;
    delay_breakdown: DelayBreakdown | null;
    track_usage_at_origin: Record<string, number>;
  } | null;
}

// Service Alert Types

export interface ServiceAlertActivePeriod {
  start: number | null;
  end: number | null;
}

export interface ServiceAlert {
  alert_id: string;
  data_source: string;
  alert_type: string; // "planned_work" | "alert" | "elevator"
  affected_route_ids: string[];
  header_text: string;
  description_text: string | null;
  active_periods: ServiceAlertActivePeriod[];
}

export interface ServiceAlertsResponse {
  alerts: ServiceAlert[];
  count: number;
}

// Feedback Types

export interface FeedbackRequest {
  message: string;
  screen: string;
  train_id?: string;
  origin_code?: string;
  destination_code?: string;
  app_version?: string;
  device_model?: string;
}

// Delay Forecast Types

export interface DelayBreakdownProbabilities {
  on_time: number;      // Probability <= 5 min delay
  slight: number;       // Probability 6-15 min delay
  significant: number;  // Probability 16-30 min delay
  major: number;        // Probability > 30 min delay
}

export interface DelayForecastResponse {
  train_id: string;
  station_code: string;
  journey_date: string;
  cancellation_probability: number;
  delay_probabilities: DelayBreakdownProbabilities;
  expected_delay_minutes: number;
  confidence: 'high' | 'medium' | 'low';
  sample_count: number;
  factors: string[];
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
