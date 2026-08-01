import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { NetworkStatusPage } from './NetworkStatusPage';
import { CongestionResponse, SegmentCongestion } from '../types';

// Mock the API so we can feed a controlled congestion payload. The page also
// calls getNetworkSummary; return null (a valid response) so that section stays empty.
const getCongestion = vi.fn();
const getNetworkSummary = vi.fn();
vi.mock('../services/api', () => ({
  apiService: {
    getCongestion: (signal?: AbortSignal) => getCongestion(signal),
    getNetworkSummary: (dataSource?: string, signal?: AbortSignal) => getNetworkSummary(dataSource, signal),
  },
}));

function segment(dataSource: string, from: string, to: string): SegmentCongestion {
  return {
    from_station: from,
    to_station: to,
    from_station_name: `${from} Name`,
    to_station_name: `${to} Name`,
    data_source: dataSource,
    congestion_level: 'severe',
    congestion_factor: 1.5,
    average_delay_minutes: 10,
    sample_count: 20,
    baseline_minutes: 30,
    current_average_minutes: 40,
    cancellation_count: 0,
    cancellation_rate: 0,
    train_count: 5,
    baseline_train_count: 8,
    frequency_factor: 0.6,
    frequency_level: 'reduced',
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <NetworkStatusPage />
    </MemoryRouter>,
  );
}

describe('NetworkStatusPage disabled-system filtering', () => {
  beforeEach(() => {
    getCongestion.mockReset();
    getNetworkSummary.mockReset();
    getNetworkSummary.mockResolvedValue(null);
  });

  it('renders enabled systems but hides systems in DISABLED_SYSTEMS', async () => {
    const response: CongestionResponse = {
      aggregated_segments: [
        segment('NJT', 'NY', 'NP'),
        segment('WMATA', 'A01', 'A02'),
      ],
      generated_at: '2026-07-05T18:00:00Z',
      time_window_hours: 3,
    };
    getCongestion.mockResolvedValue(response);

    renderPage();

    // NJT is enabled and must appear.
    expect(await screen.findByText('NJ Transit')).toBeInTheDocument();
    // WMATA is disabled app-wide and must not leak into the status page.
    expect(screen.queryByText('Washington Metro')).not.toBeInTheDocument();
  });

  it('shows a system again once it is not disabled (only NJT here, all enabled)', async () => {
    // A payload of only-enabled systems renders every system with no dropouts,
    // confirming the filter is scoped to DISABLED_SYSTEMS and nothing else.
    const response: CongestionResponse = {
      aggregated_segments: [
        segment('NJT', 'NY', 'NP'),
        segment('PATH', 'NWK', 'WTC'),
      ],
      generated_at: '2026-07-05T18:00:00Z',
      time_window_hours: 3,
    };
    getCongestion.mockResolvedValue(response);

    renderPage();

    expect(await screen.findByText('NJ Transit')).toBeInTheDocument();
    expect(screen.getByText('PATH')).toBeInTheDocument();
  });

  it('drops every disabled system (BART, WMATA, MBTA, Metra), keeping only enabled ones', async () => {
    const response: CongestionResponse = {
      aggregated_segments: [
        segment('NJT', 'NY', 'NP'),
        segment('BART', 'B01', 'B02'),
        segment('WMATA', 'A01', 'A02'),
        segment('MBTA', 'M01', 'M02'),
        segment('METRA', 'C01', 'C02'),
      ],
      generated_at: '2026-07-05T18:00:00Z',
      time_window_hours: 3,
    };
    getCongestion.mockResolvedValue(response);

    renderPage();

    expect(await screen.findByText('NJ Transit')).toBeInTheDocument();
    expect(screen.queryByText('BART')).not.toBeInTheDocument();
    expect(screen.queryByText('Washington Metro')).not.toBeInTheDocument();
    expect(screen.queryByText('MBTA')).not.toBeInTheDocument();
    expect(screen.queryByText('Metra')).not.toBeInTheDocument();
  });

  it('keeps a system whose only segments are all present (no false drops)', async () => {
    const response: CongestionResponse = {
      aggregated_segments: [segment('NJT', 'NY', 'NP')],
      generated_at: '2026-07-05T18:00:00Z',
      time_window_hours: 3,
    };
    getCongestion.mockResolvedValue(response);

    renderPage();

    await waitFor(() => expect(screen.getByText('NJ Transit')).toBeInTheDocument());
    // "1 segment" (singular) confirms the count derives from the filtered list.
    expect(screen.getByText(/1 segment$/)).toBeInTheDocument();
  });
});

