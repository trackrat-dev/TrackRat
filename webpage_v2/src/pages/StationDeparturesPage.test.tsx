import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { StationDeparturesPage } from './StationDeparturesPage';
import { Train, DeparturesResponse } from '../types';

// Mock the API service the page depends on.
vi.mock('../services/api', () => ({
  apiService: {
    getStationDepartures: vi.fn(),
    getServiceAlerts: vi.fn().mockResolvedValue({ alerts: [], count: 0 }),
  },
}));

import { apiService } from '../services/api';

const mockGetStationDepartures = vi.mocked(apiService.getStationDepartures);

function makeTrain(overrides: Partial<Train> = {}): Train {
  return {
    train_id: '3515',
    journey_date: '2025-01-15',
    line: { code: 'NEC', name: 'Northeast Corridor', color: '#003DA5' },
    destination: 'Trenton',
    departure: {
      code: 'NP',
      name: 'Newark Penn Station',
      scheduled_time: '2025-01-15T14:00:00-05:00',
    },
    // Single-station board: no arrival timing (no destination in the query).
    arrival: null,
    data_freshness: { last_updated: '2025-01-15T14:00:00Z', age_seconds: 10, update_count: 1, collection_method: null },
    data_source: 'NJT',
    observation_type: 'OBSERVED',
    is_cancelled: false,
    ...overrides,
  };
}

function makeResponse(departures: Train[]): DeparturesResponse {
  return {
    departures,
    metadata: {
      from_station: { code: 'NP', name: 'Newark Penn Station' },
      // The endpoint returns to_station: null for single-station boards; the
      // web type declares it required, so mirror the shape callers actually use.
      to_station: { code: '', name: '' },
      count: departures.length,
      generated_at: '2025-01-15T14:00:00-05:00',
    },
  };
}

function renderPage(code: string) {
  return render(
    <MemoryRouter initialEntries={[`/station/${code}`]}>
      <Routes>
        <Route path="/station/:code" element={<StationDeparturesPage />} />
        <Route path="/departures" element={<div>Departures Home</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('StationDeparturesPage', () => {
  beforeEach(() => {
    mockGetStationDepartures.mockReset();
  });

  it('renders the station header and a departure returned by the API', async () => {
    mockGetStationDepartures.mockResolvedValue(makeResponse([makeTrain()]));

    renderPage('NP');

    expect(await screen.findByText('Departures — Newark Penn Station')).toBeInTheDocument();
    expect(await screen.findByText('Train 3515')).toBeInTheDocument();
    // Destination is shown even though arrival timing is absent.
    expect(screen.getByText('Trenton')).toBeInTheDocument();
    expect(mockGetStationDepartures).toHaveBeenCalledWith('NP', 50, expect.anything());
  });

  it('shows the branded empty state with a plan-a-trip link when there are no departures', async () => {
    mockGetStationDepartures.mockResolvedValue(makeResponse([]));

    renderPage('NP');

    expect(await screen.findByText(/No upcoming departures from Newark Penn Station/)).toBeInTheDocument();
    const planLink = screen.getByText('Plan a trip instead →');
    expect(planLink).toBeInTheDocument();
    expect(planLink.closest('a')).toHaveAttribute('href', '/departures');
  });

  it('filters out app-disabled systems the backend might still surface', async () => {
    mockGetStationDepartures.mockResolvedValue(
      makeResponse([
        makeTrain({ train_id: 'NJT_OK', data_source: 'NJT' }),
        makeTrain({ train_id: 'BART_HIDDEN', data_source: 'BART' }),
      ])
    );

    renderPage('NP');

    expect(await screen.findByText('Train NJT_OK')).toBeInTheDocument();
    expect(screen.queryByText('Train BART_HIDDEN')).not.toBeInTheDocument();
  });

  it('shows a station-not-found error for an unknown code without calling the API', () => {
    renderPage('ZZZZ');

    expect(screen.getByText(/Station not found/)).toBeInTheDocument();
    expect(mockGetStationDepartures).not.toHaveBeenCalled();
  });
});
