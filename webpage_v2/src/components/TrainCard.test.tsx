import { describe, it, expect } from 'vitest';
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

    const button = container.querySelector('button');
    expect(button?.className).toContain('opacity-60');
  });
});
