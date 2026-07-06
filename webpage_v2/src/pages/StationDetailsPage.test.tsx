import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { StationDetailsPage } from './StationDetailsPage';
import { useAppStore } from '../store/appStore';
import { Train, DeparturesResponse } from '../types';

vi.mock('../services/api', () => ({
  apiService: {
    getDepartures: vi.fn(),
    getRecentDepartures: vi.fn(),
    getServiceAlerts: vi.fn(),
  },
}));

import { apiService } from '../services/api';

const mockGetDepartures = apiService.getDepartures as ReturnType<typeof vi.fn>;
const mockGetRecentDepartures = apiService.getRecentDepartures as ReturnType<typeof vi.fn>;
const mockGetServiceAlerts = apiService.getServiceAlerts as ReturnType<typeof vi.fn>;

function makeTrain(overrides: Partial<Train> = {}): Train {
  return {
    train_id: '100',
    journey_date: '2025-01-15',
    line: { code: 'NE', name: 'Northeast Corridor', color: '#003DA5' },
    destination: 'New York Penn Station',
    departure: { code: 'HB', name: 'Hoboken', scheduled_time: '2025-01-15T14:00:00-05:00' },
    // Station-only board: the backend returns no arrival stop.
    arrival: null,
    data_freshness: { last_updated: '', age_seconds: 0, update_count: 0, collection_method: null },
    data_source: 'NJT',
    observation_type: 'OBSERVED',
    is_cancelled: false,
    ...overrides,
  };
}

function departures(trains: Train[]): DeparturesResponse {
  return {
    departures: trains,
    metadata: {
      from_station: { code: 'HB', name: 'Hoboken' },
      to_station: null,
      count: trains.length,
      generated_at: '2025-01-15T14:00:00-05:00',
    },
  };
}

