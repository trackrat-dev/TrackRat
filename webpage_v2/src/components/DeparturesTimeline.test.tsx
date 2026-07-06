import type { ComponentProps } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import {
  buildDeparturesTimeline,
  DeparturesTimelineView,
  TimelineRow,
} from './DeparturesTimeline';
import { Train } from '../types';

function makeTrain(id: string, overrides: Partial<Train> = {}): Train {
  return {
    train_id: id,
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
    data_freshness: { last_updated: '', age_seconds: 0, update_count: 0, collection_method: null },
    data_source: 'NJT',
    observation_type: 'OBSERVED',
    is_cancelled: false,
    ...overrides,
  };
}

const trainRows = (rows: TimelineRow[]) =>
  rows.filter((r): r is Extract<TimelineRow, { kind: 'train' }> => r.kind === 'train');

describe('buildDeparturesTimeline', () => {
  it('orders recent (reversed) → NOW → upcoming, most-recent just above the divider', () => {
    // recent arrives most-recent-first: C is newest, A is oldest.
    const recent = [makeTrain('C'), makeTrain('B'), makeTrain('A')];
    const upcoming = [makeTrain('D'), makeTrain('E'), makeTrain('F')];

    const rows = buildDeparturesTimeline(recent, upcoming);
    const ids = rows.map((r) => (r.kind === 'now' ? 'NOW' : r.train.train_id));

    // Oldest first, newest just above NOW, then upcoming soonest-first.
    expect(ids).toEqual(['A', 'B', 'C', 'NOW', 'D', 'E', 'F']);
  });

  it('places the NOW divider at index === recent count', () => {
    const rows = buildDeparturesTimeline(
      [makeTrain('C'), makeTrain('B'), makeTrain('A')],
      [makeTrain('D')]
    );
    expect(rows.findIndex((r) => r.kind === 'now')).toBe(3);
  });

  it('marks every row before the divider as departed and every row after as not', () => {
    const rows = buildDeparturesTimeline([makeTrain('B'), makeTrain('A')], [makeTrain('C')]);
    const nowIndex = rows.findIndex((r) => r.kind === 'now');

    rows.forEach((row, i) => {
      if (row.kind !== 'train') return;
      expect(row.departed).toBe(i < nowIndex);
    });
  });

  it('handles empty recent: NOW divider sits at the top', () => {
    const rows = buildDeparturesTimeline([], [makeTrain('D'), makeTrain('E')]);
    const ids = rows.map((r) => (r.kind === 'now' ? 'NOW' : r.train.train_id));
    expect(ids).toEqual(['NOW', 'D', 'E']);
    expect(rows.findIndex((r) => r.kind === 'now')).toBe(0);
  });

  it('handles empty upcoming: NOW divider sits at the bottom', () => {
    const rows = buildDeparturesTimeline([makeTrain('B'), makeTrain('A')], []);
    const ids = rows.map((r) => (r.kind === 'now' ? 'NOW' : r.train.train_id));
    expect(ids).toEqual(['A', 'B', 'NOW']);
    expect(rows.findIndex((r) => r.kind === 'now')).toBe(rows.length - 1);
  });

  it('always includes exactly one NOW divider, even when both feeds are empty', () => {
    const rows = buildDeparturesTimeline([], []);
    expect(rows).toEqual([{ kind: 'now' }]);
  });

  it('caps recent and upcoming to their max counts', () => {
    const recent = ['E', 'D', 'C', 'B', 'A'].map((id) => makeTrain(id));
    const upcoming = ['F', 'G', 'H', 'I', 'J'].map((id) => makeTrain(id));

    const rows = buildDeparturesTimeline(recent, upcoming, { maxRecent: 2, maxUpcoming: 2 });
    const ids = rows.map((r) => (r.kind === 'now' ? 'NOW' : r.train.train_id));

    // The 2 most-recent (E, D) reversed → D, E; first 2 upcoming → F, G.
    expect(ids).toEqual(['D', 'E', 'NOW', 'F', 'G']);
  });

  it('dedups a train appearing in both feeds, keeping it as a recent/departed row only', () => {
    const shared = makeTrain('X');
    const rows = buildDeparturesTimeline([shared], [shared, makeTrain('Y')]);
    const ids = rows.map((r) => (r.kind === 'now' ? 'NOW' : r.train.train_id));

    expect(ids).toEqual(['X', 'NOW', 'Y']);
    const xRow = trainRows(rows).find((r) => r.train.train_id === 'X');
    expect(xRow?.departed).toBe(true);
  });

  it('dedups by train_id + journey_date, not train_id alone', () => {
    const recent = [makeTrain('X', { journey_date: '2025-01-15' })];
    // Same number, different service day — a genuinely different journey.
    const upcoming = [makeTrain('X', { journey_date: '2025-01-16' })];

    const rows = buildDeparturesTimeline(recent, upcoming);
    const ids = rows.map((r) => (r.kind === 'now' ? 'NOW' : r.train.train_id));
    expect(ids).toEqual(['X', 'NOW', 'X']);
  });
});

describe('DeparturesTimelineView', () => {
  function renderView(rows: TimelineRow[], props: Partial<ComponentProps<typeof DeparturesTimelineView>> = {}) {
    return render(
      <BrowserRouter>
        <DeparturesTimelineView
          rows={rows}
          from="TR"
          to="NY"
          onSelect={() => {}}
          {...props}
        />
      </BrowserRouter>
    );
  }

  it('renders the NOW divider with the current time label', () => {
    renderView(buildDeparturesTimeline([makeTrain('A')], [makeTrain('B')]));
    expect(screen.getByText(/^NOW · /)).toBeInTheDocument();
  });

  it('applies dimmed (departed) styling to recent rows and not to upcoming rows', () => {
    const { container } = renderView(
      buildDeparturesTimeline([makeTrain('A')], [makeTrain('B')])
    );

    const cards = container.querySelectorAll('[role="button"]');
    expect(cards).toHaveLength(2);
    // Recent row (rendered first) is dimmed; upcoming row is not.
    expect(cards[0].className).toContain('opacity-60');
    expect(cards[1].className).not.toContain('opacity-60');
  });

  it('shows the departed badge on recent rows', () => {
    renderView(buildDeparturesTimeline([makeTrain('A')], []));
    expect(screen.getByText('Departed')).toBeInTheDocument();
  });

  it('calls onSelect with the clicked train', () => {
    const onSelect = vi.fn();
    const upcoming = makeTrain('B');
    const { container } = renderView(
      buildDeparturesTimeline([makeTrain('A')], [upcoming]),
      { onSelect }
    );

    // The card wrappers carry an explicit role="button"; the inner ShareButtons
    // are native <button>s without that attribute, so this selects only cards.
    const cards = container.querySelectorAll('[role="button"]');
    fireEvent.click(cards[1]); // the upcoming train card

    expect(onSelect).toHaveBeenCalledWith(upcoming);
  });

  it('shows "No more trains scheduled" when there are no upcoming trains', () => {
    renderView(buildDeparturesTimeline([makeTrain('A')], []));
    expect(screen.getByText('No more trains scheduled')).toBeInTheDocument();
  });

  it('does not show the "No more trains" message when upcoming trains exist', () => {
    renderView(buildDeparturesTimeline([makeTrain('A')], [makeTrain('B')]));
    expect(screen.queryByText('No more trains scheduled')).not.toBeInTheDocument();
  });

  it('links to the full departures list', () => {
    renderView(buildDeparturesTimeline([], [makeTrain('B')]));
    const link = screen.getByText('View All Departures →').closest('a');
    expect(link).toHaveAttribute('href', '/trains/TR/NY');
  });
});
