import { useEffect, useState } from 'react';
import { useAppStore } from '../store/appStore';
import { StationPicker } from '../components/StationPicker';

export function FavoritesPage() {
  const { favoriteStations, loadFavorites, addFavorite, removeFavorite } = useAppStore();
  const [showPicker, setShowPicker] = useState(false);

  useEffect(() => {
    loadFavorites();
  }, [loadFavorites]);

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-text-primary">Favorite Stations</h2>
        <button
          onClick={() => setShowPicker(true)}
          className="px-4 py-2 bg-accent text-white rounded-lg font-semibold hover:bg-accent/80 transition-colors"
        >
          + Add
        </button>
      </div>

      {favoriteStations.length === 0 ? (
        <div className="text-center py-12">
          <div className="text-4xl mb-4">⭐</div>
          <div className="text-text-muted mb-4">No favorite stations yet</div>
          <button
            onClick={() => setShowPicker(true)}
            className="px-6 py-3 bg-accent text-white rounded-lg font-semibold hover:bg-accent/80 transition-colors"
          >
            Add Your First Favorite
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {favoriteStations.map((station) => (
            <div
              key={station.id}
              className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4 flex items-center justify-between"
            >
              <div>
                <div className="font-semibold text-lg text-text-primary">{station.name}</div>
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
          title="Add Favorite Station"
          onSelect={(station) => {
            addFavorite(station);
            setShowPicker(false);
          }}
          onClose={() => setShowPicker(false)}
        />
      )}
    </div>
  );
}
