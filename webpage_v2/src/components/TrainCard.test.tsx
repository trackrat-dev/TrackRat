import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { TrainCard } from './TrainCard';
import { Train } from '../types';

function makeTrain(overrides: Partial<Train> = {}): Train {
  return {
    train_id: '3515',
    journey_date: '2025-01-15',
    line: { code: 'NEC', name: 'Northeast Corridor', color: '#003DA5' },
    destination: 'New York Penn Station',
    departure: {
      code: 'TR',
      name: 'Trenton',
      scheduled_time: '2025-01-15T14:00:00-05:00',
    },
    arrival: {
      code: 'NY',
      name: 'New York Penn Station',
      scheduled_time: '2025-01-15T15:10:00-05:00',
    },
    data_freshness: { last_updated: '2025-01-15T14:00:00Z', age_seconds: 10, update_count: 1, collection_method: null },
    data_source: 'NJT',
    observation_type: 'OBSERVED',
    is_cancelled: false,
    ...overrides,
  };
}

// Wrap in BrowserRouter because ShareButton uses no router features but the test env needs it
function renderCard(train: Train, props: { departed?: boolean; from?: string; to?: string } = {}) {
  return render(
    <BrowserRouter>
      <TrainCard train={train} onClick={() => {}} {...props} />
    </BrowserRouter>
  );
}

describe('TrainCard', () => {
  it('renders train ID and line name', () => {
    renderCard(makeTrain());

    expect(screen.getByText('Train 3515')).toBeInTheDocument();
    expect(screen.getByText('Northeast Corridor')).toBeInTheDocument();
  });

  it('shows "TBD" for scheduled (not yet observed) trains', () => {
    renderCard(makeTrain({ observation_type: 'SCHEDULED' }));

    expect(screen.getByText('Train TBD')).toBeInTheDocument();
  });

  it('shows "On time" badge when no delay', () => {
    renderCard(makeTrain());

    expect(screen.getByText('On time')).toBeInTheDocument();
  });

  it('shows "Cancelled" badge for cancelled trains', () => {
    renderCard(makeTrain({ is_cancelled: true }));

    expect(screen.getByText('Cancelled')).toBeInTheDocument();
  });

  it('shows "Departed" badge when departed', () => {
    renderCard(makeTrain(), { departed: true });

    expect(screen.getByText('Departed')).toBeInTheDocument();
  });

  it('shows delay text when departure is delayed', () => {
    renderCard(makeTrain({
      departure: {
        code: 'TR',
        name: 'Trenton',
        scheduled_time: '2025-01-15T14:00:00-05:00',
        updated_time: '2025-01-15T14:05:00-05:00',
      },
    }));

    expect(screen.getByText('5 mins late')).toBeInTheDocument();
  });

  it('leads with the live time and strikes through the scheduled time when delayed', () => {
    const { container } = renderCard(makeTrain({
      departure: {
        code: 'TR',
        name: 'Trenton',
        scheduled_time: '2025-01-15T14:00:00-05:00',
        updated_time: '2025-01-15T14:21:00-05:00',
      },
    }));

    // Badge reports the magnitude; the scheduled time is struck through so the
    // rider's eye lands on the real (delayed) time.
    expect(screen.getByText('21 mins late')).toBeInTheDocument();
    expect(container.querySelector('.line-through')).toBeInTheDocument();
  });

  it('renders no strikethrough for an on-time train', () => {
    const { container } = renderCard(makeTrain());

    expect(container.querySelector('.line-through')).not.toBeInTheDocument();
  });

  it('shows "Boarding" when train is at departure station', () => {
    renderCard(
      makeTrain({
        train_position: { at_station_code: 'TR' },
      }),
      { from: 'TR' }
    );

    expect(screen.getByText('Boarding')).toBeInTheDocument();
  });

  it('shows boarding track when available and boarding', () => {
    renderCard(
      makeTrain({
        train_position: { at_station_code: 'TR' },
        departure: {
          code: 'TR',
          name: 'Trenton',
          scheduled_time: '2025-01-15T14:00:00-05:00',
          track: '5',
        },
      }),
      { from: 'TR' }
    );

    expect(screen.getByText('Boarding on Track 5')).toBeInTheDocument();
  });

  it('renders destination and data source', () => {
    renderCard(makeTrain());

    expect(screen.getByText('New York Penn Station')).toBeInTheDocument();
    expect(screen.getByText('NJT')).toBeInTheDocument();
  });

  it('applies dimmed styling when departed', () => {
    const { container } = renderCard(makeTrain(), { departed: true });

    const card = container.querySelector('[role="button"]');
    expect(card?.className).toContain('opacity-60');
  });

  describe('countdown', () => {
    afterEach(() => {
      vi.useRealTimers();
    });

    it('shows an "in N min" countdown for today\'s upcoming train', () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2026-07-06T16:00:00Z'));

      renderCard(makeTrain({
        journey_date: '2026-07-06',
        departure: { code: 'TR', name: 'Trenton', scheduled_time: '2026-07-06T16:20:00Z' },
      }));

      expect(screen.getByText('in 20 min')).toBeInTheDocument();
    });

    it('hides the countdown for future-date searches', () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2026-07-06T16:00:00Z'));

      renderCard(makeTrain({
        journey_date: '2026-07-08',
        departure: { code: 'TR', name: 'Trenton', scheduled_time: '2026-07-08T16:20:00Z' },
      }));

      expect(screen.queryByText(/in \d+ min/)).not.toBeInTheDocument();
    });

    it('hides the countdown for cancelled trains even today', () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2026-07-06T16:00:00Z'));

      renderCard(makeTrain({
        is_cancelled: true,
        journey_date: '2026-07-06',
        departure: { code: 'TR', name: 'Trenton', scheduled_time: '2026-07-06T16:20:00Z' },
      }));

      expect(screen.queryByText(/in \d+ min/)).not.toBeInTheDocument();
    });
  });
});
