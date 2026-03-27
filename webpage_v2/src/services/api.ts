import { DeparturesResponse, TrainDetailsResponse, PlatformPrediction, OperationsSummaryResponse, TripSearchResponse } from '../types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://apiv2.trackrat.net/api/v2';
const CACHE_DURATION = 120000; // 2 minutes in milliseconds

interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

class APIService {
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

  async getDepartures(from: string, to: string, limit = 100): Promise<DeparturesResponse> {
    const url = `${BASE_URL}/trains/departures?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&limit=${limit}`;
    return this.fetch<DeparturesResponse>(url);
  }

  async getTrainDetails(trainId: string, date?: string): Promise<TrainDetailsResponse> {
    const dateParam = date || new Date().toISOString().split('T')[0];
    const url = `${BASE_URL}/trains/${encodeURIComponent(trainId)}?date=${dateParam}`;
    // Don't cache train details - always fetch fresh
    return this.fetch<TrainDetailsResponse>(url, false);
  }

  async searchTrips(from: string, to: string, limit = 50): Promise<TripSearchResponse> {
    const url = `${BASE_URL}/trips/search?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&limit=${limit}&hide_departed=true`;
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

}

export const apiService = new APIService();
