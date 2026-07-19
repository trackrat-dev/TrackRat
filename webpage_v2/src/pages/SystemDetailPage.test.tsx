import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useParams } from 'react-router-dom';
import { SystemDetailPage } from './SystemDetailPage';
import { CongestionResponse, SegmentCongestion } from '../types';

// The page reads congestion + summary from apiService, and its ServiceAlertBanner
// child reads service alerts. Mock the whole module.
vi.mock('../services/api', () => ({
  apiService: {
    getCongestion: vi.fn(),
    getNetworkSummary: vi.fn(),
    getServiceAlerts: vi.fn(),
  },
}));

// The real CongestionMap needs WebGL/MapLibre; stub it so tests stay in jsdom.
vi.mock('../components/CongestionMap', () => ({
  CongestionMap: () => <div data-testid="congestion-map" />,
}));

// eslint-disable-next-line import/first
import { apiService } from '../services/api';

function segment(from: string, to: string, delay: number): SegmentCongestion {
  return {
    from_station: from,
    to_station: to,
    from_station_name: `${from} Name`,
    to_station_name: `${to} Name`,
    data_source: 'NJT',
    congestion_level: 'moderate',
    congestion_factor: 1.2,
    average_delay_minutes: delay,
    sample_count: 20,
    baseline_minutes: 20,
    current_average_minutes: 20 + delay,
    cancellation_count: 0,
    cancellation_rate: 0,
    train_count: 5,
    baseline_train_count: 8,
    frequency_factor: 0.6,
    frequency_level: 'reduced',
  };
}

function congestion(segments: SegmentCongestion[]): CongestionResponse {
  return { aggregated_segments: segments, generated_at: '2026-07-05T18:00:00Z', time_window_hours: 3 };
}

/** Probe that renders the resolved lineId so we can assert route-row navigation. */
function LineProbe() {
  const { lineId } = useParams<{ lineId: string }>();
  return <div>line:{lineId}</div>;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/system/:system" element={<SystemDetailPage />} />
        <Route path="/line/:lineId" element={<LineProbe />} />
        <Route path="/status" element={<div>Network Status</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('SystemDetailPage', () => {
  beforeEach(() => {
    vi.mocked(apiService.getCongestion).mockResolvedValue(congestion([]));
    vi.mocked(apiService.getNetworkSummary).mockResolvedValue(null);
    vi.mocked(apiService.getServiceAlerts).mockResolvedValue({ alerts: [], count: 0 } as never);
  });

  it('renders the system name and its routes', async () => {
    renderAt('/system/NJT');

    expect(await screen.findByText('NJ Transit')).toBeInTheDocument();
    // A known NJT route from the topology.
    expect(await screen.findByText('Northeast Corridor')).toBeInTheDocument();
  });

  it('accepts a lowercase system code in the URL', async () => {
    renderAt('/system/njt');
    expect(await screen.findByText('NJ Transit')).toBeInTheDocument();
  });

  it('passes the system to the network summary request', async () => {
    renderAt('/system/NJT');
    await screen.findByText('NJ Transit');
    expect(apiService.getNetworkSummary).toHaveBeenCalledWith('NJT', expect.anything());
  });

  it('shows a delay pill on routes whose segments are congested', async () => {
    // NEC begins NY → SE; a congested NY↔SE segment yields a pill on that route.
    vi.mocked(apiService.getCongestion).mockResolvedValue(congestion([segment('NY', 'SE', 12)]));

    renderAt('/system/NJT');

    await screen.findByText('Northeast Corridor');
    expect(screen.getAllByText('+12 min').length).toBeGreaterThan(0);
  });

  it('navigates to the line view when a route row is tapped', async () => {
    renderAt('/system/NJT');

    const routeRow = await screen.findByText('Northeast Corridor');
    fireEvent.click(routeRow);

    expect(await screen.findByText('line:njt-nec')).toBeInTheDocument();
  });

  it('shows an error for an unknown / disabled system', async () => {
    renderAt('/system/NOPE');
    expect(await screen.findByText(/Unknown system/)).toBeInTheDocument();
  });

  it('treats a disabled system (Metra) as unknown', async () => {
    renderAt('/system/METRA');
    expect(await screen.findByText(/Unknown system/)).toBeInTheDocument();
  });
});
