import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { TrainListPage } from './TrainListPage';
import { ServiceAlert, Train, TripOption } from '../types';

// TrainListPage and its children (ServiceAlertBanner) read from apiService.
vi.mock('../services/api', () => ({
  apiService: {
    searchTrips: vi.fn(),
    getDepartures: vi.fn(),
    getRouteSummary: vi.fn(),
    getServiceAlerts: vi.fn(),
  },
}));

// RouteMap is lazy-loaded and pulls in MapLibre GL, which jsdom can't render.
vi.mock('../components/RouteMap', () => ({ RouteMap: () => null }));

// eslint-disable-next-line import/first
import { apiService } from '../services/api';

function makeTrain(trainId: string, overrides: Partial<Train> = {}): Train {
  return {
    train_id: trainId,
    journey_date: '2025-01-15',
    line: { code: 'MA', name: 'Main Line', color: '#FFAA00' },
    destination: 'Suffern',
    departure: { code: 'HB', name: 'Hoboken', scheduled_time: '2999-01-15T14:00:00-05:00' },
    arrival: { code: 'SF', name: 'Suffern', scheduled_time: '2999-01-15T15:10:00-05:00' },
    data_freshness: { last_updated: '', age_seconds: 0, update_count: 0, collection_method: null },
    data_source: 'NJT',
    observation_type: 'OBSERVED',
    is_cancelled: false,
    ...overrides,
  };
}

/** Wrap a Train as the single direct leg `/trips/search` returns. */
function makeDirectTrip(train: Train): TripOption {
  return {
    legs: [
      {
        train_id: train.train_id,
        journey_date: train.journey_date,
        line: train.line,
        data_source: train.data_source,
        destination: train.destination,
        boarding: train.departure,
        alighting: train.arrival,
        observation_type: train.observation_type,
        is_cancelled: train.is_cancelled,
      },
    ],
    transfers: [],
    departure_time: train.departure.scheduled_time ?? '',
    arrival_time: train.arrival.scheduled_time ?? '',
    total_duration_minutes: 70,
    is_direct: true,
  };
}

function makeAlert(alertId: string, header: string, affectedRouteIds: string[]): ServiceAlert {
  return {
    alert_id: alertId,
    data_source: 'NJT',
    alert_type: 'alert',
    affected_route_ids: affectedRouteIds,
    header_text: header,
    description_text: `${header} — details.`,
    active_periods: [],
  };
}

