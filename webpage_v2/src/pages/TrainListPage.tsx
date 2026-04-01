import { useState, useEffect, useMemo, lazy, Suspense } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Train, TripOption, OperationsSummaryResponse } from '../types';
import { apiService } from '../services/api';
import { useAppStore } from '../store/appStore';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { TrainCard } from '../components/TrainCard';
import { TransferTripCard } from '../components/TransferTripCard';
import { ServiceAlertBanner } from '../components/ServiceAlertBanner';
import { TrainDistributionChart } from '../components/TrainDistributionChart';
import { getStationByCode } from '../data/stations';
import { formatTimeAgo, getTodayDateString } from '../utils/date';

const RouteMap = lazy(() => import('../components/RouteMap').then((m) => ({ default: m.RouteMap })));

/** Convert a direct TripOption (1 leg) to a Train for the existing TrainCard */
function tripLegToTrain(trip: TripOption): Train {
  const leg = trip.legs[0];
  return {
    train_id: leg.train_id,
    journey_date: leg.journey_date,
    line: leg.line,
    destination: leg.destination,
    departure: leg.boarding,
    arrival: leg.alighting,
    train_position: leg.train_position,
    data_freshness: { last_updated: '', age_seconds: 0, update_count: 0, collection_method: null },
    data_source: leg.data_source,
    observation_type: (leg.observation_type as 'OBSERVED' | 'SCHEDULED') || 'OBSERVED',
    is_cancelled: leg.is_cancelled,
  };
}

