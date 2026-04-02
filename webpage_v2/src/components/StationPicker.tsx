import { useState, useEffect } from 'react';
import { Station } from '../types';
import { searchStations, getGroupedPrimaryStations, SYSTEM_ORDER, SYSTEM_NAMES } from '../data/stations';
import { useAppStore } from '../store/appStore';

interface StationPickerProps {
  title: string;
  onSelect: (station: Station) => void;
  onClose: () => void;
}

export function StationPicker({ title, onSelect, onClose }: StationPickerProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Station[]>([]);
  const { preferredSystems, toggleSystem, loadPreferredSystems } = useAppStore();

  useEffect(() => {
    loadPreferredSystems();
  }, [loadPreferredSystems]);

  const activeFilter = preferredSystems.length > 0 ? preferredSystems : undefined;

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

  return (
    <div className="fixed inset-0 bg-text-primary/50 backdrop-blur-sm z-50 flex items-end md:items-center justify-center">
      <div className="bg-surface w-full md:max-w-2xl md:rounded-2xl rounded-t-2xl max-h-[80vh] flex flex-col">
        <div className="p-4 border-b border-text-muted/20 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-text-primary">{title}</h2>
          <button
            onClick={onClose}
            className="text-text-secondary hover:text-text-primary text-2xl leading-none"
          >
            ×
          </button>
        </div>

        <div className="p-4 border-b border-text-muted/20">
          <input
            type="text"
            value={query}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="Search stations..."
            autoFocus
            className="w-full px-4 py-3 bg-background border border-text-muted/30 rounded-lg text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-accent mb-3"
          />
          {/* System filter chips */}
          <div className="flex gap-1.5 overflow-x-auto pb-1 -mb-1 scrollbar-hide">
            {SYSTEM_ORDER.map(system => {
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
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium text-text-primary">{station.name}</div>
                        <div className="text-sm text-text-muted">{station.code}</div>
                      </div>
                      {station.system && (
                        <div className="text-xs text-text-muted bg-surface/80 px-2 py-0.5 rounded">
                          {station.system}
                        </div>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            )
          ) : (
            <div>
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
                        <div className="font-medium text-text-primary">{station.name}</div>
                        <div className="text-sm text-text-muted">{station.code}</div>
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
