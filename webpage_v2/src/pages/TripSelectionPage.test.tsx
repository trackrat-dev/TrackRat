import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { TripSelectionPage } from './TripSelectionPage';
import { useAppStore } from '../store/appStore';
import { getStationByCode } from '../data/stations';
import { storageService } from '../services/storage';

function resetStore() {
  useAppStore.setState({
    selectedDeparture: null,
    selectedDestination: null,
    recentTrips: [],
    favoriteRoutes: [],
    favoriteStations: [],
    preferredSystems: [],
    homeStation: null,
    workStation: null,
  });
}

function seedFavorite(code: string) {
  localStorage.setItem(
    'trackrat:favorites',
    JSON.stringify([{ id: code, name: getStationByCode(code)!.name, addedDate: new Date().toISOString() }])
  );
}

function seedLastRoute(fromCode: string, toCode: string) {
  localStorage.setItem(
    'trackrat:lastRoute',
    JSON.stringify({
      from: { code: fromCode, name: getStationByCode(fromCode)!.name },
      to: { code: toCode, name: getStationByCode(toCode)!.name },
    })
  );
}

function renderPage() {
  return render(
    <MemoryRouter>
      <TripSelectionPage />
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  resetStore();
});

describe('TripSelectionPage favorite slot filling', () => {
  it('fills From when tapping a favorite and From is empty', () => {
    seedFavorite('NY');
    renderPage();

    fireEvent.click(screen.getByRole('button', { name: /New York Penn Station/ }));

    expect(useAppStore.getState().selectedDeparture?.code).toBe('NY');
    expect(useAppStore.getState().selectedDestination).toBeNull();
  });

  it('fills To when From is already set and To is empty', () => {
    seedFavorite('NY');
    renderPage();

    // From set, To still empty.
    act(() => {
      useAppStore.setState({ selectedDeparture: getStationByCode('HB')! });
    });

    fireEvent.click(screen.getByRole('button', { name: /New York Penn Station/ }));

    expect(useAppStore.getState().selectedDeparture?.code).toBe('HB');
    expect(useAppStore.getState().selectedDestination?.code).toBe('NY');
  });

  it('asks From-or-To when both slots are already set, and can change From', () => {
    seedFavorite('NY');
    seedLastRoute('HB', 'NP'); // loadLastRoute fills both From (HB) and To (NP) on mount.
    renderPage();

    expect(useAppStore.getState().selectedDeparture?.code).toBe('HB');
    expect(useAppStore.getState().selectedDestination?.code).toBe('NP');

    // Tapping the favorite must NOT silently overwrite To — it opens the chooser.
    fireEvent.click(screen.getByRole('button', { name: /New York Penn Station/ }));
    expect(useAppStore.getState().selectedDestination?.code).toBe('NP');

    const setFrom = screen.getByRole('button', { name: /Set as From/ });
    const setTo = screen.getByRole('button', { name: /Set as To/ });
    expect(setFrom).toBeInTheDocument();
    expect(setTo).toBeInTheDocument();

    // Changing From via a favorite is now possible — the trap the issue describes.
    fireEvent.click(setFrom);
    expect(useAppStore.getState().selectedDeparture?.code).toBe('NY');
    expect(useAppStore.getState().selectedDestination?.code).toBe('NP');
    expect(screen.queryByText('Add to your route')).not.toBeInTheDocument();
  });

  it('dismisses the chooser on Escape without changing the route', () => {
    seedFavorite('NY');
    seedLastRoute('HB', 'NP');
    renderPage();

    fireEvent.click(screen.getByRole('button', { name: /New York Penn Station/ }));
    expect(screen.getByText('Add to your route')).toBeInTheDocument();

    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });

    expect(screen.queryByText('Add to your route')).not.toBeInTheDocument();
    expect(useAppStore.getState().selectedDeparture?.code).toBe('HB');
    expect(useAppStore.getState().selectedDestination?.code).toBe('NP');
  });

  it('does not render the fill-order explainer paragraph', () => {
    renderPage();
    fireEvent.change(screen.getByPlaceholderText('Search stations or train number'), {
      target: { value: 'Newark' },
    });
    expect(screen.queryByText(/Search fills/)).not.toBeInTheDocument();
  });
});

describe('TripSelectionPage quick search system filtering', () => {
  it('does not render disabled stations under Other systems', () => {
    storageService.savePreferredSystems(['NJT']);
    renderPage();

    fireEvent.change(screen.getByPlaceholderText('Search stations or train number'), {
      target: { value: 'union station' },
    });

    expect(screen.getByText('Other systems')).toBeInTheDocument();
    expect(screen.getByText('Washington Union Station')).toBeInTheDocument();
    expect(screen.queryByText('Chicago Union Station')).not.toBeInTheDocument();
    expect(screen.queryByText(/^Union Station$/)).not.toBeInTheDocument();
  });
});