/** Render at an arbitrary /trains/:from/:to URL, including its query string. */
function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/trains/:from/:to" element={<TrainListPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('TrainListPage', () => {
  beforeEach(() => {
    vi.mocked(apiService.searchTrips).mockReset();
    vi.mocked(apiService.getDepartures).mockReset();
    vi.mocked(apiService.searchTrips).mockResolvedValue({ trips: [] } as never);
    vi.mocked(apiService.getDepartures).mockResolvedValue({ departures: [] } as never);
    vi.mocked(apiService.getRouteSummary).mockResolvedValue(null);
    vi.mocked(apiService.getServiceAlerts).mockResolvedValue({ alerts: [], count: 0 } as never);
  });

  describe('unscoped station-pair URLs (existing behaviour)', () => {
    it('uses the combined trip search and never the line-filtered endpoint', async () => {
      vi.mocked(apiService.searchTrips).mockResolvedValue({
        trips: [makeDirectTrip(makeTrain('3515'))],
      } as never);

      renderAt('/trains/HB/SF');

      expect(await screen.findByText('Train 3515')).toBeInTheDocument();
      expect(apiService.searchTrips).toHaveBeenCalledWith('HB', 'SF', 50, undefined, expect.anything());
      expect(apiService.getDepartures).not.toHaveBeenCalled();
    });

    it('leaves the operations summary unscoped', async () => {
      renderAt('/trains/HB/SF');

      await vi.waitFor(() => expect(apiService.getRouteSummary).toHaveBeenCalled());
      expect(apiService.getRouteSummary).toHaveBeenCalledWith('HB', 'SF', expect.anything(), undefined);
    });

    it('still returns transfer trips', async () => {
      // Transfers only exist on the unscoped path; the scoped path is a single
      // line by definition. TransferTripCard requires >= 2 legs and >= 1 transfer.
      const legOne = makeDirectTrip(makeTrain('T1')).legs[0];
      const legTwo = makeDirectTrip(makeTrain('T2')).legs[0];
      const transfer: TripOption = {
        legs: [legOne, legTwo],
        transfers: [
          {
            from_station: { code: 'SE', name: 'Secaucus' },
            to_station: { code: 'SE', name: 'Secaucus' },
            walk_minutes: 0,
            same_station: true,
          },
        ],
        departure_time: legOne.boarding.scheduled_time ?? '',
        arrival_time: legTwo.alighting.scheduled_time ?? '',
        total_duration_minutes: 95,
        is_direct: false,
      };
      vi.mocked(apiService.searchTrips).mockResolvedValue({ trips: [transfer] } as never);

      renderAt('/trains/HB/SF');

      // The compact transfer indicator renders the walk description, and the
      // card footer renders the total duration.
      expect(await screen.findByText('Same station')).toBeInTheDocument();
      expect(screen.getByText('1h 35m')).toBeInTheDocument();
      expect(apiService.getDepartures).not.toHaveBeenCalled();
    });

    it('treats a blank lines param as no scope at all', async () => {
      // `?lines=` must not send an empty code to the API — it should read as
      // "unscoped" and keep the ordinary combined search.
      renderAt('/trains/HB/SF?lines=');

      await vi.waitFor(() => expect(apiService.searchTrips).toHaveBeenCalled());
      expect(apiService.getDepartures).not.toHaveBeenCalled();
    });
  });

  describe('line-scoped URLs', () => {
    // NJT Main and Bergen both run HB -> SF. Same route params, different line
    // scope in the query string: the two must produce different requests, which
    // is the whole point of putting the scope in the URL (issue #1625).
    it('fetches the Main line board with server-side line filtering', async () => {
      vi.mocked(apiService.getDepartures).mockResolvedValue({
        departures: [makeTrain('3515')],
      } as never);

      renderAt('/trains/HB/SF?data_source=NJT&lines=MA%2CMa');

      expect(await screen.findByText('Train 3515')).toBeInTheDocument();
      expect(apiService.getDepartures).toHaveBeenCalledWith(
        'HB',
        expect.objectContaining({ to: 'SF', dataSources: 'NJT', lines: ['MA', 'Ma'], limit: 50 })
      );
      // The combined station-pair search must not run for a scoped board.
      expect(apiService.searchTrips).not.toHaveBeenCalled();
    });

    it('fetches the Bergen line board with its own codes', async () => {
      vi.mocked(apiService.getDepartures).mockResolvedValue({
        departures: [makeTrain('1250', { line: { code: 'BE', name: 'Bergen County Line', color: '#911' } })],
      } as never);

      renderAt('/trains/HB/SF?data_source=NJT&lines=BE%2CBe');

      expect(await screen.findByText('Train 1250')).toBeInTheDocument();
      expect(apiService.getDepartures).toHaveBeenCalledWith(
        'HB',
        expect.objectContaining({ to: 'SF', dataSources: 'NJT', lines: ['BE', 'Be'] })
      );
    });

    it('scopes the operations summary to the same line codes', async () => {
      renderAt('/trains/HB/SF?data_source=NJT&lines=MA%2CMa');

      await vi.waitFor(() => expect(apiService.getRouteSummary).toHaveBeenCalled());
      expect(apiService.getRouteSummary).toHaveBeenCalledWith(
        'HB', 'SF', expect.anything(), ['MA', 'Ma']
      );
    });

    it('filters service alerts to the line while keeping system-wide ones', async () => {
      vi.mocked(apiService.getDepartures).mockResolvedValue({
        departures: [makeTrain('3515')],
      } as never);
      vi.mocked(apiService.getServiceAlerts).mockResolvedValue({
        alerts: [
          makeAlert('m1', 'Main Line signal trouble', ['MA']),
          makeAlert('s1', 'Bergen County Line detour', ['BE']),
          makeAlert('w1', 'NJT systemwide advisory', []),
        ],
        count: 3,
      } as never);

      renderAt('/trains/HB/SF?data_source=NJT&lines=MA%2CMa');

      fireEvent.click(await screen.findByRole('button', { name: /show service alerts \(2\)/i }));

      expect(await screen.findByText('Main Line signal trouble')).toBeInTheDocument();
      expect(screen.getByText('NJT systemwide advisory')).toBeInTheDocument();
      expect(screen.queryByText('Bergen County Line detour')).not.toBeInTheDocument();
    });

    it('keeps the data source from the URL when the board comes back empty', async () => {
      // The derived-from-results source is unavailable with zero rows, so
      // without the URL fallback the alert banner would disappear entirely.
      vi.mocked(apiService.getDepartures).mockResolvedValue({ departures: [] } as never);
      vi.mocked(apiService.getServiceAlerts).mockResolvedValue({
        alerts: [makeAlert('w1', 'NJT systemwide advisory', [])],
        count: 1,
      } as never);

      renderAt('/trains/HB/SF?data_source=NJT&lines=MA%2CMa');

      fireEvent.click(await screen.findByRole('button', { name: /show service alerts/i }));
      expect(await screen.findByText('NJT systemwide advisory')).toBeInTheDocument();
    });

    it('trims whitespace around line codes before sending them', async () => {
      renderAt('/trains/HB/SF?data_source=NJT&lines=%20MA%20%2C%20Ma%20');

      await vi.waitFor(() => expect(apiService.getDepartures).toHaveBeenCalled());
      expect(apiService.getDepartures).toHaveBeenCalledWith(
        'HB',
        expect.objectContaining({ lines: ['MA', 'Ma'] })
      );
    });

    it('hides already-departed trains, matching the unscoped board', async () => {
      // `/trips/search` hardcodes hide_departed=true, but `/trains/departures`
      // defaults it to false. Without this the scoped board would keep listing a
      // train that has left the origin, which the combined board never shows.
      renderAt('/trains/HB/SF?data_source=NJT&lines=MA%2CMa');

      await vi.waitFor(() => expect(apiService.getDepartures).toHaveBeenCalled());
      expect(apiService.getDepartures).toHaveBeenCalledWith(
        'HB',
        expect.objectContaining({ hideDeparted: true })
      );
    });

    it('forwards the selected date so a future board is not silently today', async () => {
      // The heading says the chosen date; without the date param the API
      // defaults to today and the board would contradict its own label.
      const { container } = renderAt('/trains/HB/SF?data_source=NJT&lines=MA%2CMa');

      await vi.waitFor(() => expect(apiService.getDepartures).toHaveBeenCalled());

      const datePicker = container.querySelector('input[type="date"]') as HTMLInputElement;
      fireEvent.change(datePicker, { target: { value: '2999-01-20' } });

      await vi.waitFor(() =>
        expect(apiService.getDepartures).toHaveBeenCalledWith(
          'HB',
          expect.objectContaining({ date: '2999-01-20', lines: ['MA', 'Ma'] })
        )
      );
    });
  });
});
