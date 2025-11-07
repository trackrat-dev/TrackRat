import { useState } from 'react';
import { Station } from '../types';
import { searchStations, getPrimaryDepartureStations } from '../data/stations';

interface StationPickerProps {
  title: string;
  onSelect: (station: Station) => void;
  onClose: () => void;
}

export function StationPicker({ title, onSelect, onClose }: StationPickerProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Station[]>([]);

  const handleSearch = (value: string) => {
    setQuery(value);
    if (value.trim()) {
      setResults(searchStations(value));
    } else {
      setResults([]);
    }
  };

  const handleSelect = (station: Station) => {
    onSelect(station);
    onClose();
  };

  const primaryStations = getPrimaryDepartureStations();
  const displayStations = query.trim() ? results : primaryStations;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-end md:items-center justify-center">
      <div className="bg-surface w-full md:max-w-2xl md:rounded-2xl rounded-t-2xl max-h-[80vh] flex flex-col">
        <div className="p-4 border-b border-white/10 flex items-center justify-between">
          <h2 className="text-xl font-semibold">{title}</h2>
          <button
            onClick={onClose}
            className="text-white/70 hover:text-white text-2xl leading-none"
          >
            ×
          </button>
        </div>

        <div className="p-4 border-b border-white/10">
          <input
            type="text"
            value={query}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="Search stations..."
            autoFocus
            className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-accent"
          />
        </div>

        <div className="flex-1 overflow-y-auto">
          {displayStations.length === 0 ? (
            <div className="p-8 text-center text-white/50">
              {query.trim() ? 'No stations found' : 'Start typing to search'}
            </div>
          ) : (
            <div className="divide-y divide-white/10">
              {displayStations.map((station) => (
                <button
                  key={station.code}
                  onClick={() => handleSelect(station)}
                  className="w-full px-4 py-3 text-left hover:bg-white/5 transition-colors"
                >
                  <div className="font-medium">{station.name}</div>
                  <div className="text-sm text-white/50">{station.code}</div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
