import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { RouteStatusPage } from './RouteStatusPage';
import { AggregateStats, RouteHistoryResponse } from '../types';

// RouteStatusPage and its children (DeparturesTimeline, ServiceAlertBanner) all
// read from apiService, so mock the whole module.
vi.mock('../services/api', () => ({
  apiService: {
    getRouteHistory: vi.fn(),
    getRouteSummary: vi.fn(),
    searchTrips: vi.fn(),
    getRecentDepartures: vi.fn(),
    getServiceAlerts: vi.fn(),
  },
}));

// eslint-disable-next-line import/first
import { apiService } from '../services/api';

function makeStats(onTimePercentage: number): AggregateStats {
  return {
    on_time_percentage: onTimePercentage,
    on_time_source: 'departure',
    average_delay_minutes: 2.5,
    average_departure_delay_minutes: 2.0,
    cancellation_rate: 1.0,
    delay_breakdown: { on_time: 80, slight: 15, significant: 4, major: 1 },
    track_usage_at_origin: { '1': 60, '2': 40 },
  };
}

function makeHistory(onTimePercentage: number): RouteHistoryResponse {
  return {
    route: { from_station: 'NP', to_station: 'NY', total_trains: 100, data_source: 'NJT', baseline_train_count: null },
    aggregate_stats: makeStats(onTimePercentage),
    highlighted_train: null,
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/route/NP/NY']}>
      <Routes>
        <Route path="/route/:from/:to" element={<RouteStatusPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('RouteStatusPage', () => {
  beforeEach(() => {
    vi.mocked(apiService.getRouteHistory).mockReset();
    vi.mocked(apiService.getRouteSummary).mockResolvedValue(null);
    vi.mocked(apiService.searchTrips).mockResolvedValue({ trips: [] } as never);
    vi.mocked(apiService.getRecentDepartures).mockResolvedValue({ departures: [] } as never);
    vi.mocked(apiService.getServiceAlerts).mockResolvedValue({ alerts: [] } as never);
  });

  it('keeps prior stats mounted (dimmed) while a period change is in flight', async () => {
    // First load (24h) resolves at 87% on-time. The second load (7d) is left
    // pending so we can observe the page mid-refresh.
    let resolveSecond: (v: RouteHistoryResponse) => void = () => {};
    const secondPending = new Promise<RouteHistoryResponse>(res => {
      resolveSecond = res;
    });
    vi.mocked(apiService.getRouteHistory)
      .mockResolvedValueOnce(makeHistory(87))
      .mockReturnValueOnce(secondPending);

    renderPage();

    // Initial stats render once the first fetch resolves.
    expect(await screen.findByText('87%')).toBeInTheDocument();

    // Switch 24h -> 7d, kicking off the (still-pending) refetch.
    fireEvent.click(screen.getByRole('button', { name: '7d' }));

    // The previous stats must stay in the DOM — never a full-area spinner.
    const priorStat = screen.getByText('87%');
    expect(priorStat).toBeInTheDocument();

    // The metrics container is dimmed and non-interactive during the refresh,
    // and still contains the prior stats.
    const dimmed = document.querySelector('.opacity-60.pointer-events-none');
    expect(dimmed).not.toBeNull();
    expect(dimmed).toContainElement(priorStat);

    // Resolving the refetch swaps in the new stats and clears the dim.
    resolveSecond(makeHistory(92));
    expect(await screen.findByText('92%')).toBeInTheDocument();
    expect(document.querySelector('.opacity-60.pointer-events-none')).toBeNull();
  });

  it('shows a skeleton (not stats) on the very first load', async () => {
    let resolveFirst: (v: RouteHistoryResponse) => void = () => {};
    const firstPending = new Promise<RouteHistoryResponse>(res => {
      resolveFirst = res;
    });
    vi.mocked(apiService.getRouteHistory).mockReturnValueOnce(firstPending);

    renderPage();

    // While the first fetch is pending, the layout-matched skeleton is shown
    // and no real stats exist yet.
    expect(screen.getByRole('status', { name: 'Loading route status' })).toBeInTheDocument();
    expect(screen.queryByText('87%')).not.toBeInTheDocument();

    resolveFirst(makeHistory(87));
    expect(await screen.findByText('87%')).toBeInTheDocument();
    expect(screen.queryByRole('status', { name: 'Loading route status' })).not.toBeInTheDocument();
  });
});
