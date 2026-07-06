import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate, Navigate, Link } from 'react-router-dom';
import { LineInfo, Train } from '../types';
import { apiService } from '../services/api';
import { useAppStore } from '../store/appStore';
import { getStationByCode, SYSTEM_NAMES } from '../data/stations';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { TrainCard } from '../components/TrainCard';
import { ServiceAlertBanner } from '../components/ServiceAlertBanner';
import { SubwayLineChips } from '../components/SubwayLineChips';
import { buildTrainUrl } from '../utils/routes';
import { usePolling } from '../utils/usePolling';

// Match iOS StationDetailsViewModel: 120-minute recent window; show only the
// most recent handful above the NOW divider so the dimmed section stays small.
const RECENT_WINDOW_MINUTES = 120;
const RECENT_DISPLAY_LIMIT = 5;
const UPCOMING_LIMIT = 30;

function bestDepartureTime(train: Train): string | undefined {
  return (
    train.departure.actual_time ||
    train.departure.updated_time ||
    train.departure.scheduled_time ||
    undefined
  );
}

/** Sort by best-known departure time, earliest first. */
function byDepartureAscending(a: Train, b: Train): number {
  const ta = bestDepartureTime(a);
  const tb = bestDepartureTime(b);
  if (!ta) return 1;
  if (!tb) return -1;
  return new Date(ta).getTime() - new Date(tb).getTime();
}

/** Horizontal rule with a centered "Now" pill separating recent from upcoming. */
function NowDivider() {
  return (
    <div className="flex items-center gap-3 py-1" aria-label="Now">
      <div className="flex-1 h-px bg-accent/40" />
      <span className="text-xs font-bold uppercase tracking-wider text-accent">Now</span>
      <div className="flex-1 h-px bg-accent/40" />
    </div>
  );
}

function ActionButton({
  label,
  icon,
  active,
  onClick,
}: {
  label: string;
  icon: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={`flex-1 flex flex-col items-center gap-1 py-3 rounded-xl font-semibold text-sm transition-colors ${
        active
          ? 'bg-accent/20 text-accent border border-accent/40'
          : 'bg-surface/70 backdrop-blur-xl border border-text-muted/20 text-text-primary hover:bg-surface'
      }`}
    >
      <span className="text-lg leading-none" aria-hidden="true">{icon}</span>
      <span>{label}</span>
    </button>
  );
}

