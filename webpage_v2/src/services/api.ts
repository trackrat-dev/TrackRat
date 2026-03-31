import { TrainDetailsResponse, PlatformPrediction, OperationsSummaryResponse, TripSearchResponse, SupportedStationsResponse, DelayForecastResponse, FeedbackRequest, ServiceAlertsResponse, TrainHistoryResponse, RouteHistoryResponse, CongestionResponse } from '../types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://apiv2.trackrat.net/api/v2';
const CACHE_DURATION = 120000; // 2 minutes in milliseconds

interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

export class APIService {
  private cache = new Map<string, CacheEntry<unknown>>();

  private async fetch<T>(url: string, useCache = true): Promise<T> {
    const cacheKey = url;

    // Check cache
    if (useCache) {
      const cached = this.cache.get(cacheKey);
      if (cached && Date.now() - cached.timestamp < CACHE_DURATION) {
        return cached.data as T;
      }
    }

    try {
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();

      // Cache the result
      if (useCache) {
        this.cache.set(cacheKey, {
          data,
          timestamp: Date.now(),
        });
      }

      return data as T;
    } catch (error) {
      if (error instanceof Error) {
        throw new Error(`Failed to fetch data: ${error.message}`);
      }
      throw new Error('Failed to fetch data: Unknown error');
    }
  }

  async getTrainDetails(trainId: string, date?: string): Promise<TrainDetailsResponse> {
    const dateParam = date || new Date().toISOString().split('T')[0];
    const url = `${BASE_URL}/trains/${encodeURIComponent(trainId)}?date=${dateParam}`;
    // Don't cache train details - always fetch fresh
    return this.fetch<TrainDetailsResponse>(url, false);
  }

  async searchTrips(from: string, to: string, limit = 50, date?: string): Promise<TripSearchResponse> {
    let url = `${BASE_URL}/trips/search?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&limit=${limit}&hide_departed=true`;
    if (date) url += `&date=${encodeURIComponent(date)}`;
    return this.fetch<TripSearchResponse>(url, false); // Don't cache — 30s polling needs fresh data
  }

  async getRouteSummary(from: string, to: string): Promise<OperationsSummaryResponse | null> {
    try {
      const url = `${BASE_URL}/routes/summary?scope=route&from_station=${encodeURIComponent(from)}&to_station=${encodeURIComponent(to)}`;
      return await this.fetch<OperationsSummaryResponse>(url);
    } catch {
      // Fail silently - summary is optional
      return null;
    }
  }

  async getPlatformPrediction(
    stationCode: string,
    trainId: string,
    journeyDate: string
  ): Promise<PlatformPrediction | null> {
    try {
      const url = `${BASE_URL}/predictions/track?station_code=${stationCode}&train_id=${trainId}&journey_date=${journeyDate}`;
      return await this.fetch<PlatformPrediction>(url, false); // Don't cache predictions
    } catch (error) {
      // Fail silently - predictions are optional
      console.warn('Failed to fetch platform predictions:', error);
      return null;
    }
  }

  async getDelayForecast(
    trainId: string,
    stationCode: string,
    journeyDate: string
  ): Promise<DelayForecastResponse | null> {
    try {
      const url = `${BASE_URL}/predictions/delay?train_id=${encodeURIComponent(trainId)}&station_code=${encodeURIComponent(stationCode)}&journey_date=${encodeURIComponent(journeyDate)}`;
      return await this.fetch<DelayForecastResponse>(url, false);
    } catch {
      // Fail silently - delay predictions are optional
      return null;
    }
  }

  async getSupportedStations(): Promise<SupportedStationsResponse> {
    const url = `${BASE_URL}/predictions/supported-stations`;
    return this.fetch<SupportedStationsResponse>(url);
  }

  async getTrainHistory(trainId: string, days = 365, fromStation?: string, toStation?: string): Promise<TrainHistoryResponse | null> {
    try {
      const params = new URLSearchParams({ days: days.toString() });
      if (fromStation) params.set('from_station', fromStation);
      if (toStation) params.set('to_station', toStation);
      const url = `${BASE_URL}/trains/${encodeURIComponent(trainId)}/history?${params.toString()}`;
      return await this.fetch<TrainHistoryResponse>(url);
    } catch {
      return null;
    }
  }

  async getTrainSummary(trainId: string, from: string, to: string): Promise<OperationsSummaryResponse | null> {
    try {
      const url = `${BASE_URL}/routes/summary?scope=train&train_id=${encodeURIComponent(trainId)}&from_station=${encodeURIComponent(from)}&to_station=${encodeURIComponent(to)}`;
      return await this.fetch<OperationsSummaryResponse>(url);
    } catch {
      return null;
    }
  }

  async getRouteHistory(from: string, to: string, dataSource: string, days = 30, hours?: number): Promise<RouteHistoryResponse | null> {
    try {
      const params = new URLSearchParams({
        from_station: from,
        to_station: to,
        data_source: dataSource,
      });
      if (hours !== undefined) {
        params.set('hours', hours.toString());
      } else {
        params.set('days', days.toString());
      }
      const url = `${BASE_URL}/routes/history?${params.toString()}`;
      return await this.fetch<RouteHistoryResponse>(url);
    } catch {
      return null;
    }
  }

  async getCongestion(): Promise<CongestionResponse> {
    const url = `${BASE_URL}/routes/congestion`;
    return this.fetch<CongestionResponse>(url);
  }

  async getNetworkSummary(): Promise<OperationsSummaryResponse | null> {
    try {
      const url = `${BASE_URL}/routes/summary?scope=network`;
      return await this.fetch<OperationsSummaryResponse>(url);
    } catch {
      return null;
    }
  }

  async getServiceAlerts(dataSource?: string, alertType?: string): Promise<ServiceAlertsResponse> {
    const params = new URLSearchParams();
    if (dataSource) params.set('data_source', dataSource);
    if (alertType) params.set('alert_type', alertType);
    const query = params.toString();
    const url = `${BASE_URL}/alerts/service${query ? `?${query}` : ''}`;
    return this.fetch<ServiceAlertsResponse>(url);
  }

  async submitFeedback(feedback: FeedbackRequest): Promise<void> {
    const url = `${BASE_URL}/feedback`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(feedback),
    });
    if (!response.ok) {
      throw new Error(`Failed to submit feedback: ${response.status}`);
    }
  }

}

export const apiService = new APIService();
