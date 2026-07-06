import { describe, it, expect } from 'vitest';
import { render as rtlRender, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ReactElement } from 'react';
import { StopCard } from './StopCard';
import { Stop } from '../types';

// StopCard links known station names to /station/:code, so it needs a Router.
function render(ui: ReactElement) {
  return rtlRender(<BrowserRouter>{ui}</BrowserRouter>);
}

function makeStop(overrides: Partial<Stop> = {}): Stop {
  return {
    station: { code: 'NY', name: 'New York Penn Station' },
    stop_sequence: 1,
    scheduled_arrival: '2025-01-15T15:10:00-05:00',
    scheduled_departure: '2025-01-15T15:15:00-05:00',
    has_departed_station: false,
    ...overrides,
  };
}

describe('StopCard', () => {
  it('renders station name and code', () => {
    render(<StopCard stop={makeStop()} />);

    expect(screen.getByText('New York Penn Station')).toBeInTheDocument();
    expect(screen.getByText('NY')).toBeInTheDocument();
  });

  it('shows track assignment when available', () => {
    render(<StopCard stop={makeStop({ track: '7' })} />);

    expect(screen.getByText('Track 7')).toBeInTheDocument();
  });

  it('hides track when not assigned', () => {
    render(<StopCard stop={makeStop()} />);

    expect(screen.queryByText(/Track/)).not.toBeInTheDocument();
  });

  it('shows "Departed" indicator when station has been passed', () => {
    render(<StopCard stop={makeStop({ has_departed_station: true })} />);

    expect(screen.getByText('✓ Departed')).toBeInTheDocument();
  });

  it('hides arrival row for origin station', () => {
    render(<StopCard stop={makeStop()} isOrigin={true} />);

    expect(screen.queryByText('Arrival:')).not.toBeInTheDocument();
    expect(screen.getByText('Departure:')).toBeInTheDocument();
  });

  it('hides departure row for destination station', () => {
    render(<StopCard stop={makeStop()} isDestination={true} />);

    expect(screen.getByText('Arrival:')).toBeInTheDocument();
    expect(screen.queryByText('Departure:')).not.toBeInTheDocument();
  });

  it('leads with the live time and strikes through scheduled when delayed', () => {
    const { container } = render(<StopCard stop={makeStop({
      scheduled_arrival: '2025-01-15T15:10:00-05:00',
      updated_arrival: '2025-01-15T15:20:00-05:00',
    })} />);

    // Scheduled time struck through; live (delayed) time carries the warning color.
    expect(container.querySelector('.line-through')).toBeInTheDocument();
    expect(container.querySelector('.text-warning')).toBeInTheDocument();
  });

  it('colors an early stop green with the scheduled time struck through', () => {
    const { container } = render(<StopCard stop={makeStop({
      scheduled_arrival: '2025-01-15T15:10:00-05:00',
      actual_arrival: '2025-01-15T15:07:00-05:00',
    })} />);

    expect(container.querySelector('.line-through')).toBeInTheDocument();
    expect(container.querySelector('.text-success')).toBeInTheDocument();
  });

  it('shows a single scheduled time with no strikethrough when on schedule', () => {
    const { container } = render(<StopCard stop={makeStop()} />);

    expect(container.querySelector('.line-through')).not.toBeInTheDocument();
  });

  it('shows predicted arrival when available and no actual arrival', () => {
    render(<StopCard stop={makeStop({
      predicted_arrival: '2025-01-15T15:12:00-05:00',
    })} />);

    expect(screen.getByText('Predicted:')).toBeInTheDocument();
  });

  it('hides predicted arrival when actual arrival exists', () => {
    render(<StopCard stop={makeStop({
      actual_arrival: '2025-01-15T15:11:00-05:00',
      predicted_arrival: '2025-01-15T15:12:00-05:00',
    })} />);

    expect(screen.queryByText('Predicted:')).not.toBeInTheDocument();
  });
});
