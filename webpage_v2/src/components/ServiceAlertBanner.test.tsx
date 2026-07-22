import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, within, act } from '@testing-library/react';
import { ServiceAlertBanner } from './ServiceAlertBanner';
import { apiService } from '../services/api';
import { ServiceAlert, ServiceAlertsResponse } from '../types';

vi.mock('../services/api', () => ({
  apiService: {
    getServiceAlerts: vi.fn(),
  },
}));

const mockedGetServiceAlerts = vi.mocked(apiService.getServiceAlerts);
const ALERTS_POLL_MS = 120_000;

function makeAlert(overrides: Partial<ServiceAlert> = {}): ServiceAlert {
  return {
    alert_id: 'njt-rss-1',
    data_source: 'NJT',
    alert_type: 'alert',
    affected_route_ids: [],
    header_text: 'Northeast Corridor delays',
    description_text: 'Trains are running 15 minutes late.',
    active_periods: [],
    ...overrides,
  };
}

function mockAlerts(alerts: ServiceAlert[]) {
  const response: ServiceAlertsResponse = { alerts, count: alerts.length };
  mockedGetServiceAlerts.mockResolvedValue(response);
}

describe('ServiceAlertBanner', () => {
  beforeEach(() => {
    mockedGetServiceAlerts.mockReset();
  });

  it('surfaces an active real-time headline while remaining collapsed by default', async () => {
    mockAlerts([makeAlert({ header_text: 'NJT service change' })]);

    render(<ServiceAlertBanner dataSource="NJT" />);

    const toggle = await screen.findByRole('button', {
      name: /show service alerts \(1\): njt service change/i,
    });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(within(toggle).getByText('NJT service change')).toBeInTheDocument();
    expect(within(toggle).getByText('1')).toBeInTheDocument();
    // usePolling threads an AbortSignal through so in-flight fetches cancel on unmount.
    expect(mockedGetServiceAlerts).toHaveBeenCalledWith('NJT', undefined, expect.any(AbortSignal));
  });

  it('prioritizes a real-time headline in a mixed alert set', async () => {
    mockAlerts([
      makeAlert({
        alert_id: 'planned-1',
        alert_type: 'planned_work',
        header_text: 'Weekend track work',
      }),
      makeAlert({ alert_id: 'alert-1', header_text: 'Trains bypass Secaucus' }),
    ]);

    render(<ServiceAlertBanner dataSource="NJT" />);

    const toggle = await screen.findByRole('button', {
      name: /show service alerts \(2\): trains bypass secaucus/i,
    });
    expect(within(toggle).getByText('Trains bypass Secaucus')).toBeInTheDocument();
    expect(within(toggle).getByText('2')).toBeInTheDocument();
    expect(screen.queryByText('Weekend track work')).not.toBeInTheDocument();
  });

  it('keeps planned-work-only alerts compact and identifies their type', async () => {
    mockAlerts([
      makeAlert({ alert_type: 'planned_work', header_text: 'Weekend track work' }),
    ]);

    render(<ServiceAlertBanner dataSource="NJT" />);

    const toggle = await screen.findByRole('button', {
      name: /show service alerts \(1\): planned work/i,
    });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(within(toggle).getByText('Planned Work')).toBeInTheDocument();
    expect(screen.queryByText('Weekend track work')).not.toBeInTheDocument();
  });

  it('keeps elevator-only alerts compact and identifies their type', async () => {
    mockAlerts([
      makeAlert({ alert_type: 'elevator', header_text: 'Elevator unavailable at Newark Penn' }),
    ]);

    render(<ServiceAlertBanner dataSource="NJT" />);

    const toggle = await screen.findByRole('button', {
      name: /show service alerts \(1\): elevator outage/i,
    });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(within(toggle).getByText('Elevator Outage')).toBeInTheDocument();
    expect(screen.queryByText('Elevator unavailable at Newark Penn')).not.toBeInTheDocument();
  });

  it('does not mislabel a mixed planned-work and elevator summary', async () => {
    mockAlerts([
      makeAlert({ alert_id: 'planned-1', alert_type: 'planned_work' }),
      makeAlert({ alert_id: 'elevator-1', alert_type: 'elevator' }),
    ]);

    render(<ServiceAlertBanner dataSource="NJT" />);

    const toggle = await screen.findByRole('button', {
      name: /show service alerts \(2\): planned work and elevator outage/i,
    });
    expect(within(toggle).getByText('Service Alerts')).toBeInTheDocument();
  });

  it('clamps a long real-time headline without removing its accessible text', async () => {
    const longHeadline = 'Major service changes affect Northeast Corridor trains between New York and Trenton throughout the evening rush';
    mockAlerts([makeAlert({ header_text: longHeadline })]);

    render(<ServiceAlertBanner dataSource="NJT" />);

    const toggle = await screen.findByRole('button', { name: new RegExp(longHeadline, 'i') });
    const headline = within(toggle).getByText(longHeadline);
    expect(headline).toHaveClass('line-clamp-2', 'break-words');
    expect(headline.parentElement).toHaveClass('min-w-0');
  });

  it('renders MTA (SUBWAY) alerts once expanded — fetch behavior unchanged', async () => {
    mockAlerts([makeAlert({ data_source: 'SUBWAY', header_text: 'Subway delays' })]);

    render(<ServiceAlertBanner dataSource="SUBWAY" />);

    fireEvent.click(await screen.findByRole('button', { name: /show service alerts/i }));

    expect(await screen.findByText('Subway delays')).toBeInTheDocument();
    expect(mockedGetServiceAlerts).toHaveBeenCalledWith('SUBWAY', undefined, expect.any(AbortSignal));
  });

  it('toggles expansion and restores the compact headline on collapse', async () => {
    mockAlerts([makeAlert({ header_text: 'NJT service change' })]);

    render(<ServiceAlertBanner dataSource="NJT" />);

    const toggle = await screen.findByRole('button', { name: /show service alerts/i });
    fireEvent.click(toggle);
    const expandedToggle = screen.getByRole('button', { name: /hide service alerts/i });
    expect(expandedToggle).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getAllByRole('button')).toHaveLength(2);
    expect(screen.getByText('NJT service change')).toBeInTheDocument();

    fireEvent.click(expandedToggle);

    const collapsedToggle = screen.getByRole('button', { name: /show service alerts/i });
    expect(collapsedToggle).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getAllByRole('button')).toHaveLength(1);
    expect(within(collapsedToggle).getByText('NJT service change')).toBeInTheDocument();
  });

  it('updates the collapsed summary on polling without resetting the user choice', async () => {
    vi.useFakeTimers();
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
    mockedGetServiceAlerts
      .mockResolvedValueOnce({
        alerts: [makeAlert({ alert_type: 'planned_work', header_text: 'Weekend track work' })],
        count: 1,
      })
      .mockResolvedValue({
        alerts: [makeAlert({ alert_id: 'alert-2', header_text: 'Northeast Corridor suspended' })],
        count: 1,
      });

    try {
      render(<ServiceAlertBanner dataSource="NJT" />);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });

      const initialToggle = screen.getByRole('button', { name: /show service alerts \(1\): planned work/i });
      fireEvent.click(initialToggle);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(ALERTS_POLL_MS);
      });

      const updatedToggle = screen.getByRole('button', {
        name: /hide service alerts \(1\): northeast corridor suspended/i,
      });
      expect(updatedToggle).toHaveAttribute('aria-expanded', 'true');
      expect(screen.getByText('Northeast Corridor suspended')).toBeInTheDocument();

      fireEvent.click(updatedToggle);
      const collapsedToggle = screen.getByRole('button', {
        name: /show service alerts \(1\): northeast corridor suspended/i,
      });
      expect(collapsedToggle).toHaveAttribute('aria-expanded', 'false');
      expect(within(collapsedToggle).getByText('Northeast Corridor suspended')).toBeInTheDocument();
      expect(mockedGetServiceAlerts).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it('does not fetch and renders nothing for a system without backend alerts (PATH)', async () => {
    // Even if the API were to return data, a non-capable system must not fetch.
    mockAlerts([makeAlert()]);

    const { container } = render(<ServiceAlertBanner dataSource="PATH" />);

    expect(mockedGetServiceAlerts).not.toHaveBeenCalled();
    expect(container).toBeEmptyDOMElement();
  });

  it('shows a system-wide alert (empty affected_route_ids) even when a routeIds filter is passed', async () => {
    mockAlerts([
      makeAlert({ header_text: 'System-wide NJT alert', affected_route_ids: [] }),
    ]);

    render(<ServiceAlertBanner dataSource="NJT" routeIds={['NE']} />);

    fireEvent.click(await screen.findByRole('button', { name: /show service alerts/i }));

    expect(await screen.findByText('System-wide NJT alert')).toBeInTheDocument();
  });

  it('keeps alerts matching the routeIds filter and drops non-matching ones', async () => {
    mockAlerts([
      makeAlert({ alert_id: 'a1', header_text: 'NEC alert', affected_route_ids: ['NE'] }),
      makeAlert({ alert_id: 'a2', header_text: 'Coast Line alert', affected_route_ids: ['NC'] }),
    ]);

    render(<ServiceAlertBanner dataSource="NJT" routeIds={['NE']} />);

    // The count in the collapsed toggle reflects the filtered set (1 of 2 matches).
    fireEvent.click(await screen.findByRole('button', { name: /show service alerts \(1\)/i }));

    expect(await screen.findByText('NEC alert')).toBeInTheDocument();
    expect(screen.queryByText('Coast Line alert')).not.toBeInTheDocument();
  });
});