// #1638: a segment escalated by cancellations has an average delay of zero.
// The page must not describe it as delayed — that combination ("red but there
// are no delays") is exactly what the reporter saw.
describe('NetworkStatusPage cancellation-driven segments', () => {
  beforeEach(() => {
    getCongestion.mockReset();
    getNetworkSummary.mockReset();
    getNetworkSummary.mockResolvedValue(null);
  });

  function cancelledSegment(from: string, to: string): SegmentCongestion {
    return {
      ...segment('NJT', from, to),
      congestion_level: 'severe',
      congestion_factor: 1.0,
      average_delay_minutes: 0,
      cancellation_count: 4,
      cancellation_rate: 50,
      congestion_cause: 'cancellations',
    };
  }

  /** Delayed AND escalated further by cancellations — the review case on #1681. */
  function mixedSegment(from: string, to: string): SegmentCongestion {
    return {
      ...segment('NJT', from, to),
      congestion_level: 'heavy',
      congestion_factor: 1.2,
      average_delay_minutes: 2,
      cancellation_count: 3,
      cancellation_rate: 20,
      congestion_cause: 'both',
    };
  }

  it('labels the system badge as cancellations rather than delays', async () => {
    getCongestion.mockResolvedValue({
      aggregated_segments: [cancelledSegment('CH', 'PE')],
      generated_at: '2026-07-05T18:00:00Z',
      time_window_hours: 3,
    } as CongestionResponse);

    renderPage();

    expect(await screen.findByText('Severe cancellations')).toBeInTheDocument();
    expect(screen.queryByText('Severe delays')).not.toBeInTheDocument();
  });

  it('counts cancellation-driven segments separately from delayed ones', async () => {
    getCongestion.mockResolvedValue({
      aggregated_segments: [cancelledSegment('CH', 'PE'), segment('NJT', 'NY', 'NP')],
      generated_at: '2026-07-05T18:00:00Z',
      time_window_hours: 3,
    } as CongestionResponse);

    renderPage();

    // One genuinely delayed segment, one escalated by cancellations. Rolling
    // both into "2 delayed" is the misreport this split exists to prevent.
    expect(await screen.findByText('1 delayed')).toBeInTheDocument();
    expect(screen.getByText('1 with cancellations')).toBeInTheDocument();
  });

  it('captions the segment row with its cancellation count', async () => {
    getCongestion.mockResolvedValue({
      aggregated_segments: [cancelledSegment('CH', 'PE')],
      generated_at: '2026-07-05T18:00:00Z',
      time_window_hours: 3,
    } as CongestionResponse);

    renderPage();
    fireEvent.click(await screen.findByText('NJ Transit'));

    // The delay text is suppressed at 0 min, so without this caption the row is
    // a bare colored dot with nothing explaining it (#1638).
    expect(await screen.findByText('4 cancelled')).toBeInTheDocument();
  });

  it('names both causes on a segment that is delayed and cancelled', async () => {
    getCongestion.mockResolvedValue({
      aggregated_segments: [mixedSegment('CH', 'PE')],
      generated_at: '2026-07-05T18:00:00Z',
      time_window_hours: 3,
    } as CongestionResponse);

    renderPage();

    // Reporting this as cancellations alone would contradict the +2m delay the
    // row shows; reporting it as delays alone would hide the cancellations.
    expect(await screen.findByText('Heavy delays and cancellations')).toBeInTheDocument();
  });

  it('counts a mixed segment as both delayed and cancelled', async () => {
    getCongestion.mockResolvedValue({
      aggregated_segments: [mixedSegment('CH', 'PE')],
      generated_at: '2026-07-05T18:00:00Z',
      time_window_hours: 3,
    } as CongestionResponse);

    renderPage();

    // The counts overlap deliberately: both statements are true of this one
    // segment, and dropping it from "delayed" was the review finding.
    expect(await screen.findByText('1 delayed')).toBeInTheDocument();
    expect(screen.getByText('1 with cancellations')).toBeInTheDocument();
  });

  it('keeps the delay visible alongside the cancellation count on a mixed row', async () => {
    getCongestion.mockResolvedValue({
      aggregated_segments: [mixedSegment('CH', 'PE')],
      generated_at: '2026-07-05T18:00:00Z',
      time_window_hours: 3,
    } as CongestionResponse);

    renderPage();
    fireEvent.click(await screen.findByText('NJ Transit'));

    expect(await screen.findByText('+2m')).toBeInTheDocument();
    expect(screen.getByText('3 cancelled')).toBeInTheDocument();
  });

  it('still says delays when the segment is genuinely delayed', async () => {
    getCongestion.mockResolvedValue({
      aggregated_segments: [segment('NJT', 'NY', 'NP')],
      generated_at: '2026-07-05T18:00:00Z',
      time_window_hours: 3,
    } as CongestionResponse);

    renderPage();

    expect(await screen.findByText('Severe delays')).toBeInTheDocument();
    expect(screen.queryByText('Severe cancellations')).not.toBeInTheDocument();
  });
});
