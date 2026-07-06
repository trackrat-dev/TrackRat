import { useState, useCallback, useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Train } from '../types';
import { apiService } from '../services/api';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { TrainCard } from '../components/TrainCard';
import { ServiceAlertBanner } from '../components/ServiceAlertBanner';
import { getStationByCode, DISABLED_SYSTEMS } from '../data/stations';
import { formatTime } from '../utils/date';
import { buildTrainUrl } from '../utils/routes';
import { usePolling } from '../utils/usePolling';

/**
 * Single-station departure board: "what's leaving {station} right now?".
 * Backed by GET /trains/departures?from={code}&hide_departed=true (no `to`),
 * which returns upcoming trains across every line serving the station.
 * Deep-linkable and sharable at /station/:code.
 */
export function StationDeparturesPage() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();

  const [trains, setTrains] = useState<Train[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const station = code ? getStationByCode(code) : undefined;

  const fetchDepartures = useCallback(async (signal?: AbortSignal) => {
    if (!code) return;
    try {
      const response = await apiService.getStationDepartures(code, 50, signal);
      // Defensively drop any app-disabled systems the backend might still
      // surface (keeps web/backend disabled sets from drifting apart).
      const visible = response.departures.filter(
        (train) => !DISABLED_SYSTEMS.has(train.data_source)
      );
      setTrains(visible);
      setLastUpdated(new Date());
      setError(null);
      setLoading(false);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      setError(err instanceof Error ? err.message : 'Failed to load departures');
      setLoading(false);
    }
  }, [code]);

  // Polling: visibility-aware, aborts in-flight on unmount/code change.
  // Skip entirely for an unknown station (nothing to fetch).
  usePolling(fetchDepartures, [code], { enabled: !!station });

  // Show service alerts only when every departure shares one data source
  // (matches TrainListPage — a mixed board has no single relevant feed).
  const serviceAlertDataSource = useMemo(() => {
    const sources = new Set(trains.map((t) => t.data_source));
    return sources.size === 1 ? [...sources][0] : undefined;
  }, [trains]);

  if (!code || !station) {
    return (
      <ErrorMessage
        message="Station not found"
        onRetry={() => navigate('/departures')}
      />
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <button
          onClick={() => navigate('/departures')}
          className="text-accent hover:text-accent/80 mb-4 flex items-center gap-2 font-semibold"
        >
          ← Back
        </button>
        <h2 className="text-2xl font-bold text-text-primary text-center">
          Departures — {station.name}
        </h2>
        {lastUpdated && (
          <div className="flex items-center justify-center mt-2">
            <span className="text-sm text-text-muted">
              Updated at {formatTime(lastUpdated.toISOString())}
            </span>
          </div>
        )}
      </div>

      {serviceAlertDataSource && (
        <ServiceAlertBanner dataSource={serviceAlertDataSource} />
      )}

      {loading && trains.length === 0 ? (
        <LoadingSpinner />
      ) : error ? (
        <ErrorMessage message={error} onRetry={() => fetchDepartures()} />
      ) : trains.length === 0 ? (
        <div className="text-center py-12">
          <div className="text-4xl mb-4">🚉</div>
          <div className="text-text-muted mb-4">
            No upcoming departures from {station.name} right now
          </div>
          <Link to="/departures" className="text-accent hover:text-accent/80 font-semibold">
            Plan a trip instead →
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {trains.map((train) => (
            <TrainCard
              key={`${train.data_source}-${train.train_id}-${train.journey_date}`}
              train={train}
              onClick={() => navigate(buildTrainUrl({
                trainId: train.train_id,
                from: code,
                date: train.journey_date,
                dataSource: train.data_source,
              }))}
              from={code}
            />
          ))}
        </div>
      )}
    </div>
  );
}
