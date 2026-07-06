import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
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

  it('fetches and renders alerts for NJT (newly alert-capable)', async () => {
    mockAlerts([makeAlert({ header_text: 'NJT service change' })]);

    render(<ServiceAlertBanner dataSource="NJT" />);

    expect(await screen.findByText('NJT service change')).toBeInTheDocument();
    // usePolling threads an AbortSignal through so in-flight fetches cancel on unmount.
    expect(mockedGetServiceAlerts).toHaveBeenCalledWith('NJT', undefined, expect.any(AbortSignal));
  });

  it('still fetches and renders MTA (SUBWAY) alerts — existing behavior unchanged', async () => {
    mockAlerts([makeAlert({ data_source: 'SUBWAY', header_text: 'Subway delays' })]);

    render(<ServiceAlertBanner dataSource="SUBWAY" />);

    expect(await screen.findByText('Subway delays')).toBeInTheDocument();
    expect(mockedGetServiceAlerts).toHaveBeenCalledWith('SUBWAY', undefined, expect.any(AbortSignal));
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

    expect(await screen.findByText('System-wide NJT alert')).toBeInTheDocument();
  });

  it('keeps alerts matching the routeIds filter and drops non-matching ones', async () => {
    mockAlerts([
      makeAlert({ alert_id: 'a1', header_text: 'NEC alert', affected_route_ids: ['NE'] }),
      makeAlert({ alert_id: 'a2', header_text: 'Coast Line alert', affected_route_ids: ['NC'] }),
    ]);

    render(<ServiceAlertBanner dataSource="NJT" routeIds={['NE']} />);

    expect(await screen.findByText('NEC alert')).toBeInTheDocument();
    expect(screen.queryByText('Coast Line alert')).not.toBeInTheDocument();
  });
});
