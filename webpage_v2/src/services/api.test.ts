import { describe, it, expect, vi, beforeEach } from 'vitest';
import { APIService } from './api';

// Mock global fetch
const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

function jsonResponse(data: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    json: () => Promise.resolve(data),
  });
}

let api: APIService;

beforeEach(() => {
  mockFetch.mockReset();
  api = new APIService(); // Fresh instance with empty cache
});

describe('getTrainDetails', () => {
  it('constructs correct URL with train ID and date', async () => {
    mockFetch.mockReturnValue(jsonResponse({ train: { train_id: '3515' } }));

    await api.getTrainDetails('3515', '2025-01-15');

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/trains/3515?date=2025-01-15')
    );
  });

  it('uses today date when no date provided', async () => {
    mockFetch.mockReturnValue(jsonResponse({ train: { train_id: '3515' } }));

    await api.getTrainDetails('3515');

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toMatch(/date=\d{4}-\d{2}-\d{2}/);
  });

  it('encodes special characters in train ID', async () => {
    mockFetch.mockReturnValue(jsonResponse({ train: {} }));

    await api.getTrainDetails('A/B');

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/trains/A%2FB')
    );
  });

  it('does not cache (always fetches fresh)', async () => {
    mockFetch.mockReturnValue(jsonResponse({ train: { train_id: '3515' } }));

    await api.getTrainDetails('3515', '2025-01-15');
    await api.getTrainDetails('3515', '2025-01-15');

    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it('throws on HTTP error', async () => {
    mockFetch.mockReturnValue(jsonResponse(null, 500));

    await expect(api.getTrainDetails('3515')).rejects.toThrow('Failed to fetch data');
  });

  it('throws on network error', async () => {
    mockFetch.mockRejectedValue(new TypeError('Network error'));

    await expect(api.getTrainDetails('3515')).rejects.toThrow('Failed to fetch data');
  });
});

describe('searchTrips', () => {
  it('constructs correct URL with from, to, limit, and hide_departed', async () => {
    mockFetch.mockReturnValue(jsonResponse({ trips: [], metadata: {} }));

    await api.searchTrips('NY', 'NP');

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('/trips/search?');
    expect(url).toContain('from=NY');
    expect(url).toContain('to=NP');
    expect(url).toContain('limit=50');
    expect(url).toContain('hide_departed=true');
  });

  it('uses custom limit', async () => {
    mockFetch.mockReturnValue(jsonResponse({ trips: [], metadata: {} }));

    await api.searchTrips('NY', 'NP', 25);

    expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('limit=25'));
  });

  it('appends date parameter when provided', async () => {
    mockFetch.mockReturnValue(jsonResponse({ trips: [], metadata: {} }));

    await api.searchTrips('NY', 'NP', 50, '2025-03-28');

    expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('date=2025-03-28'));
  });

  it('omits date parameter when not provided', async () => {
    mockFetch.mockReturnValue(jsonResponse({ trips: [], metadata: {} }));

    await api.searchTrips('NY', 'NP');

    expect(mockFetch).toHaveBeenCalledWith(expect.not.stringContaining('date='));
  });

  it('encodes station codes', async () => {
    mockFetch.mockReturnValue(jsonResponse({ trips: [], metadata: {} }));

    await api.searchTrips('S+1', 'S 2');

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('from=S%2B1');
    expect(url).toContain('to=S%202');
  });

  it('does not cache (polled endpoint)', async () => {
    mockFetch.mockReturnValue(jsonResponse({ trips: [], metadata: {} }));

    await api.searchTrips('NY', 'NP');
    await api.searchTrips('NY', 'NP');

    expect(mockFetch).toHaveBeenCalledTimes(2);
  });
});

describe('getRouteSummary', () => {
  it('returns null on failure (fail-silent)', async () => {
    mockFetch.mockReturnValue(jsonResponse(null, 500));

    const result = await api.getRouteSummary('NY', 'NP');
    expect(result).toBeNull();
  });

  it('constructs correct URL with scope=route', async () => {
    mockFetch.mockReturnValue(jsonResponse({ headline: 'test', body: '' }));

    await api.getRouteSummary('NY', 'NP');

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('scope=route&from_station=NY&to_station=NP')
    );
  });
});

describe('getPlatformPrediction', () => {
  it('returns null on failure (fail-silent)', async () => {
    mockFetch.mockReturnValue(jsonResponse(null, 404));

    const result = await api.getPlatformPrediction('NY', '3515', '2025-01-15');
    expect(result).toBeNull();
  });

  it('constructs correct URL', async () => {
    mockFetch.mockReturnValue(jsonResponse({ primary_prediction: '7' }));

    await api.getPlatformPrediction('NY', '3515', '2025-01-15');

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('station_code=NY');
    expect(url).toContain('train_id=3515');
    expect(url).toContain('journey_date=2025-01-15');
  });
});

describe('getDelayForecast', () => {
  it('returns null on failure (fail-silent)', async () => {
    mockFetch.mockReturnValue(jsonResponse(null, 500));

    const result = await api.getDelayForecast('3515', 'NY', '2025-01-15');
    expect(result).toBeNull();
  });

  it('constructs correct URL', async () => {
    mockFetch.mockReturnValue(jsonResponse({ cancellation_probability: 0.1 }));

    await api.getDelayForecast('3515', 'NY', '2025-01-15');

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('train_id=3515');
    expect(url).toContain('station_code=NY');
    expect(url).toContain('journey_date=2025-01-15');
  });
});

