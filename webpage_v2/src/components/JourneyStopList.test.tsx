import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { JourneyStopList } from './JourneyStopList';
import { Stop } from '../types';

// Train 1212 from issue #1840: Waldwick → Hoboken, rider boarded at Passaic.
const CODES = ['WK', 'RW', 'PS', 'DL', 'HB'];
const STOPS: Stop[] = CODES.map((code, i) => ({
  station: { code, name: `Station ${code}` },
  stop_sequence: i + 1,
  has_departed_station: i < 2,
}));

function renderList(journeyRange: [number, number] | null) {
  return render(
    <JourneyStopList
      stops={STOPS}
      journeyRange={journeyRange}
      renderStop={stop => <div key={stop.station.code} data-testid="stop">{stop.station.code}</div>}
    />
  );
}

function shownCodes(): string[] {
  const codes = screen.queryAllByTestId('stop').map(el => el.textContent ?? '');
  console.log('JourneyStopList shows:', codes.join(' → '));
  return codes;
}

describe('JourneyStopList', () => {
  it('trims to the journey and expands previous stops on tap', () => {
    renderList([2, 3]);
    expect(shownCodes()).toEqual(['PS', 'DL']);

    const toggle = screen.getByRole('button', { name: 'Train has previous stops' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(toggle);
    expect(shownCodes()).toEqual(['WK', 'RW', 'PS', 'DL']);
    expect(screen.getByRole('button', { name: 'Hide previous stops' })).toHaveAttribute('aria-expanded', 'true');

    fireEvent.click(screen.getByRole('button', { name: 'Hide previous stops' }));
    expect(shownCodes()).toEqual(['PS', 'DL']);
    expect(screen.getByRole('button', { name: 'Train has previous stops' })).toHaveAttribute('aria-expanded', 'false');
  });

  it('expands later stops independently of previous stops', () => {
    renderList([2, 3]);

    fireEvent.click(screen.getByRole('button', { name: 'Train has later stops' }));
    expect(shownCodes()).toEqual(['PS', 'DL', 'HB']);
    expect(screen.getByRole('button', { name: 'Hide later stops' })).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('button', { name: 'Train has previous stops' })).toHaveAttribute('aria-expanded', 'false');
  });

  it('omits toggles at the ends of the line', () => {
    renderList([0, 4]);
    expect(shownCodes()).toEqual(CODES);
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('shows every stop with no toggles when the journey is unknown', () => {
    renderList(null);
    expect(shownCodes()).toEqual(CODES);
    expect(screen.queryByRole('button')).toBeNull();
  });
});
