import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { TripDetailsPage } from './TripDetailsPage';
import { TrainDetails } from '../types';

// The page reconstructs the whole trip from per-leg getTrainDetails responses,
// so those are the only network calls we need to control.
const { getTrainDetails, getServiceAlerts } = vi.hoisted(() => ({
  getTrainDetails: vi.fn(),
  getServiceAlerts: vi.fn(),
}));

vi.mock('../services/api', () => ({
  apiService: { getTrainDetails, getServiceAlerts },
}));

function makeTrain(overrides: Partial<TrainDetails>): TrainDetails {
  return {
    train_id: '0000',
    journey_date: '2026-04-01',
    line: { code: 'X', name: 'Line', color: '#000' },
    route: { origin: 'A', destination: 'B', origin_code: 'A', destination_code: 'B' },
    stops: [],
    data_freshness: { last_updated: '2026-04-01T08:00:00Z', age_seconds: 5, update_count: 1, collection_method: null },
    data_source: 'NJT',
    observation_type: 'OBSERVED',
    is_cancelled: false,
    is_completed: false,
    ...overrides,
  };
}

const legOne = makeTrain({
  train_id: '3515',
  line: { code: 'NEC', name: 'Northeast Corridor', color: '#f60' },
  route: { origin: 'Trenton', destination: 'Secaucus', origin_code: 'TR', destination_code: 'SEC' },
  data_source: 'NJT',
  stops: [
    { station: { code: 'TR', name: 'Trenton' }, stop_sequence: 1, scheduled_departure: '2026-04-01T08:00:00-04:00', has_departed_station: false },
    { station: { code: 'SEC', name: 'Secaucus' }, stop_sequence: 2, scheduled_arrival: '2026-04-01T08:50:00-04:00', has_departed_station: false },
  ],
});

const legTwo = makeTrain({
  train_id: 'A174',
  line: { code: 'AMT', name: 'Amtrak', color: '#1f3a93' },
  route: { origin: 'Secaucus', destination: 'New York Penn Station', origin_code: 'SEC', destination_code: 'NY' },
  data_source: 'AMTRAK',
  stops: [
    { station: { code: 'SEC', name: 'Secaucus' }, stop_sequence: 1, scheduled_departure: '2026-04-01T09:00:00-04:00', has_departed_station: false },
    { station: { code: 'NY', name: 'New York Penn Station' }, stop_sequence: 2, scheduled_arrival: '2026-04-01T09:15:00-04:00', has_departed_station: false },
  ],
});

const COMPACT_URL = '/trip?date=2026-04-01&legs=NJT:3515:TR:SEC,AMTRAK:A174:SEC:NY&walk=0';

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <TripDetailsPage />
    </MemoryRouter>
  );
}

describe('TripDetailsPage compact URL', () => {
  beforeEach(() => {
    localStorage.clear();
    getTrainDetails.mockReset();
    getServiceAlerts.mockReset();
    getServiceAlerts.mockResolvedValue({ alerts: [], count: 0 });
  });

  it('reconstructs and renders a full transfer trip from the compact URL alone', async () => {
    getTrainDetails.mockImplementation((trainId: string) =>
      Promise.resolve({ train: trainId === '3515' ? legOne : legTwo })
    );

    renderAt(COMPACT_URL);

    // Header is derived purely from the fetched legs — no location.state passed.
    expect(await screen.findByText('Trenton → New York Penn Station')).toBeInTheDocument();
    expect(screen.getByText('Northeast Corridor')).toBeInTheDocument();
    expect(screen.getByText('Amtrak')).toBeInTheDocument();

    // Each leg is fetched with its own data source and boarding station.
    expect(getTrainDetails).toHaveBeenCalledWith('3515', '2026-04-01', expect.objectContaining({ dataSource: 'NJT', fromStation: 'TR' }));
    expect(getTrainDetails).toHaveBeenCalledWith('A174', '2026-04-01', expect.objectContaining({ dataSource: 'AMTRAK', fromStation: 'SEC' }));
  });

  it('shows the per-leg error state when a leg 404s, without crashing', async () => {
    getTrainDetails.mockImplementation((trainId: string) =>
      trainId === '3515' ? Promise.resolve({ train: legOne }) : Promise.reject(new Error('404'))
    );

    renderAt(COMPACT_URL);

    // The surviving leg still renders; the aged-out leg shows the error state.
    expect(await screen.findByText('Could not load stops for this leg.')).toBeInTheDocument();
    expect(screen.getByText('Northeast Corridor')).toBeInTheDocument();
  });

  it('shows the not-available error when no trip source is present', () => {
    renderAt('/trip');
    expect(screen.getByText(/Trip details not available/)).toBeInTheDocument();
    expect(getTrainDetails).not.toHaveBeenCalled();
  });
});
