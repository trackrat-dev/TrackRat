import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '../store/appStore';
import { StationPicker } from '../components/StationPicker';
import { Station } from '../types';
import { SubwayLineChips } from '../components/SubwayLineChips';

export function FavoritesPage() {
  const navigate = useNavigate();
  const {
    favoriteStations,
    favoriteRoutes,
    homeStation,
    workStation,
    loadFavorites,
    loadFavoriteRoutes,
    loadCommuteProfile,
    addFavorite,
    removeFavorite,
    removeFavoriteRoute,
    setHomeStation,
    setWorkStation,
  } = useAppStore();
  const [showPicker, setShowPicker] = useState(false);
  const [pickerMode, setPickerMode] = useState<'favorite' | 'home' | 'work'>('favorite');

  useEffect(() => {
    loadFavorites();
    loadFavoriteRoutes();
    loadCommuteProfile();
  }, [loadFavorites, loadFavoriteRoutes, loadCommuteProfile]);

  const pickerTitle = pickerMode === 'home'
    ? 'Set Home Station'
    : pickerMode === 'work'
    ? 'Set Work Station'
    : 'Add Favorite Station';

  const handleStationPick = (station: Station) => {
    if (pickerMode === 'home') {
      setHomeStation(station);
      setShowPicker(false);
      return;
    }

    if (pickerMode === 'work') {
      setWorkStation(station);
      setShowPicker(false);
      return;
    }

    addFavorite(station);
    setShowPicker(false);
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-text-primary">Saved Places</h2>
        <button
          onClick={() => {
            setPickerMode('favorite');
            setShowPicker(true);
          }}
          className="px-4 py-2 bg-accent text-white rounded-lg font-semibold hover:bg-accent/80 transition-colors"
        >
          + Add
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-8">
        <ProfileStationCard
          label="Home Station"
          station={homeStation}
          onSet={() => {
            setPickerMode('home');
            setShowPicker(true);
          }}
          onClear={homeStation ? () => setHomeStation(null) : undefined}
        />
        <ProfileStationCard
          label="Work Station"
          station={workStation}
          onSet={() => {
            setPickerMode('work');
            setShowPicker(true);
          }}
          onClear={workStation ? () => setWorkStation(null) : undefined}
        />
      </div>

      {favoriteRoutes.length > 0 && (
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-3 text-text-primary">Favorite Routes</h3>
          <div className="space-y-3">
            {favoriteRoutes.map((route) => (
              <div
                key={route.id}
                className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4 flex items-center justify-between"
              >
                <div>
                  <div className="font-semibold text-text-primary">
                    {route.departureName} → {route.destinationName}
                  </div>
                  <div className="text-sm text-text-muted">
                    {route.departureCode} to {route.destinationCode}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => navigate(`/trains/${route.departureCode}/${route.destinationCode}`)}
                    className="px-3 py-2 bg-accent text-white rounded-lg hover:bg-accent/80 transition-colors font-semibold"
                  >
                    Use
                  </button>
                  <button
                    onClick={() => navigate(`/trains/${route.destinationCode}/${route.departureCode}`)}
                    className="px-3 py-2 bg-surface border border-text-muted/20 text-text-primary rounded-lg hover:bg-background transition-colors font-semibold"
                  >
                    Reverse
                  </button>
                  <button
                    onClick={() => removeFavoriteRoute(route.id)}
                    className="px-3 py-2 bg-error/20 text-error rounded-lg hover:bg-error/30 transition-colors font-semibold"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {favoriteStations.length === 0 ? (
        <div className="text-center py-12">
          <div className="text-4xl mb-4">⭐</div>
          <div className="text-text-muted mb-4">No favorite stations yet</div>
          <button
            onClick={() => {
              setPickerMode('favorite');
              setShowPicker(true);
            }}
            className="px-6 py-3 bg-accent text-white rounded-lg font-semibold hover:bg-accent/80 transition-colors"
          >
            Add Your First Favorite
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <h3 className="text-lg font-semibold text-text-primary">Favorite Stations</h3>
          {favoriteStations.map((station) => (
            <div
              key={station.id}
              className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4 flex items-center justify-between"
            >
              <div>
                <div className="font-semibold text-lg text-text-primary flex items-center gap-1.5">
                  {station.name}
                  <SubwayLineChips stationCode={station.id} />
                </div>
                <div className="text-sm text-text-muted">{station.id}</div>
              </div>
              <button
                onClick={() => removeFavorite(station.id)}
                className="px-3 py-2 bg-error/20 text-error rounded-lg hover:bg-error/30 transition-colors font-semibold"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}

      {showPicker && (
        <StationPicker
          title={pickerTitle}
          onSelect={handleStationPick}
          onClose={() => setShowPicker(false)}
        />
      )}
    </div>
  );
}

function ProfileStationCard({
  label,
  station,
  onSet,
  onClear,
}: {
  label: string;
  station: Station | null;
  onSet: () => void;
  onClear?: () => void;
}) {
  return (
    <div className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4">
      <div className="text-sm text-text-muted mb-1">{label}</div>
      <div className="font-semibold text-text-primary flex items-center gap-1.5">
        {station ? station.name : 'Not set'}
        {station?.system === 'SUBWAY' && <SubwayLineChips stationCode={station.code} />}
      </div>
      {station && (
        <div className="text-sm text-text-muted mt-1">{station.code}</div>
      )}
      <div className="flex gap-2 mt-4">
        <button
          onClick={onSet}
          className="px-3 py-2 bg-accent text-white rounded-lg font-semibold hover:bg-accent/80 transition-colors"
        >
          {station ? 'Change' : 'Set'}
        </button>
        {onClear && (
          <button
            onClick={onClear}
            className="px-3 py-2 bg-error/20 text-error rounded-lg font-semibold hover:bg-error/30 transition-colors"
          >
            Clear
          </button>
        )}
      </div>
    </div>
  );
}
