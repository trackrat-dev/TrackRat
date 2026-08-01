import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
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

/**
 * Congestion load/error/staleness states (#1627).
 *
 * Fake timers, because the failure modes that matter only appear across the
 * 60s poll boundary: a refresh that fails after a good load, and the recovery
 * that must clear the warning again.
 */
describe('SystemDetailPage congestion load states', () => {
  let consoleError: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.useFakeTimers();
    // Queued *Once values must not leak between cases in this block.
    vi.mocked(apiService.getCongestion).mockReset();
    vi.mocked(apiService.getNetworkSummary).mockReset();
    vi.mocked(apiService.getServiceAlerts).mockReset();

    vi.mocked(apiService.getCongestion).mockResolvedValue(congestion([]));
    vi.mocked(apiService.getNetworkSummary).mockResolvedValue(null);
    vi.mocked(apiService.getServiceAlerts).mockResolvedValue({ alerts: [], count: 0 } as never);

    // usePolling logs unexpected callback rejections. Nothing in this block
    // should reach it now that fetchData catches — asserted in the abort case.
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleError.mockRestore();
    vi.useRealTimers();
  });

  /** Settle pending promises (and optionally cross a poll boundary). */
  async function tick(ms = 0) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(ms);
    });
  }

  const summaryPayload = {
    headline: 'All clear',
    body: 'No significant delays.',
    scope: 'network',
    time_window_minutes: 60,
    data_freshness_seconds: 30,
    generated_at: '2026-07-05T18:00:00Z',
  };

  it('shows a loading state while the first congestion request is in flight', async () => {
    // Never settles: the page must be in its pending state, not its empty one.
    vi.mocked(apiService.getCongestion).mockReturnValue(new Promise(() => {}));

    renderAt('/system/NJT');
    await tick();

    expect(screen.getByRole('status', { name: 'Loading system status' })).toBeInTheDocument();
    // The routes list must not paint before any data exists — an all-plain list
    // is exactly the "healthy system" illusion this issue is about.
    expect(screen.queryByText('Northeast Corridor')).not.toBeInTheDocument();
  });

  it('shows an explicit error instead of an empty page when the first load fails', async () => {
    vi.mocked(apiService.getCongestion).mockRejectedValue(new Error('Request timed out'));

    renderAt('/system/NJT');
    await tick();

    expect(screen.getByText(/Request timed out/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
    // Regression guard: before the fix this rendered the full page with an
    // empty routes list, indistinguishable from a system running clean.
    expect(screen.queryByText('Northeast Corridor')).not.toBeInTheDocument();
    expect(screen.queryByText('No congestion reported for this system.')).not.toBeInTheDocument();
  });

  it('recovers in place when Retry succeeds after an initial failure', async () => {
    vi.mocked(apiService.getCongestion)
      .mockRejectedValueOnce(new Error('Request timed out'))
      .mockResolvedValue(congestion([segment('NY', 'SE', 12)]));

    renderAt('/system/NJT');
    await tick();
    expect(screen.getByText(/Request timed out/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    await tick();

    expect(screen.queryByText(/Request timed out/)).not.toBeInTheDocument();
    expect(screen.getByText('Northeast Corridor')).toBeInTheDocument();
    expect(screen.getAllByText('+12 min').length).toBeGreaterThan(0);
  });

  it('keeps prior values but marks them stale when a refresh fails, then clears on recovery', async () => {
    vi.mocked(apiService.getCongestion)
      .mockResolvedValueOnce(congestion([segment('NY', 'SE', 12)]))
      .mockRejectedValueOnce(new Error('Failed to fetch data: 503 Service Unavailable'))
      .mockResolvedValue(congestion([segment('NY', 'SE', 3)]));

    renderAt('/system/NJT');
    await tick();

    expect(screen.getAllByText('+12 min').length).toBeGreaterThan(0);
    expect(screen.queryByText(/showing last loaded data/)).not.toBeInTheDocument();

    // Failed refresh: values survive, but they are labelled stale.
    await tick(60_000);
    expect(screen.getByText(/503 Service Unavailable/)).toBeInTheDocument();
    expect(screen.getByText(/showing last loaded data/)).toBeInTheDocument();
    expect(screen.getAllByText('+12 min').length).toBeGreaterThan(0);
    // Still the page, not the full-page error — prior data outranks the failure.
    expect(screen.getByText('Northeast Corridor')).toBeInTheDocument();

    // Next good poll clears the warning and moves the numbers.
    await tick(60_000);
    expect(screen.queryByText(/showing last loaded data/)).not.toBeInTheDocument();
    expect(screen.queryByText(/503 Service Unavailable/)).not.toBeInTheDocument();
    expect(screen.getAllByText('+3 min').length).toBeGreaterThan(0);
    expect(screen.queryByText('+12 min')).not.toBeInTheDocument();
  });

  it('renders congestion when only the summary is unavailable', async () => {
    vi.mocked(apiService.getCongestion).mockResolvedValue(congestion([segment('NY', 'SE', 12)]));
    // getNetworkSummary returns null for every failure except cancellation.
    vi.mocked(apiService.getNetworkSummary).mockResolvedValue(null);

    renderAt('/system/NJT');
    await tick();

    expect(screen.getAllByText('+12 min').length).toBeGreaterThan(0);
    expect(screen.getByText('Northeast Corridor')).toBeInTheDocument();
    // A missing summary is not a page failure.
    expect(screen.queryByText(/showing last loaded data/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
  });

  it('treats an aborted poll as cancellation, not failure', async () => {
    vi.mocked(apiService.getCongestion).mockResolvedValue(congestion([segment('NY', 'SE', 12)]));
    vi.mocked(apiService.getNetworkSummary)
      .mockResolvedValueOnce(summaryPayload as never)
      // Cancellation is the one case getNetworkSummary re-throws.
      .mockRejectedValue(new DOMException('Aborted', 'AbortError'));

    renderAt('/system/NJT');
    await tick();
    expect(screen.getByText('All clear')).toBeInTheDocument();

    await tick(60_000);

    // The aborted poll must commit nothing. Before the fix, the page's own
    // `.catch(() => null)` swallowed the abort and wrote summary = null,
    // silently erasing a good summary on every cancelled request.
    expect(screen.getByText('All clear')).toBeInTheDocument();
    expect(screen.queryByText(/showing last loaded data/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
    expect(consoleError).not.toHaveBeenCalled();
  });

  it('treats a successful zero-segment response as a valid empty state', async () => {
    vi.mocked(apiService.getCongestion).mockResolvedValue(congestion([]));

    renderAt('/system/NJT');
    await tick();

    expect(screen.getByText('No congestion reported for this system.')).toBeInTheDocument();
    // Loaded successfully, so it must read as data — not as an error or a spinner.
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
    expect(screen.queryByRole('status', { name: 'Loading system status' })).not.toBeInTheDocument();
    expect(screen.queryByText(/showing last loaded data/)).not.toBeInTheDocument();
    expect(screen.getByText('Northeast Corridor')).toBeInTheDocument();
    // Freshness is stamped even with nothing congested — that stamp is what
    // separates "loaded and quiet" from "never loaded".
    expect(screen.getByText(/^Updated at /)).toBeInTheDocument();
  });

  it('does not fall back to the full-page error after a zero-segment load fails to refresh', async () => {
    vi.mocked(apiService.getCongestion)
      .mockResolvedValueOnce(congestion([]))
      .mockRejectedValue(new Error('Request timed out'));

    renderAt('/system/NJT');
    await tick();
    expect(screen.getByText('No congestion reported for this system.')).toBeInTheDocument();

    await tick(60_000);

    // Guards the choice of `generatedAt` over `segments.length` as the marker of
    // a completed load: a quiet system must not be demoted to "never loaded".
    expect(screen.getByText(/showing last loaded data/)).toBeInTheDocument();
    expect(screen.getByText('Northeast Corridor')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
  });
});