export function StationDetailsPage() {
  const { code: rawCode } = useParams<{ code: string }>();
  const navigate = useNavigate();

  const {
    favoriteStations,
    homeStation,
    workStation,
    loadFavorites,
    loadCommuteProfile,
    addFavorite,
    removeFavorite,
    setHomeStation,
    setWorkStation,
  } = useAppStore();

  const [upcoming, setUpcoming] = useState<Train[]>([]);
  const [recent, setRecent] = useState<Train[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Resolve alias-aware; uppercase so lowercase URLs still resolve.
  const station = rawCode ? getStationByCode(rawCode.toUpperCase()) : undefined;
  const stationCode = station?.code;
  // True only when the URL already uses the canonical code — an alias/casing
  // mismatch redirects below, so don't poll for the soon-to-unmount route.
  const isCanonical = Boolean(stationCode) && station?.code === rawCode;

  useEffect(() => {
    loadFavorites();
    loadCommuteProfile();
  }, [loadFavorites, loadCommuteProfile]);

  const fetchBoard = useCallback(
    async (signal?: AbortSignal) => {
      if (!stationCode) return;
      try {
        const [up, rec] = await Promise.all([
          apiService.getDepartures(stationCode, { limit: UPCOMING_LIMIT, signal }),
          apiService.getRecentDepartures(stationCode, {
            windowMinutes: RECENT_WINDOW_MINUTES,
            limit: 10,
            signal,
          }),
        ]);
        setUpcoming([...up.departures].sort(byDepartureAscending));
        setRecent([...rec.departures].sort(byDepartureAscending));
        setError(null);
        setLoading(false);
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError(err instanceof Error ? err.message : 'Failed to load departures');
        setLoading(false);
      }
    },
    [stationCode]
  );

  usePolling(fetchBoard, [stationCode], { enabled: isCanonical });

  // Lines with an active departure, deduped by code, for the header summary.
  const linesServed = useMemo(() => {
    const seen = new Map<string, LineInfo>();
    for (const train of [...upcoming, ...recent]) {
      if (train.line?.code && !seen.has(train.line.code)) {
        seen.set(train.line.code, train.line);
      }
    }
    return [...seen.values()];
  }, [upcoming, recent]);

  if (!station) {
    return (
      <div className="max-w-2xl mx-auto text-center py-12">
        <div className="text-4xl mb-4">🚉</div>
        <div className="text-lg font-semibold text-text-primary mb-2">Station not found</div>
        <div className="text-text-muted mb-6">
          We don&apos;t recognize the station code &ldquo;{rawCode}&rdquo;.
        </div>
        <Link
          to="/departures"
          className="px-6 py-3 bg-accent text-white rounded-lg font-semibold hover:bg-accent/80 transition-colors"
        >
          Browse departures
        </Link>
      </div>
    );
  }

  // Normalize alias/casing in the URL so the board always lives at its canonical code.
  if (station.code !== rawCode) {
    return <Navigate to={`/station/${station.code}`} replace />;
  }

  const isHome = homeStation?.code === station.code;
  const isWork = workStation?.code === station.code;
  // Home/Work auto-inject the station as a favorite, so the plain "favorite"
  // state is the residual "favorited but not designated Home/Work" (mirrors iOS).
  const isPlainFavorite =
    !isHome && !isWork && favoriteStations.some((f) => f.id === station.code);

  // Home, Work, and Favorite are mutually exclusive per station (mirrors iOS
  // StationDetailsView): setting Home/Work injects a favorite and demotes the
  // prior holder; the residual favorite is cleared unless another role anchors it.
  const applyHome = () => {
    const { homeStation: h, workStation: w } = useAppStore.getState();
    const home = h?.code === station.code;
    const work = w?.code === station.code;
    if (home) {
      setHomeStation(null);
      if (!work) removeFavorite(station.code);
      return;
    }
    if (work) setWorkStation(null);
    const currentWork = work ? null : w;
    if (h && h.code !== station.code && h.code !== currentWork?.code) {
      removeFavorite(h.code);
    }
    setHomeStation(station);
    addFavorite(station);
  };

  const applyWork = () => {
    const { homeStation: h, workStation: w } = useAppStore.getState();
    const home = h?.code === station.code;
    const work = w?.code === station.code;
    if (work) {
      setWorkStation(null);
      if (!home) removeFavorite(station.code);
      return;
    }
    if (home) setHomeStation(null);
    const currentHome = home ? null : h;
    if (w && w.code !== station.code && w.code !== currentHome?.code) {
      removeFavorite(w.code);
    }
    setWorkStation(station);
    addFavorite(station);
  };

  const applyFavorite = () => {
    const state = useAppStore.getState();
    const home = state.homeStation?.code === station.code;
    const work = state.workStation?.code === station.code;
    // Demote a Home/Work station to a plain favorite (keep it in favorites).
    if (home || work) {
      if (home) setHomeStation(null);
      if (work) setWorkStation(null);
      addFavorite(station);
      return;
    }
    // Plain toggle otherwise.
    if (state.favoriteStations.some((f) => f.id === station.code)) {
      removeFavorite(station.code);
    } else {
      addFavorite(station);
    }
  };

  const openTrain = (train: Train) =>
    navigate(
      buildTrainUrl({
        trainId: train.train_id,
        from: station.code,
        date: train.journey_date,
        dataSource: train.data_source,
      })
    );

  // recent is ascending (oldest first); keep the most-recent few just above NOW.
  const recentToShow = recent.slice(-RECENT_DISPLAY_LIMIT);
  const hasDepartures = recent.length > 0 || upcoming.length > 0;

  return (
    <div className="max-w-2xl mx-auto">
      <button
        onClick={() => navigate(-1)}
        className="text-accent hover:text-accent/80 mb-4 flex items-center gap-2 font-semibold"
      >
        ← Back
      </button>

      {/* Header */}
      <div className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-5 mb-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold text-text-primary flex items-center gap-2">
              {station.name}
              {station.system === 'SUBWAY' && (
                <SubwayLineChips stationCode={station.code} size={20} />
              )}
            </h1>
            <div className="text-sm text-text-muted mt-1">{station.code}</div>
          </div>
          {station.system && (
            <span className="text-xs font-semibold text-text-muted bg-background border border-text-muted/20 rounded-full px-3 py-1 shrink-0">
              {SYSTEM_NAMES[station.system]}
            </span>
          )}
        </div>

        {linesServed.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2" aria-label="Lines serving this station">
            {linesServed.map((line) => (
              <span
                key={line.code}
                className="inline-flex items-center gap-1.5 text-xs font-medium text-text-secondary bg-background border border-text-muted/20 rounded-full px-2.5 py-1"
              >
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: line.color || '#808183' }}
                  aria-hidden="true"
                />
                {line.name}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Home / Work / Favorite (mutually exclusive) */}
      <div className="flex gap-2 mb-4">
        <ActionButton label={isHome ? 'Home' : 'Set Home'} icon="🏠" active={isHome} onClick={applyHome} />
        <ActionButton label={isWork ? 'Work' : 'Set Work'} icon="💼" active={isWork} onClick={applyWork} />
        <ActionButton
          label={isPlainFavorite ? 'Favorited' : 'Set Favorite'}
          icon="⭐"
          active={isPlainFavorite}
          onClick={applyFavorite}
        />
      </div>

      {/* Service alerts (MTA systems only; the banner no-ops for others) */}
      {station.system && <ServiceAlertBanner dataSource={station.system} />}

      {/* Departure board */}
      <h2 className="text-lg font-semibold text-text-primary mb-3">Departures</h2>

      {loading && !hasDepartures ? (
        <LoadingSpinner label="Loading departures" />
      ) : error ? (
        <ErrorMessage message={error} onRetry={() => fetchBoard()} />
      ) : !hasDepartures ? (
        <div className="text-center py-12 text-text-muted">No departures available</div>
      ) : (
        <div className="space-y-3">
          {recentToShow.map((train) => (
            <TrainCard
              key={`recent-${train.train_id}-${train.journey_date}`}
              train={train}
              onClick={() => openTrain(train)}
              from={station.code}
              departed
            />
          ))}

          <NowDivider />

          {upcoming.length > 0 ? (
            upcoming.map((train) => (
              <TrainCard
                key={`upcoming-${train.train_id}-${train.journey_date}`}
                train={train}
                onClick={() => openTrain(train)}
                from={station.code}
              />
            ))
          ) : (
            <div className="text-center py-6 text-text-muted text-sm">No more trains scheduled</div>
          )}
        </div>
      )}
    </div>
  );
}
