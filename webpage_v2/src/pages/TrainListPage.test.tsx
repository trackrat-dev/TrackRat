import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { TrainListPage } from './TrainListPage';
import { DeparturesResponse, Train, TripSearchResponse } from '../types';

// TrainListPage and its children (ServiceAlertBanner, TrainDistributionChart)
// all read from apiService, so mock the whole module.
vi.mock('../services/api', () => ({
  apiService: {
    searchTrips: vi.fn(),
    getDepartures: vi.fn(),
    getRouteSummary: vi.fn(),
    getServiceAlerts: vi.fn(),
  },
}));

// RouteMap is lazy-loaded and pulls in maplibre; stub it out.
vi.mock('../components/RouteMap', () => ({ RouteMap: () => null }));

// eslint-disable-next-line import/first
import { apiService } from '../services/api';

function makeTrain(trainId: string, lineCode: string): Train {
  return {
    train_id: trainId,
    journey_date: '2026-07-28',
    line: { code: lineCode, name: lineCode, color: '#ffffff' },
    destination: 'Suffern',
    departure: {
      code: 'HB',
      name: 'Hoboken',
      scheduled_time: '2026-07-28T23:00:00-04:00',
      updated_time: null,
      actual_time: null,
      track: null,
      status: null,
    },
    arrival: null,
    data_freshness: { last_updated: '2026-07-28T22:00:00-04:00', is_stale: false, age_seconds: 10 },
    data_source: 'NJT',
    observation_type: 'OBSERVED',
    is_cancelled: false,
  } as unknown as Train;
}

function departuresResponse(trains: Train[]): DeparturesResponse {
  return {
    departures: trains,
    metadata: {
      from_station: { code: 'HB', name: 'Hoboken' },
      to_station: { code: 'SF', name: 'Suffern' },
      count: trains.length,
    },
  } as unknown as DeparturesResponse;
}

function tripsResponse(trains: Train[]): TripSearchResponse {
  return {
    trips: trains.map((t) => ({
      is_direct: true,
      legs: [
        {
          train_id: t.train_id,
          journey_date: t.journey_date,
          line: t.line,
          destination: t.destination,
          boarding: t.departure,
          alighting: t.departure,
          data_source: t.data_source,
          observation_type: t.observation_type,
          is_cancelled: t.is_cancelled,
          data_freshness: t.data_freshness,
        },
      ],
      transfers: [],
    })),
    metadata: { search_type: 'direct', count: trains.length },
  } as unknown as TripSearchResponse;
}

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/trains/:from/:to" element={<TrainListPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('TrainListPage line scoping (issue #1625)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiService.getServiceAlerts).mockResolvedValue({ alerts: [] } as never);
    vi.mocked(apiService.getRouteSummary).mockRejectedValue(new Error('no summary'));
    vi.mocked(apiService.searchTrips).mockResolvedValue(tripsResponse([makeTrain('1', 'MA')]));
    vi.mocked(apiService.getDepartures).mockResolvedValue(
      departuresResponse([makeTrain('1', 'MA')])
    );
  });

  it('fetches line-filtered departures when the URL carries a line scope', async () => {
    renderAt('/trains/HB/SF?data_source=NJT&lines=MA,Ma');

    await waitFor(() => expect(apiService.getDepartures).toHaveBeenCalled());

    expect(apiService.getDepartures).toHaveBeenCalledWith(
      'HB',
      expect.objectContaining({
        to: 'SF',
        dataSources: 'NJT',
        lines: ['MA', 'Ma'],
      })
    );
    // Trip search takes no line argument, so using it here would silently
    // return the combined shared-terminal board.
    expect(apiService.searchTrips).not.toHaveBeenCalled();
  });

  it('does not hide departed trains in line mode, matching the unscoped list', async () => {
    // The page deliberately shows departed trains sorted last; passing
    // hideDeparted would drop them only in line mode.
    renderAt('/trains/HB/SF?data_source=NJT&lines=MA,Ma');

    await waitFor(() => expect(apiService.getDepartures).toHaveBeenCalled());
    expect(apiService.getDepartures).toHaveBeenCalledWith(
      'HB',
      expect.not.objectContaining({ hideDeparted: true })
    );
  });

  it('falls back to the combined trip search when no line scope is present', async () => {
    renderAt('/trains/HB/SF');

    await waitFor(() => expect(apiService.searchTrips).toHaveBeenCalled());

    expect(apiService.searchTrips).toHaveBeenCalledWith(
      'HB',
      'SF',
      50,
      undefined,
      expect.anything()
    );
    expect(apiService.getDepartures).not.toHaveBeenCalled();
  });

  it('treats an empty lines param as unscoped rather than filtering to nothing', async () => {
    renderAt('/trains/HB/SF?data_source=NJT&lines=');

    await waitFor(() => expect(apiService.searchTrips).toHaveBeenCalled());
    expect(apiService.getDepartures).not.toHaveBeenCalled();
  });

  it('scopes service alerts to the line so a sibling line’s alerts are not attributed to it', async () => {
    vi.mocked(apiService.getServiceAlerts).mockResolvedValue({
      alerts: [
        {
          alert_id: 'bergen-only',
          alert_type: 'alert',
          header_text: 'Bergen County delays',
          description_text: null,
          affected_route_ids: ['BC'],
          active_periods: [],
          data_source: 'NJT',
        },
        {
          alert_id: 'system-wide',
          alert_type: 'alert',
          header_text: 'NJ Transit systemwide notice',
          description_text: null,
          affected_route_ids: [],
          active_periods: [],
          data_source: 'NJT',
        },
      ],
    } as never);

    renderAt('/trains/HB/SF?data_source=NJT&lines=MA,Ma');

    // The system-wide alert (no affected routes) must survive the filter; the
    // Bergen-only one must not be attributed to Main.
    await waitFor(() =>
      expect(screen.getByText('NJ Transit systemwide notice')).toBeInTheDocument()
    );
    expect(screen.queryByText('Bergen County delays')).not.toBeInTheDocument();
  });

  it('does not filter alerts by line on an unscoped station-pair view', async () => {
    vi.mocked(apiService.getServiceAlerts).mockResolvedValue({
      alerts: [
        {
          alert_id: 'bergen-only',
          alert_type: 'alert',
          header_text: 'Bergen County delays',
          description_text: null,
          affected_route_ids: ['BC'],
          active_periods: [],
          data_source: 'NJT',
        },
      ],
    } as never);

    renderAt('/trains/HB/SF');

    await waitFor(() => expect(screen.getByText('Bergen County delays')).toBeInTheDocument());
  });

  it('passes the future date through to the line-scoped fetch', async () => {
    // getDepartures previously had no `date` option, which would have silently
    // broken the date picker in line mode.
    renderAt('/trains/HB/SF?data_source=NJT&lines=MA,Ma');

    await waitFor(() => expect(apiService.getDepartures).toHaveBeenCalled());
    const opts = vi.mocked(apiService.getDepartures).mock.calls[0][1];
    expect(opts).toHaveProperty('date');
  });
});
