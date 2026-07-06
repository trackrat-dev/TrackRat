import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { StationPicker } from './StationPicker';
import { useAppStore } from '../store/appStore';
import { storageService } from '../services/storage';
import { getStationByCode } from '../data/stations';

describe('StationPicker', () => {
  let onSelect: ReturnType<typeof vi.fn>;
  let onClose: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onSelect = vi.fn();
    onClose = vi.fn();
    localStorage.clear();
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
  });

  afterEach(() => {
    document.body.style.overflow = '';
  });

  function renderPicker(title = 'Select Station') {
    return render(
      <StationPicker title={title} onSelect={onSelect} onClose={onClose} />
    );
  }

  describe('dialog semantics', () => {
    it('renders with role="dialog" and aria-modal="true"', () => {
      renderPicker();
      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
      expect(dialog).toHaveAttribute('aria-modal', 'true');
    });

    it('has aria-labelledby pointing to the title', () => {
      renderPicker('Pick a Station');
      const dialog = screen.getByRole('dialog');
      const titleId = dialog.getAttribute('aria-labelledby');
      expect(titleId).toBe('stationpicker-title');
      const heading = document.getElementById(titleId!);
      expect(heading).toHaveTextContent('Pick a Station');
    });

    it('close button has aria-label', () => {
      renderPicker();
      const closeBtn = screen.getByRole('button', { name: 'Close' });
      expect(closeBtn).toBeInTheDocument();
    });
  });

  describe('Escape-to-close', () => {
    it('calls onClose when Escape is pressed', () => {
      renderPicker();
      const dialog = screen.getByRole('dialog');
      fireEvent.keyDown(dialog, { key: 'Escape' });
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('does not call onClose for other keys', () => {
      renderPicker();
      const dialog = screen.getByRole('dialog');
      fireEvent.keyDown(dialog, { key: 'Enter' });
      fireEvent.keyDown(dialog, { key: 'a' });
      expect(onClose).not.toHaveBeenCalled();
    });
  });

  describe('body scroll lock', () => {
    it('sets body overflow to hidden on mount', () => {
      renderPicker();
      expect(document.body.style.overflow).toBe('hidden');
    });

    it('restores previous body overflow on unmount', () => {
      document.body.style.overflow = 'auto';
      const { unmount } = renderPicker();
      expect(document.body.style.overflow).toBe('hidden');
      unmount();
      expect(document.body.style.overflow).toBe('auto');
    });

    it('restores empty string when body had no overflow set', () => {
      document.body.style.overflow = '';
      const { unmount } = renderPicker();
      expect(document.body.style.overflow).toBe('hidden');
      unmount();
      expect(document.body.style.overflow).toBe('');
    });
  });

  describe('focus trap', () => {
    it('wraps focus from last to first element on Tab', () => {
      renderPicker();
      const dialog = screen.getByRole('dialog');
      const focusableElements = dialog.querySelectorAll<HTMLElement>('button, input');
      const lastElement = focusableElements[focusableElements.length - 1];

      lastElement.focus();
      expect(document.activeElement).toBe(lastElement);

      fireEvent.keyDown(dialog, { key: 'Tab' });
      expect(document.activeElement).toBe(focusableElements[0]);
    });

    it('wraps focus from first to last element on Shift+Tab', () => {
      renderPicker();
      const dialog = screen.getByRole('dialog');
      const focusableElements = dialog.querySelectorAll<HTMLElement>('button, input');
      const firstElement = focusableElements[0];

      firstElement.focus();
      expect(document.activeElement).toBe(firstElement);

      fireEvent.keyDown(dialog, { key: 'Tab', shiftKey: true });
      expect(document.activeElement).toBe(focusableElements[focusableElements.length - 1]);
    });
  });

  describe('auto-focus', () => {
    it('focuses the search input on mount', () => {
      renderPicker();
      const searchInput = screen.getByPlaceholderText('Search stations...');
      expect(document.activeElement).toBe(searchInput);
    });
  });

  describe('close button', () => {
    it('calls onClose when close button is clicked', () => {
      renderPicker();
      fireEvent.click(screen.getByRole('button', { name: 'Close' }));
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('has a touch target of at least 44x44 (w-11 h-11)', () => {
      renderPicker();
      const closeBtn = screen.getByRole('button', { name: 'Close' });
      expect(closeBtn.className).toContain('w-11');
      expect(closeBtn.className).toContain('h-11');
    });
  });

  describe('Your stations section', () => {
    function seedSavedStations() {
      // home / work carry full stations; favorites + recents are code-only in storage.
      storageService.setHomeStation(getStationByCode('NY')!);
      storageService.setWorkStation(getStationByCode('NP')!);
      storageService.addFavoriteStation({ id: 'S127', name: getStationByCode('S127')!.name });
      storageService.saveRecentTrip({
        departureCode: 'HB',
        departureName: 'Hoboken',
        destinationCode: 'SE',
        destinationName: 'Secaucus Upper Lvl',
      });
    }

    it('is absent when the user has no saved stations or trips', () => {
      renderPicker();
      expect(screen.queryByText('Your stations')).not.toBeInTheDocument();
    });

    it('renders home, work, favorites, and recents above the system groups', () => {
      seedSavedStations();
      renderPicker();

      const header = screen.getByText('Your stations');
      expect(header).toBeInTheDocument();

      // Scope to the "Your stations" section (these names also appear in the
      // NJT system group below, so an unscoped query would match twice).
      const section = within(header.parentElement as HTMLElement);
      expect(section.getByRole('button', { name: /New York Penn Station/ })).toBeInTheDocument();
      expect(section.getByRole('button', { name: /Newark Penn Station/ })).toBeInTheDocument();
      // Recent-trip stations surface too.
      expect(section.getByRole('button', { name: /Hoboken/ })).toBeInTheDocument();
      expect(section.getByRole('button', { name: /Secaucus Upper Lvl/ })).toBeInTheDocument();
    });

    it('never shows raw station codes as subtitles', () => {
      seedSavedStations();
      renderPicker();
      // Codes like the subway id "S127" must not leak as visible text anywhere.
      expect(screen.queryByText('S127')).not.toBeInTheDocument();
      expect(screen.queryByText('NY')).not.toBeInTheDocument();
      expect(screen.queryByText('HB')).not.toBeInTheDocument();
    });

    it('selecting a Your-stations row selects that station and closes', () => {
      seedSavedStations();
      renderPicker();
      // The first "New York Penn Station" button is the Home row (rendered above the groups).
      fireEvent.click(screen.getAllByRole('button', { name: /New York Penn Station/ })[0]);
      expect(onSelect).toHaveBeenCalledTimes(1);
      expect(onSelect.mock.calls[0][0].code).toBe('NY');
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('hides Your stations once a query is typed', () => {
      seedSavedStations();
      renderPicker();
      fireEvent.change(screen.getByPlaceholderText('Search stations...'), {
        target: { value: 'Newark' },
      });
      expect(screen.queryByText('Your stations')).not.toBeInTheDocument();
    });
  });
});
