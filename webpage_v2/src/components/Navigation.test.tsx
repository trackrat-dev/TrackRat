import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Navigation } from './Navigation';

function renderNavAt(path: string, variant: 'header' | 'bottom' = 'header') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Navigation variant={variant} />
    </MemoryRouter>
  );
}

describe('Navigation active-tab mapping', () => {
  // Each route family should light exactly one tab. getByRole with current:'page'
  // is singular, so it also asserts that no other tab is simultaneously active.
  it.each([
    ['/departures', 'Departures'],
    ['/trains/NP/NY', 'Departures'],
    ['/train/7232/NP/NY', 'Departures'],
    ['/trip', 'Departures'],
    ['/status', 'Status'],
    ['/route/NP/NY', 'Status'],
    ['/favorites', 'Favorites'],
    ['/history', 'History'],
  ])('lights exactly one tab at %s -> %s', (path, expectedLabel) => {
    renderNavAt(path);
    const active = screen.getByRole('link', { current: 'page' });
    expect(active).toHaveTextContent(expectedLabel);
  });

  it('renders all four tabs for both variants', () => {
    for (const variant of ['header', 'bottom'] as const) {
      const { unmount } = renderNavAt('/departures', variant);
      for (const label of ['Departures', 'Status', 'Favorites', 'History']) {
        expect(screen.getByText(label)).toBeInTheDocument();
      }
      unmount();
    }
  });

  it('lights no tab on a route outside every family', () => {
    renderNavAt('/');
    expect(screen.queryByRole('link', { current: 'page' })).toBeNull();
  });
});
