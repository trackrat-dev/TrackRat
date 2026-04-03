import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '../store/appStore';
import { StationPicker } from '../components/StationPicker';
import { getStationByCode, searchStations, SYSTEM_NAMES, SYSTEM_ORDER } from '../data/stations';
import { Station, TransitSystem } from '../types';
import { storageService } from '../services/storage';
import { getSuggestedRoute } from '../utils/ratsense';
import { buildTrainUrl } from '../utils/routes';
import { getTrainSearchCandidates, inferTrainSearchSystem } from '../utils/trainSearch';
import { APIRequestError, apiService } from '../services/api';

export function TripSelectionPage() {
  const navigate = useNavigate();
  const {
    selectedDeparture,
    selectedDestination,
    setDeparture,
    setDestination,
    loadLastRoute,
    recentTrips,
    favoriteRoutes,
    favoriteStations,
    preferredSystems,
    homeStation,
    workStation,
    loadRecentTrips,
    loadFavoriteRoutes,
    loadFavorites,
    loadCommuteProfile,
    loadPreferredSystems,
    addFavoriteRoute,
    toggleSystem,
  } = useAppStore();

  const [showDeparturePicker, setShowDeparturePicker] = useState(false);
  const [showDestinationPicker, setShowDestinationPicker] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearchingTrain, setIsSearchingTrain] = useState(false);
  const [trainSearchError, setTrainSearchError] = useState<string | null>(null);

  useEffect(() => {
    loadLastRoute();
    loadRecentTrips();
    loadFavoriteRoutes();
    loadFavorites();
    loadCommuteProfile();
    loadPreferredSystems();
  }, [loadLastRoute, loadRecentTrips, loadFavoriteRoutes, loadFavorites, loadCommuteProfile, loadPreferredSystems]);

  const suggestedRoute = useMemo(() => getSuggestedRoute({
    homeStation,
    workStation,
    recentTrips,
  }), [homeStation, workStation, recentTrips]);
  const activeSystems = preferredSystems.length > 0 ? preferredSystems : undefined;
  const stationResults = useMemo(
    () => searchStations(searchQuery, activeSystems),
    [searchQuery, activeSystems]
  );
  const otherSystemStationResults = useMemo(() => {
    if (!searchQuery.trim() || !activeSystems) return [];

    const primaryCodes = new Set(stationResults.map((station) => station.code));
    return searchStations(searchQuery).filter((station) => !primaryCodes.has(station.code));
  }, [searchQuery, activeSystems, stationResults]);
  const favoriteStationCodes = useMemo(
    () => new Set(favoriteStations.map((station) => station.id)),
    [favoriteStations]
  );
  const favoriteStationMatches = useMemo(
    () => stationResults.filter((station) => favoriteStationCodes.has(station.code)),
    [stationResults, favoriteStationCodes]
  );
  const standardStationMatches = useMemo(
    () => stationResults.filter((station) => !favoriteStationCodes.has(station.code)),
    [stationResults, favoriteStationCodes]
  );
  const trainSearchCandidates = useMemo(
    () => getTrainSearchCandidates(searchQuery, preferredSystems),
    [searchQuery, preferredSystems]
  );
  const shouldShowSearchResults = searchQuery.trim().length > 0;

  const currentRouteId = selectedDeparture && selectedDestination
    ? `${selectedDeparture.code}-${selectedDestination.code}`
    : null;
  const currentRouteIsFavorited = currentRouteId
    ? favoriteRoutes.some(route => route.id === currentRouteId)
    : false;

  const handleSearch = () => {
    if (selectedDeparture && selectedDestination) {
      navigate(`/trains/${selectedDeparture.code}/${selectedDestination.code}`);
    }
  };

  const handleSwapStations = () => {
    if (!selectedDeparture || !selectedDestination) return;

    setDeparture(selectedDestination);
    setDestination(selectedDeparture);
  };

  const handleStationSearchSelection = (station: Station) => {
    setTrainSearchError(null);

    if (!selectedDeparture) {
      setDeparture(station);
    } else if (!selectedDestination) {
      setDestination(station);
    } else {
      setDestination(station);
    }

    setSearchQuery('');
  };

  const handleTrainSearch = async () => {
    if (trainSearchCandidates.length === 0 || isSearchingTrain) return;

    setIsSearchingTrain(true);
    setTrainSearchError(null);

    for (const candidate of trainSearchCandidates) {
      let train = null;
      try {
        train = await apiService.findTrainByNumber(candidate, {
          dataSource: inferTrainSearchSystem(candidate),
        });
      } catch (error) {
        const message = error instanceof APIRequestError
          ? 'Train search is temporarily unavailable. Please try again.'
          : 'Train search failed. Please try again.';
        setTrainSearchError(message);
        setIsSearchingTrain(false);
        return;
      }

      if (train) {
        navigate(buildTrainUrl({
          trainId: train.train_id,
          from: train.route.origin_code,
          to: train.route.destination_code,
          date: train.journey_date,
          dataSource: train.data_source,
        }));
        setSearchQuery('');
        setIsSearchingTrain(false);
        return;
      }
    }

    setTrainSearchError(`Train ${searchQuery.trim()} was not found in the supported train systems.`);
    setIsSearchingTrain(false);
  };

  const trainSearchLabel = useMemo(() => {
    if (trainSearchCandidates.length === 0) return null;
    if (trainSearchCandidates.length === 1) return `Search train ${trainSearchCandidates[0]}`;
    return `Search train ${searchQuery.trim()} across ${trainSearchCandidates.length} systems`;
  }, [trainSearchCandidates, searchQuery]);

  return (
    <div className="max-w-2xl mx-auto">
      <h2 className="text-2xl font-bold mb-6 text-center text-text-primary">Where would you like to go?</h2>

      {suggestedRoute && (
        <button
          onClick={() => {
            setDeparture(suggestedRoute.departure);
            setDestination(suggestedRoute.destination);
            navigate(`/trains/${suggestedRoute.departure.code}/${suggestedRoute.destination.code}`);
          }}
          className="w-full mb-4 bg-accent/10 backdrop-blur-xl border border-accent/30 rounded-2xl p-4 text-left hover:bg-accent/15 transition-all"
        >
          <div className="text-xs font-semibold uppercase tracking-wide text-accent mb-1">
            {suggestedRoute.reason}
          </div>
          <div className="text-lg font-semibold text-text-primary">
            {suggestedRoute.departure.name} → {suggestedRoute.destination.name}
          </div>
        </button>
      )}

      {(!homeStation || !workStation) && (
        <button
          onClick={() => navigate('/favorites')}
          className="w-full mb-6 bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4 text-left hover:bg-surface transition-all"
        >
          <div className="text-sm font-semibold text-text-primary">Set your home and work stations</div>
          <div className="text-sm text-text-muted mt-1">
            Save your commute once so TrackRat can surface quicker suggestions.
          </div>
        </button>
      )}

      <div className="mb-6 bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4">
        <div className="text-sm font-semibold text-text-primary mb-3">Quick search</div>
        <input
          type="text"
          value={searchQuery}
          onChange={(event) => {
            setSearchQuery(event.target.value);
            if (trainSearchError) {
              setTrainSearchError(null);
            }
          }}
          placeholder="Search stations or train number"
          className="w-full px-4 py-3 bg-background border border-text-muted/30 rounded-xl text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-accent"
        />

        <div className="flex gap-1.5 overflow-x-auto pt-3">
          {SYSTEM_ORDER.map((system) => {
            const active = preferredSystems.length === 0 || preferredSystems.includes(system);
            return (
              <button
                key={system}
                onClick={() => toggleSystem(system)}
                className={`flex-shrink-0 px-2.5 py-1 rounded-full text-[11px] font-semibold transition-colors ${
                  active
                    ? 'bg-accent text-white'
                    : 'bg-surface border border-text-muted/20 text-text-muted hover:text-text-secondary'
                }`}
              >
                {SYSTEM_NAMES[system]}
              </button>
            );
          })}
        </div>

        {shouldShowSearchResults && (
          <div className="mt-4 space-y-3">
            <div className="text-xs text-text-muted">
              Search fills <span className="font-semibold text-text-secondary">From</span> first, then <span className="font-semibold text-text-secondary">To</span>. When both are set, quick search updates your destination.
            </div>

            {trainSearchLabel && (
              <button
                onClick={handleTrainSearch}
                disabled={isSearchingTrain}
                className="w-full bg-accent/10 border border-accent/30 rounded-xl p-4 text-left hover:bg-accent/15 transition-all disabled:opacity-60"
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-accent">{trainSearchLabel}</div>
                    <div className="text-xs text-text-muted mt-1">
                      {trainSearchCandidates.join(' • ')}
                    </div>
                  </div>
                  <div className="text-sm font-semibold text-accent">
                    {isSearchingTrain ? 'Searching…' : 'Open'}
                  </div>
                </div>
              </button>
            )}

            {trainSearchError && (
              <div className="text-sm text-error bg-error/10 border border-error/20 rounded-xl px-4 py-3">
                {trainSearchError}
              </div>
            )}

            {favoriteStationMatches.length > 0 && (
              <SearchResultSection
                title="Favorite stations"
                stations={favoriteStationMatches}
                onSelect={handleStationSearchSelection}
              />
            )}

            {standardStationMatches.length > 0 && (
              <SearchResultSection
                title="Stations"
                stations={standardStationMatches.slice(0, 6)}
                onSelect={handleStationSearchSelection}
              />
            )}

            {otherSystemStationResults.length > 0 && (
              <SearchResultSection
                title="Other systems"
                stations={otherSystemStationResults.slice(0, 6)}
                onSelect={handleStationSearchSelection}
                subdued
              />
            )}

            {stationResults.length === 0 && otherSystemStationResults.length === 0 && !trainSearchLabel && (
              <div className="text-sm text-text-muted bg-background border border-text-muted/20 rounded-xl px-4 py-3">
                No stations or trains matched your search.
              </div>
            )}
          </div>
        )}
      </div>

      {/* Station Selection */}
      <div className="space-y-4 mb-8">
        <button
          onClick={() => setShowDeparturePicker(true)}
          className="w-full bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-6 text-left hover:bg-surface transition-all"
        >
          <div className="text-sm text-text-muted mb-1">From</div>
          <div className="text-lg font-semibold text-text-primary">
            {selectedDeparture ? selectedDeparture.name : 'Choose a station'}
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
            {selectedDestination ? selectedDestination.name : 'Choose a station'}
          </div>
          {selectedDestination && (
            <div className="text-sm text-text-muted mt-1">{selectedDestination.code}</div>
          )}
        </button>

        <button
          onClick={handleSwapStations}
          disabled={!selectedDeparture || !selectedDestination}
          className="w-full bg-surface/40 backdrop-blur-xl border border-text-muted/20 text-text-primary font-semibold py-3 rounded-xl hover:bg-surface transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Swap Route
        </button>

        <button
          onClick={handleSearch}
          disabled={!selectedDeparture || !selectedDestination}
          className="w-full bg-accent text-white font-semibold py-4 rounded-xl hover:bg-accent/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Search Trains
        </button>

        {selectedDeparture && selectedDestination && (
          <button
            onClick={() => addFavoriteRoute(selectedDeparture, selectedDestination)}
            disabled={currentRouteIsFavorited}
            className="w-full bg-surface/50 backdrop-blur-xl border border-text-muted/20 text-text-primary font-semibold py-3 rounded-xl hover:bg-surface transition-colors disabled:opacity-60 disabled:cursor-default"
          >
            {currentRouteIsFavorited ? 'Route Saved' : 'Save This Route'}
          </button>
        )}
      </div>

      {/* Favorite Routes */}
      {favoriteRoutes.length > 0 && (
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-3">Favorite Routes</h3>
          <div className="space-y-2">
            {favoriteRoutes.slice(0, 5).map((route) => (
              <div
                key={route.id}
                className="w-full bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl p-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-medium text-text-primary">{route.departureName}</div>
                    <div className="text-sm text-text-muted">to {route.destinationName}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => navigate(`/trains/${route.departureCode}/${route.destinationCode}`)}
                      className="px-3 py-2 bg-accent text-white rounded-lg text-sm font-semibold hover:bg-accent/80 transition-colors"
                    >
                      Use
                    </button>
                    <button
                      onClick={() => navigate(`/trains/${route.destinationCode}/${route.departureCode}`)}
                      className="px-3 py-2 bg-surface border border-text-muted/20 text-text-primary rounded-lg text-sm font-semibold hover:bg-background transition-colors"
                    >
                      Reverse
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Trips */}
      {recentTrips.length > 0 && (
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-3">Recent Trips</h3>
          <div className="space-y-2">
            {recentTrips.slice(0, 5).map((trip) => (
              <button
                key={trip.id}
                onClick={() => {
                  const url = `/trains/${trip.departureCode}/${trip.destinationCode}`;
                  try {
                    storageService.saveLastRoute(
                      { code: trip.departureCode, name: trip.departureName },
                      { code: trip.destinationCode, name: trip.destinationName }
                    );
                  } catch {
                    // localStorage may be full or disabled; navigate anyway
                  }
                  navigate(url);
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
          title="Where are you leaving from?"
          onSelect={(station) => {
            setDeparture(station);
            setShowDeparturePicker(false);
          }}
          onClose={() => setShowDeparturePicker(false)}
        />
      )}

      {showDestinationPicker && (
        <StationPicker
          title="Where are you headed?"
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

function SearchResultSection({
  title,
  stations,
  onSelect,
  subdued = false,
}: {
  title: string;
  stations: Station[];
  onSelect: (station: Station) => void;
  subdued?: boolean;
}) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wide text-text-muted mb-2">
        {title}
      </div>
      <div className="space-y-2">
        {stations.map((station) => (
          <button
            key={station.code}
            onClick={() => onSelect(station)}
            className={`w-full border rounded-xl p-3 text-left transition-all ${
              subdued
                ? 'bg-surface/40 border-text-muted/15 hover:bg-surface/60'
                : 'bg-background border-text-muted/20 hover:bg-surface'
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="font-medium text-text-primary">{station.name}</div>
                <div className="text-sm text-text-muted">{station.code}</div>
              </div>
              {station.system && (
                <div className="text-xs text-text-muted bg-surface/80 px-2 py-1 rounded-full">
                  {formatSystemLabel(station.system)}
                </div>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function formatSystemLabel(system: TransitSystem) {
  return SYSTEM_NAMES[system] || system;
}