export function TrainListPage() {
  const { from, to } = useParams<{ from: string; to: string }>();
  const navigate = useNavigate();
  const { addRecentTrip } = useAppStore();

  const [trains, setTrains] = useState<Train[]>([]);
  const [transferTrips, setTransferTrips] = useState<TripOption[]>([]);
  const [isTransferSearch, setIsTransferSearch] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [trainFilter, setTrainFilter] = useState('');
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [summary, setSummary] = useState<OperationsSummaryResponse | null>(null);
  const [summaryExpanded, setSummaryExpanded] = useState(false);

  const isViewingFutureDate = selectedDate !== null && selectedDate !== getTodayDateString();

  const fromStation = from ? getStationByCode(from) : null;
  const toStation = to ? getStationByCode(to) : null;

  // Check if train has already departed from the origin station
  const hasTrainDeparted = (train: Train): boolean => {
    const now = new Date();
    const departureTimeStr = train.departure.actual_time || train.departure.updated_time || train.departure.scheduled_time;
    if (!departureTimeStr) return false;
    const departureTime = new Date(departureTimeStr);
    // 1 minute buffer (matching iOS implementation)
    const departureWithBuffer = new Date(departureTime.getTime() + 60 * 1000);
    return departureWithBuffer < now;
  };

  const fetchTrains = async () => {
    if (!from || !to) return;

    try {
      setError(null);
      const response = await apiService.searchTrips(from, to, 50, selectedDate || undefined);

      // Split response into direct and transfer trips
      const directTrips = response.trips.filter(t => t.is_direct);
      const transferTripsResult = response.trips.filter(t => !t.is_direct);

      // Convert direct trips to Train objects for existing TrainCard
      const directTrains = directTrips.map(tripLegToTrain);
      const sorted = [...directTrains].sort((a, b) => {
        const aDeparted = hasTrainDeparted(a);
        const bDeparted = hasTrainDeparted(b);
        if (aDeparted !== bDeparted) return aDeparted ? 1 : -1;
        return 0;
      });

      setTrains(sorted);
      setTransferTrips(transferTripsResult);
      setIsTransferSearch(transferTripsResult.length > 0 && directTrips.length === 0);

      setLastUpdated(new Date());
      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load trains');
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTrains();

    // Save to recent trips once on mount, not every poll cycle
    if (fromStation && toStation) {
      addRecentTrip(fromStation, toStation);
    }

    // Fetch summary once on mount (not polled) - only for direct routes
    if (from && to) {
      apiService.getRouteSummary(from, to).then(setSummary);
    }

    // Poll every 30 seconds — but not for future dates (no real-time data)
    if (!isViewingFutureDate) {
      const interval = setInterval(fetchTrains, 30000);
      return () => clearInterval(interval);
    }
  }, [from, to, selectedDate]);

  const filteredTrains = useMemo(() => {
    if (!trainFilter.trim()) return trains;
    const q = trainFilter.trim().toLowerCase();
    return trains.filter(t => t.train_id.toLowerCase().includes(q));
  }, [trains, trainFilter]);

  const filteredTransferTrips = useMemo(() => {
    if (!trainFilter.trim()) return transferTrips;
    const q = trainFilter.trim().toLowerCase();
    return transferTrips.filter(t =>
      t.legs.some(leg => leg.train_id.toLowerCase().includes(q))
    );
  }, [transferTrips, trainFilter]);

  const isEmpty = filteredTrains.length === 0 && filteredTransferTrips.length === 0;
  const hasResults = trains.length > 0 || transferTrips.length > 0;

  if (!from || !to || !fromStation || !toStation) {
    return (
      <ErrorMessage
        message="Invalid route"
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
          {fromStation.name} → {toStation.name}
        </h2>
        <div className="flex items-center justify-center gap-4 mt-2">
          {lastUpdated && (
            <span className="text-sm text-text-muted">
              Updated {formatTimeAgo(lastUpdated.toISOString())}
            </span>
          )}
          <Link
            to={`/route/${from}/${to}`}
            className="text-sm text-accent hover:text-accent/80 font-medium"
          >
            Route Status →
          </Link>
        </div>
      </div>

      {/* Service alerts for MTA systems */}
      {fromStation.system && (
        <ServiceAlertBanner dataSource={fromStation.system} />
      )}

      {/* Route map (lazy-loaded) */}
      {fromStation && toStation && (
        <Suspense fallback={null}>
          <RouteMap
            fromStation={fromStation}
            toStation={toStation}
            lineColor={trains[0]?.line.color}
          />
        </Suspense>
      )}

      {/* Route summary (direct routes only) */}
      {summary && !isTransferSearch && (
        <button
          onClick={() => setSummaryExpanded(!summaryExpanded)}
          className="w-full mb-4 bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl p-4 text-left transition-all hover:bg-surface"
          aria-expanded={summaryExpanded}
        >
          <div className="flex items-center justify-between">
            <div className="text-sm font-medium text-text-primary">{summary.headline}</div>
            <span className="text-text-muted text-xs ml-2">{summaryExpanded ? '▲' : '▼'}</span>
          </div>
          {summaryExpanded && (
            <>
              <div className="mt-3 text-sm text-text-muted whitespace-pre-line">{summary.body}</div>
              {summary.metrics && (
                <TrainDistributionChart
                  trainsByCategory={summary.metrics.trains_by_category}
                  trainsByHeadway={summary.metrics.trains_by_headway}
                  dataSource={fromStation?.system}
                  from={from}
                  to={to}
                />
              )}
            </>
          )}
        </button>
      )}

      {/* Transfer search banner */}
      {isTransferSearch && hasResults && (
        <div className="mb-4 bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl px-4 py-3">
          <div className="text-sm text-text-muted flex items-center gap-2">
            <span>⇆</span>
            <span>No direct service — showing connections with 1 transfer</span>
          </div>
        </div>
      )}

      {/* Future date banner */}
      {isViewingFutureDate && (
        <div className="mb-4 bg-warning/10 border border-warning/30 rounded-xl px-4 py-3 flex items-center justify-between">
          <div className="text-sm text-text-primary">
            Showing scheduled departures for <span className="font-semibold">{selectedDate}</span>
          </div>
          <button
            onClick={() => setSelectedDate(null)}
            className="text-xs text-accent font-semibold hover:text-accent/80"
          >
            Back to today
          </button>
        </div>
      )}

      <div className="flex gap-2 mb-4">
        <button
          onClick={fetchTrains}
          disabled={loading}
          className="py-3 px-4 bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl font-semibold hover:bg-surface transition-all disabled:opacity-50 text-text-primary"
        >
          {loading ? '...' : '🔄'}
        </button>
        <input
          type="date"
          value={selectedDate || getTodayDateString()}
          min={getTodayDateString()}
          onChange={(e) => setSelectedDate(e.target.value === getTodayDateString() ? null : e.target.value)}
          className="py-3 px-3 bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-accent"
        />
        <div className="flex-1 relative">
          <input
            type="text"
            value={trainFilter}
            onChange={(e) => setTrainFilter(e.target.value)}
            placeholder="Filter by train #"
            className="w-full px-4 py-3 bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-accent"
          />
          {trainFilter && (
            <button
              onClick={() => setTrainFilter('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
            >
              ×
            </button>
          )}
        </div>
      </div>

      {loading && !hasResults ? (
        <LoadingSpinner />
      ) : error ? (
        <ErrorMessage message={error} onRetry={fetchTrains} />
      ) : isEmpty ? (
        <div className="text-center py-12 text-text-muted">
          {trainFilter ? 'No matching trains' : 'No trains found for this route'}
        </div>
      ) : (
        <div className="space-y-3">
          {filteredTrains.map((train) => (
            <TrainCard
              key={train.train_id}
              train={train}
              onClick={() => navigate(`/train/${train.train_id}/${from}/${to}`)}
              from={from}
              to={to}
              departed={hasTrainDeparted(train)}
            />
          ))}
          {filteredTransferTrips.map((trip) => (
            <TransferTripCard
              key={trip.legs.map(l => l.train_id).join('-')}
              trip={trip}
              onClick={() => navigate('/trip', { state: { trip } })}
            />
          ))}
        </div>
      )}
    </div>
  );
}