describe('getTrainHistory', () => {
  it('returns null on failure (fail-silent)', async () => {
    mockFetch.mockReturnValue(jsonResponse(null, 500));

    const result = await api.getTrainHistory('3515');
    expect(result).toBeNull();
  });

  it('constructs URL with default days=365', async () => {
    mockFetch.mockReturnValue(jsonResponse({ train_id: '3515', journeys: [] }));

    await api.getTrainHistory('3515');

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('/trains/3515/history?');
    expect(url).toContain('days=365');
  });

  it('includes from/to station params when provided', async () => {
    mockFetch.mockReturnValue(jsonResponse({ train_id: '3515', journeys: [] }));

    await api.getTrainHistory('3515', 30, 'NY', 'NP');

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('days=30');
    expect(url).toContain('from_station=NY');
    expect(url).toContain('to_station=NP');
  });

  it('omits from/to when not provided', async () => {
    mockFetch.mockReturnValue(jsonResponse({ train_id: '9999', journeys: [] }));

    await api.getTrainHistory('9999', 365);

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).not.toContain('from_station');
    expect(url).not.toContain('to_station');
  });
});

describe('getRouteHistory', () => {
  it('returns null on failure (fail-silent)', async () => {
    mockFetch.mockReturnValue(jsonResponse(null, 500));

    const result = await api.getRouteHistory('NY', 'NP', 'NJT');
    expect(result).toBeNull();
  });

  it('constructs URL with all required params', async () => {
    mockFetch.mockReturnValue(jsonResponse({ route: {}, aggregate_stats: {} }));

    await api.getRouteHistory('NY', 'NP', 'NJT', 90);

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('from_station=NY');
    expect(url).toContain('to_station=NP');
    expect(url).toContain('data_source=NJT');
    expect(url).toContain('days=90');
  });
});

describe('getCongestion', () => {
  it('fetches from correct endpoint', async () => {
    mockFetch.mockReturnValue(jsonResponse({ aggregated_segments: [], generated_at: '' }));

    await api.getCongestion();

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/routes/congestion')
    );
  });
});

describe('getNetworkSummary', () => {
  it('uses scope=network', async () => {
    mockFetch.mockReturnValue(jsonResponse({ headline: 'test' }));

    await api.getNetworkSummary();

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('scope=network')
    );
  });

  it('returns null on failure (fail-silent)', async () => {
    mockFetch.mockReturnValue(jsonResponse(null, 500));

    const result = await api.getNetworkSummary();
    expect(result).toBeNull();
  });
});

describe('getServiceAlerts', () => {
  it('constructs URL with data_source filter', async () => {
    mockFetch.mockReturnValue(jsonResponse({ alerts: [], count: 0 }));

    await api.getServiceAlerts('SUBWAY');

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('data_source=SUBWAY')
    );
  });

  it('constructs URL with both filters', async () => {
    mockFetch.mockReturnValue(jsonResponse({ alerts: [], count: 0 }));

    await api.getServiceAlerts('LIRR', 'alert');

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('data_source=LIRR');
    expect(url).toContain('alert_type=alert');
  });

  it('constructs URL without filters when none provided', async () => {
    mockFetch.mockReturnValue(jsonResponse({ alerts: [], count: 0 }));

    await api.getServiceAlerts();

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/alerts\/service$/)
    );
  });
});

describe('submitFeedback', () => {
  it('sends POST request with JSON body', async () => {
    mockFetch.mockReturnValue(jsonResponse({ status: 'received' }));

    await api.submitFeedback({
      message: 'Great app!',
      screen: 'web_feedback',
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/feedback'),
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: expect.stringContaining('"message":"Great app!"'),
      })
    );
  });

  it('throws on HTTP error', async () => {
    mockFetch.mockReturnValue(jsonResponse(null, 500));

    await expect(
      api.submitFeedback({ message: 'test', screen: 'test' })
    ).rejects.toThrow('Failed to submit feedback: 500');
  });

  it('includes all optional fields in body', async () => {
    mockFetch.mockReturnValue(jsonResponse({ status: 'received' }));

    await api.submitFeedback({
      message: 'Bug report',
      screen: 'train_details',
      train_id: '3515',
      origin_code: 'NY',
      destination_code: 'NP',
      app_version: 'web-1.0.0',
      device_model: 'Chrome',
    });

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.message).toBe('Bug report');
    expect(body.screen).toBe('train_details');
    expect(body.train_id).toBe('3515');
    expect(body.origin_code).toBe('NY');
    expect(body.destination_code).toBe('NP');
  });
});

describe('caching behavior', () => {
  it('caches cacheable endpoints (getSupportedStations)', async () => {
    mockFetch.mockReturnValue(jsonResponse({ stations: [{ code: 'NY' }], total_predictions_enabled: 1 }));

    const result1 = await api.getSupportedStations();
    const result2 = await api.getSupportedStations();

    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(result1).toEqual(result2);
  });

  it('caches getServiceAlerts', async () => {
    mockFetch.mockReturnValue(jsonResponse({ alerts: [], count: 0 }));

    await api.getServiceAlerts('SUBWAY');
    await api.getServiceAlerts('SUBWAY');

    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('does not share cache between different URLs', async () => {
    mockFetch.mockReturnValue(jsonResponse({ alerts: [], count: 0 }));

    await api.getServiceAlerts('SUBWAY');
    await api.getServiceAlerts('LIRR');

    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it('does not cache uncacheable endpoints (getTrainDetails)', async () => {
    mockFetch.mockReturnValue(jsonResponse({ train: { train_id: '3515' } }));

    await api.getTrainDetails('3515', '2025-01-15');
    await api.getTrainDetails('3515', '2025-01-15');

    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it('does not cache searchTrips', async () => {
    mockFetch.mockReturnValue(jsonResponse({ trips: [], metadata: {} }));

    await api.searchTrips('NY', 'NP');
    await api.searchTrips('NY', 'NP');

    expect(mockFetch).toHaveBeenCalledTimes(2);
  });
});
