import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '../store/appStore';
import { StationPicker } from '../components/StationPicker';
import { getStationByCode } from '../data/stations';

export function TripSelectionPage() {
  const navigate = useNavigate();
  const {
    selectedDeparture,
    selectedDestination,
    setDeparture,
    setDestination,
    loadLastRoute,
    recentTrips,
    favoriteStations,
    loadRecentTrips,
    loadFavorites,
  } = useAppStore();

  const [showDeparturePicker, setShowDeparturePicker] = useState(false);
  const [showDestinationPicker, setShowDestinationPicker] = useState(false);

  useEffect(() => {
    loadLastRoute();
    loadRecentTrips();
    loadFavorites();
  }, [loadLastRoute, loadRecentTrips, loadFavorites]);

  const handleSearch = () => {
    if (selectedDeparture && selectedDestination) {
      navigate(`/trains/${selectedDeparture.code}/${selectedDestination.code}`);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <h2 className="text-2xl font-bold mb-6 text-center text-text-primary">Plan Your Trip</h2>

      {/* Station Selection */}
      <div className="space-y-4 mb-8">
        <button
          onClick={() => setShowDeparturePicker(true)}
          className="w-full bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-6 text-left hover:bg-surface transition-all"
        >
          <div className="text-sm text-text-muted mb-1">From</div>
          <div className="text-lg font-semibold text-text-primary">
            {selectedDeparture ? selectedDeparture.name : 'Select departure station'}
          </div>
          {selectedDeparture && (
            <div className="text-sm text-text-muted mt-1">{selectedDeparture.code}</div>
          )}
        </button>

        <button
          onClick={() => setShowDestinationPicker(true)}
          className="w-full bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-6 text-left hover:bg-surface transition-all"
        >
          <div className="text-sm text-text-muted mb-1">To</div>
          <div className="text-lg font-semibold text-text-primary">
            {selectedDestination ? selectedDestination.name : 'Select destination station'}
          </div>
          {selectedDestination && (
            <div className="text-sm text-text-muted mt-1">{selectedDestination.code}</div>
          )}
        </button>

        <button
          onClick={handleSearch}
          disabled={!selectedDeparture || !selectedDestination}
          className="w-full bg-accent text-white font-semibold py-4 rounded-xl hover:bg-accent/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Search Trains
        </button>
      </div>

      {/* Recent Trips */}
      {recentTrips.length > 0 && (
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-3">Recent Trips</h3>
          <div className="space-y-2">
            {recentTrips.slice(0, 5).map((trip) => (
              <button
                key={trip.id}
                onClick={() => {
                  const from = getStationByCode(trip.departureCode);
                  const to = getStationByCode(trip.destinationCode);
                  if (from && to) {
                    setDeparture(from);
                    setDestination(to);
                  }
                }}
                className="w-full bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl p-4 text-left hover:bg-surface transition-all"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium text-text-primary">{trip.departureName}</div>
                    <div className="text-sm text-text-muted">to {trip.destinationName}</div>
                  </div>
                  <div className="text-2xl text-text-secondary">→</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Favorite Stations */}
      {favoriteStations.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold mb-3">Favorite Stations</h3>
          <div className="grid grid-cols-2 gap-2">
            {favoriteStations.map((station) => (
              <button
                key={station.id}
                onClick={() => {
                  const st = getStationByCode(station.id);
                  if (st) {
                    if (!selectedDeparture) {
                      setDeparture(st);
                    } else {
                      setDestination(st);
                    }
                  }
                }}
                className="bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl p-3 text-left hover:bg-surface transition-all"
              >
                <div className="font-medium text-sm text-text-primary">{station.name}</div>
                <div className="text-xs text-text-muted mt-1">{station.id}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Pickers */}
      {showDeparturePicker && (
        <StationPicker
          title="Select Departure Station"
          onSelect={(station) => {
            setDeparture(station);
            setShowDeparturePicker(false);
          }}
          onClose={() => setShowDeparturePicker(false)}
        />
      )}

      {showDestinationPicker && (
        <StationPicker
          title="Select Destination Station"
          onSelect={(station) => {
            setDestination(station);
            setShowDestinationPicker(false);
          }}
          onClose={() => setShowDestinationPicker(false)}
        />
      )}
    </div>
  );
}
