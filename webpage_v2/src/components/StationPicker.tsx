import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Station } from '../types';
import { searchStations, getGroupedPrimaryStations, AVAILABLE_SYSTEMS, SYSTEM_NAMES } from '../data/stations';
import { useAppStore } from '../store/appStore';
import { SubwayLineChips } from './SubwayLineChips';
import { buildQuickStations, collidingStationNames, QuickStationRole } from '../utils/stationSelection';

interface StationPickerProps {
  title: string;
  onSelect: (station: Station) => void;
  onClose: () => void;
}

function RoleIcon({ role }: { role: QuickStationRole }) {
  const common = {
    width: 18,
    height: 18,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    className: 'shrink-0 text-text-muted',
    'aria-hidden': true,
  };
  switch (role) {
    case 'home':
      return <svg {...common}><path d="M3 10.5 12 3l9 7.5" /><path d="M5 9.5V21h14V9.5" /></svg>;
    case 'work':
      return <svg {...common}><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>;
    case 'favorite':
      return <svg {...common}><path d="M12 3l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 18.9 6.2 21.4l1.1-6.5L2.6 9.8l6.5-.9z" /></svg>;
    case 'recent':
      return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 3" /></svg>;
  }
}

export function StationPicker({ title, onSelect, onClose }: StationPickerProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Station[]>([]);
  const {
    preferredSystems,
    toggleSystem,
    loadPreferredSystems,
    homeStation,
    workStation,
    favoriteStations,
    recentTrips,
    loadCommuteProfile,
    loadFavorites,
    loadRecentTrips,
  } = useAppStore();
  const dialogRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadPreferredSystems();
    loadCommuteProfile();
    loadFavorites();
    loadRecentTrips();
  }, [loadPreferredSystems, loadCommuteProfile, loadFavorites, loadRecentTrips]);

  // Body scroll lock
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, []);

  // Escape-to-close and focus trap
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose();
      return;
    }
    if (e.key === 'Tab' && dialogRef.current) {
      const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }, [onClose]);

  // Auto-focus search input
  useEffect(() => {
    searchInputRef.current?.focus();
  }, []);

  // Default (empty preferredSystems) means "all on" — but search/grouping must
  // still exclude disabled systems, so fall back to AVAILABLE_SYSTEMS rather than
  // an undefined filter (whose default path scans the full, disabled-inclusive list).
  const activeFilter = preferredSystems.length > 0 ? preferredSystems : AVAILABLE_SYSTEMS;

  const handleSearch = (value: string) => {
    setQuery(value);
    if (value.trim()) {
      setResults(searchStations(value, activeFilter));
    } else {
      setResults([]);
    }
  };

  // Re-run search when filter changes
  useEffect(() => {
    if (query.trim()) {
      setResults(searchStations(query, activeFilter));
    }
  }, [preferredSystems]);

  const handleSelect = (station: Station) => {
    onSelect(station);
    onClose();
  };

  const groupedStations = getGroupedPrimaryStations(activeFilter);
  const isSearching = query.trim().length > 0;

  // Personalized shortcuts (home/work/favorites/recents) shown above the raw
  // system groups when the user hasn't typed a query.
  const quickStations = useMemo(
    () => buildQuickStations({ homeStation, workStation, favoriteStations, recentTrips }),
    [homeStation, workStation, favoriteStations, recentTrips]
  );
  const quickCollisions = useMemo(
    () => collidingStationNames(quickStations.map((q) => q.station)),
    [quickStations]
  );

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="stationpicker-title"
      onKeyDown={handleKeyDown}
      className="fixed inset-0 bg-text-primary/50 backdrop-blur-sm z-50 flex items-end md:items-center justify-center"
    >
      <div className="bg-surface w-full md:max-w-2xl md:rounded-2xl rounded-t-2xl max-h-[80vh] flex flex-col">
        <div className="p-4 border-b border-text-muted/20 flex items-center justify-between">
          <h2 id="stationpicker-title" className="text-xl font-semibold text-text-primary">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="flex items-center justify-center w-11 h-11 -mr-2 rounded-full text-text-secondary hover:text-text-primary hover:bg-background text-2xl leading-none transition-colors"
          >
            ×
          </button>
        </div>

        <div className="p-4 border-b border-text-muted/20">
          <input
            ref={searchInputRef}
            type="text"
            value={query}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="Search stations..."
            className="w-full px-4 py-3 bg-background border border-text-muted/30 rounded-lg text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-accent mb-3"
          />
          {/* System filter chips */}
          <div className="flex gap-1.5 overflow-x-auto pb-1 -mb-1 scrollbar-hide">
            {AVAILABLE_SYSTEMS.map(system => {
              const active = preferredSystems.length === 0 || preferredSystems.includes(system);
              return (
                <button
                  key={system}
                  onClick={() => toggleSystem(system)}
                  className={`flex-shrink-0 px-2.5 py-1 rounded-full text-[11px] font-semibold transition-colors ${
                    active
                      ? 'bg-accent text-white'
                      : 'bg-surface/80 border border-text-muted/20 text-text-muted hover:text-text-secondary'
                  }`}
                >
                  {SYSTEM_NAMES[system]}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {isSearching ? (
            results.length === 0 ? (
              <div className="p-8 text-center text-text-muted">
                No stations found
              </div>
            ) : (
              <div className="divide-y divide-text-muted/20">
                {results.map((station) => (
                  <button
                    key={station.code}
                    onClick={() => handleSelect(station)}
                    className="w-full px-4 py-3 text-left hover:bg-background transition-colors"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-medium text-text-primary flex items-center gap-1.5">
                        {station.name}
                        {station.system === 'SUBWAY' && <SubwayLineChips stationCode={station.code} />}
                      </div>
                      {station.system && (
                        <div className="text-xs text-text-muted bg-surface/80 px-2 py-0.5 rounded whitespace-nowrap">
                          {SYSTEM_NAMES[station.system]}
                        </div>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            )
          ) : (
            <div>
              {quickStations.length > 0 && (
                <div>
                  <div className="px-4 py-2 bg-background/50 text-xs font-semibold text-text-muted uppercase tracking-wider sticky top-0">
                    Your stations
                  </div>
                  <div className="divide-y divide-text-muted/20">
                    {quickStations.map(({ station, role }) => (
                      <button
                        key={`${role}-${station.code}`}
                        onClick={() => handleSelect(station)}
                        className="w-full px-4 py-3 text-left hover:bg-background transition-colors flex items-center gap-3"
                      >
                        <RoleIcon role={role} />
                        <div className="min-w-0">
                          <div className="font-medium text-text-primary flex items-center gap-1.5">
                            {station.name}
                            {station.system === 'SUBWAY' && <SubwayLineChips stationCode={station.code} />}
                          </div>
                          {station.system && quickCollisions.has(station.name) && (
                            <div className="text-sm text-text-muted">{SYSTEM_NAMES[station.system]}</div>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {groupedStations.map((group) => (
                <div key={group.system}>
                  <div className="px-4 py-2 bg-background/50 text-xs font-semibold text-text-muted uppercase tracking-wider sticky top-0">
                    {group.name}
                  </div>
                  <div className="divide-y divide-text-muted/20">
                    {group.stations.map((station) => (
                      <button
                        key={station.code}
                        onClick={() => handleSelect(station)}
                        className="w-full px-4 py-3 text-left hover:bg-background transition-colors"
                      >
                        <div className="font-medium text-text-primary flex items-center gap-1.5">
                          {station.name}
                          {station.system === 'SUBWAY' && <SubwayLineChips stationCode={station.code} />}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
