import { DeparturesResponse, TrainDetailsResponse, HealthResponse, PlatformPrediction } from '../types';

const BASE_URL = 'https://prod.api.trackrat.net/api/v2';
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
    const url = `${BASE_URL}/trains/departures?from=${from}&to=${to}&limit=${limit}`;
    return this.fetch<DeparturesResponse>(url);
  }

  async getTrainDetails(trainId: string, date?: string): Promise<TrainDetailsResponse> {
    const dateParam = date || new Date().toISOString().split('T')[0];
    const url = `${BASE_URL}/trains/${trainId}?date=${dateParam}`;
    // Don't cache train details - always fetch fresh
    return this.fetch<TrainDetailsResponse>(url, false);
  }

  async checkHealth(): Promise<HealthResponse> {
    const url = `${BASE_URL}/../health`;
    return this.fetch<HealthResponse>(url, false);
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

  clearCache(): void {
    this.cache.clear();
  }

  // Get cache age for a URL
  getCacheAge(url: string): number | null {
    const cached = this.cache.get(url);
    if (!cached) return null;
    return Date.now() - cached.timestamp;
  }
}

export const apiService = new APIService();