function renderStation(code = 'HB') {
  return render(
    <MemoryRouter initialEntries={[`/station/${code}`]}>
      <Routes>
        <Route path="/station/:code" element={<StationDetailsPage />} />
        <Route path="/departures" element={<div>Departures Page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  useAppStore.setState({
    selectedDeparture: null,
    selectedDestination: null,
    recentTrips: [],
    favoriteRoutes: [],
    favoriteStations: [],
    preferredSystems: [],
    homeStation: null,
    workStation: null,
  });
  mockGetDepartures.mockReset();
  mockGetRecentDepartures.mockReset();
  mockGetServiceAlerts.mockReset();
  // Sensible defaults; individual tests override as needed.
  mockGetDepartures.mockResolvedValue(departures([]));
  mockGetRecentDepartures.mockResolvedValue(departures([]));
  mockGetServiceAlerts.mockResolvedValue({ alerts: [], count: 0 });
});

describe('StationDetailsPage', () => {
  it('renders the station header from the resolved code', async () => {
    renderStation('HB');
    expect(screen.getByRole('heading', { name: /Hoboken/ })).toBeInTheDocument();
    expect(screen.getByText('NJ Transit')).toBeInTheDocument();
  });

  it('renders recent (dimmed), a NOW divider, and upcoming trains', async () => {
    mockGetRecentDepartures.mockResolvedValue(
      departures([
        makeTrain({
          train_id: '1',
          departure: { code: 'HB', name: 'Hoboken', scheduled_time: '2025-01-15T13:50:00-05:00' },
        }),
      ])
    );
    mockGetDepartures.mockResolvedValue(
      departures([
        makeTrain({
          train_id: '2',
          departure: { code: 'HB', name: 'Hoboken', scheduled_time: '2025-01-15T14:10:00-05:00' },
        }),
      ])
    );

    renderStation('HB');

    await waitFor(() => expect(screen.getByText('Train 1')).toBeInTheDocument());
    expect(screen.getByText('Train 2')).toBeInTheDocument();
    expect(screen.getByText('Now')).toBeInTheDocument();
  });

  it('orders recent above the NOW divider and upcoming below it', async () => {
    mockGetRecentDepartures.mockResolvedValue(
      departures([
        makeTrain({
          train_id: '1',
          departure: { code: 'HB', name: 'Hoboken', scheduled_time: '2025-01-15T13:50:00-05:00' },
        }),
      ])
    );
    mockGetDepartures.mockResolvedValue(
      departures([
        makeTrain({
          train_id: '2',
          departure: { code: 'HB', name: 'Hoboken', scheduled_time: '2025-01-15T14:10:00-05:00' },
        }),
      ])
    );

    renderStation('HB');

    await waitFor(() => expect(screen.getByText('Train 1')).toBeInTheDocument());

    const recent = screen.getByText('Train 1');
    const now = screen.getByText('Now');
    const upcoming = screen.getByText('Train 2');

    // recent → NOW → upcoming in document order.
    expect(recent.compareDocumentPosition(now) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(now.compareDocumentPosition(upcoming) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('does not render an Arrival row for station-only departures', async () => {
    mockGetDepartures.mockResolvedValue(departures([makeTrain({ train_id: '2' })]));

    renderStation('HB');

    await waitFor(() => expect(screen.getByText('Train 2')).toBeInTheDocument());
    expect(screen.getByText('Departure')).toBeInTheDocument();
    expect(screen.queryByText('Arrival')).not.toBeInTheDocument();
  });

  it('shows "No departures available" when both lists are empty', async () => {
    renderStation('HB');
    await waitFor(() => expect(screen.getByText('No departures available')).toBeInTheDocument());
  });

  it('shows a friendly error for an unknown station code', () => {
    renderStation('ZZ999');

    expect(screen.getByText('Station not found')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Browse departures/ })).toBeInTheDocument();
    expect(mockGetDepartures).not.toHaveBeenCalled();
  });

  it('redirects an alias code to its canonical station', async () => {
    // PHO (Hoboken PATH) resolves to canonical HB.
    renderStation('PHO');

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /Hoboken/ })).toBeInTheDocument()
    );
    await waitFor(() =>
      expect(mockGetDepartures).toHaveBeenCalledWith('HB', expect.objectContaining({ limit: 30 }))
    );
  });

  it('sets the station as Home (and injects it as a favorite)', async () => {
    renderStation('HB');
    await waitFor(() => expect(screen.getByText('Set Home')).toBeInTheDocument());

    fireEvent.click(screen.getByText('Set Home'));

    expect(useAppStore.getState().homeStation?.code).toBe('HB');
    expect(useAppStore.getState().favoriteStations.some((f) => f.id === 'HB')).toBe(true);
    expect(screen.getByText('Home')).toBeInTheDocument();
  });

  it('sets the station as Work', async () => {
    renderStation('HB');
    await waitFor(() => expect(screen.getByText('Set Work')).toBeInTheDocument());

    fireEvent.click(screen.getByText('Set Work'));

    expect(useAppStore.getState().workStation?.code).toBe('HB');
    expect(screen.getByText('Work')).toBeInTheDocument();
  });

  it('toggles the station favorite on and off', async () => {
    renderStation('HB');
    await waitFor(() => expect(screen.getByText('Set Favorite')).toBeInTheDocument());

    fireEvent.click(screen.getByText('Set Favorite'));
    expect(useAppStore.getState().favoriteStations.some((f) => f.id === 'HB')).toBe(true);
    expect(screen.getByText('Favorited')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Favorited'));
    expect(useAppStore.getState().favoriteStations.some((f) => f.id === 'HB')).toBe(false);
  });

  it('makes Home, Work, and Favorite mutually exclusive for the station', async () => {
    renderStation('HB');
    await waitFor(() => expect(screen.getByText('Set Home')).toBeInTheDocument());

    // Home, then Work: the station moves from Home to Work (not both).
    fireEvent.click(screen.getByText('Set Home'));
    expect(useAppStore.getState().homeStation?.code).toBe('HB');

    fireEvent.click(screen.getByText('Set Work'));
    expect(useAppStore.getState().workStation?.code).toBe('HB');
    expect(useAppStore.getState().homeStation).toBeNull();
    // Still a favorite (Work injects one).
    expect(useAppStore.getState().favoriteStations.some((f) => f.id === 'HB')).toBe(true);
  });
});
