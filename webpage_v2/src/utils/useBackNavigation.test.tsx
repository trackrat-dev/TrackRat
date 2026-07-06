import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import { useBackNavigation } from './useBackNavigation';

/** Renders the current pathname so tests can assert where navigation landed. */
function LocationProbe() {
  const location = useLocation();
  return <div data-testid="pathname">{location.pathname}</div>;
}

/** A detail page whose Back button uses the hook under test. */
function DetailPage({ fallback }: { fallback: string }) {
  const goBack = useBackNavigation(fallback);
  return (
    <>
      <button onClick={goBack}>Back</button>
      <LocationProbe />
    </>
  );
}

/**
 * The hook decides its branch from `window.history.state.idx`, which
 * React Router's BrowserRouter maintains but MemoryRouter does not. Tests set
 * it directly to simulate "arrived via in-app navigation" vs "cold deep-link",
 * while MemoryRouter provides the actual history stack to pop/replace against.
 */
function setHistoryIdx(idx: number | null) {
  window.history.replaceState(idx === null ? null : { idx }, '');
}

afterEach(() => {
  setHistoryIdx(null);
});

describe('useBackNavigation', () => {
  it('pops in-app history (navigate(-1)) when a prior entry exists (idx > 0)', () => {
    // Simulate having navigated into the app: idx advanced past the initial 0.
    setHistoryIdx(1);

    render(
      <MemoryRouter initialEntries={['/history', '/train/123']} initialIndex={1}>
        <Routes>
          <Route path="/history" element={<LocationProbe />} />
          <Route path="/train/:trainId" element={<DetailPage fallback="/trains/NY/NP" />} />
        </Routes>
      </MemoryRouter>
    );

    // Start on the deep page reached from /history.
    expect(screen.getByTestId('pathname')).toHaveTextContent('/train/123');

    fireEvent.click(screen.getByText('Back'));

    // Back pops the stack to where the user actually came from, not the fallback.
    expect(screen.getByTestId('pathname')).toHaveTextContent('/history');
  });

  it('replaces with the fallback path on a cold deep-link (idx === 0)', () => {
    // Fresh page load: React Router seeds idx to 0, nothing to pop back to.
    setHistoryIdx(0);

    render(
      <MemoryRouter initialEntries={['/train/123']} initialIndex={0}>
        <Routes>
          <Route path="/train/:trainId" element={<DetailPage fallback="/trains/NY/NP" />} />
          <Route path="/trains/:from/:to" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByTestId('pathname')).toHaveTextContent('/train/123');

    fireEvent.click(screen.getByText('Back'));

    // No in-app history, so Back stays in the app via the same-origin fallback.
    expect(screen.getByTestId('pathname')).toHaveTextContent('/trains/NY/NP');
  });

  it('falls back when window.history.state is absent (null)', () => {
    // Defensive: some entry points leave history.state null before any push.
    setHistoryIdx(null);

    render(
      <MemoryRouter initialEntries={['/trip']} initialIndex={0}>
        <Routes>
          <Route path="/trip" element={<DetailPage fallback="/departures" />} />
          <Route path="/departures" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByText('Back'));

    expect(screen.getByTestId('pathname')).toHaveTextContent('/departures');
  });
});
