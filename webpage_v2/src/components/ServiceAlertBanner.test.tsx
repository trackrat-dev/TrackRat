import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ServiceAlertBanner } from './ServiceAlertBanner';
import { apiService } from '../services/api';
import { ServiceAlert, ServiceAlertsResponse } from '../types';

vi.mock('../services/api', () => ({
  apiService: {
    getServiceAlerts: vi.fn(),
  },
}));

const mockedGetServiceAlerts = vi.mocked(apiService.getServiceAlerts);

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

  it('collapses alerts by default and expands them on click (NJT, newly alert-capable)', async () => {
    mockAlerts([makeAlert({ header_text: 'NJT service change' })]);

    render(<ServiceAlertBanner dataSource="NJT" />);

    // Collapsed by default (#1543): the section shows a count-bearing toggle,
    // but the individual alert cards are not rendered until the user expands.
    const toggle = await screen.findByRole('button', { name: /show service alerts \(1\)/i });
    expect(screen.queryByText('NJT service change')).not.toBeInTheDocument();

    fireEvent.click(toggle);

    expect(await screen.findByText('NJT service change')).toBeInTheDocument();
    // usePolling threads an AbortSignal through so in-flight fetches cancel on unmount.
    expect(mockedGetServiceAlerts).toHaveBeenCalledWith('NJT', undefined, expect.any(AbortSignal));
  });

  it('renders MTA (SUBWAY) alerts once expanded — fetch behavior unchanged', async () => {
    mockAlerts([makeAlert({ data_source: 'SUBWAY', header_text: 'Subway delays' })]);

    render(<ServiceAlertBanner dataSource="SUBWAY" />);

    fireEvent.click(await screen.findByRole('button', { name: /show service alerts/i }));

    expect(await screen.findByText('Subway delays')).toBeInTheDocument();
    expect(mockedGetServiceAlerts).toHaveBeenCalledWith('SUBWAY', undefined, expect.any(AbortSignal));
  });

  it('collapses again when the toggle is clicked a second time', async () => {
    mockAlerts([makeAlert({ header_text: 'NJT service change' })]);

    render(<ServiceAlertBanner dataSource="NJT" />);

    const toggle = await screen.findByRole('button', { name: /show service alerts/i });
    fireEvent.click(toggle);
    expect(await screen.findByText('NJT service change')).toBeInTheDocument();

    // While expanded the toggle's accessible label flips to "Hide".
    fireEvent.click(screen.getByRole('button', { name: /hide service alerts/i }));
    expect(screen.queryByText('NJT service change')).not.toBeInTheDocument();
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
