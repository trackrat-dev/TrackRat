import { useState, useCallback, lazy, Suspense } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { SegmentCongestion, OperationsSummaryResponse, TransitSystem } from '../types';
import { apiService } from '../services/api';
import { SYSTEM_NAMES, SYSTEM_COLORS, AVAILABLE_SYSTEMS, getStationByCode } from '../data/stations';
import { getRoutesForSystem, RouteDefinition } from '../data/routeTopology';
import { averageRouteDelay } from '../utils/congestion';
import { ServiceAlertBanner } from '../components/ServiceAlertBanner';
import { ErrorMessage } from '../components/ErrorMessage';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { ChevronIcon } from '../components/icons';
import { usePolling } from '../utils/usePolling';
import { useBackNavigation } from '../utils/useBackNavigation';

// Shares the lazy MapLibre chunk with RouteMap / NetworkStatusPage.
const CongestionMap = lazy(() => import('../components/CongestionMap').then((m) => ({ default: m.CongestionMap })));

/** System-level details: system-scoped congestion map, operations summary,
 *  service alerts, and a tappable list of the system's routes. Mirrors the iOS
 *  TrainSystemDetailView. Each route row opens the line view (`/line/:lineId`). */
export function SystemDetailPage() {
  const { system: systemParam } = useParams<{ system: string }>();
  const navigate = useNavigate();
  const goBack = useBackNavigation('/status');

  const system = (systemParam?.toUpperCase() ?? '') as TransitSystem;
  const isKnownSystem = AVAILABLE_SYSTEMS.includes(system);

  const [segments, setSegments] = useState<SegmentCongestion[]>([]);
  const [summary, setSummary] = useState<OperationsSummaryResponse | null>(null);

  const fetchData = useCallback(async (signal?: AbortSignal) => {
    if (!isKnownSystem) return;
    const [congestion, systemSummary] = await Promise.all([
      apiService.getCongestion(signal),
      // Summary is optional context; a failure must not blank the page.
      apiService.getNetworkSummary(system, signal).catch(() => null),
    ]);
    setSegments(congestion.aggregated_segments.filter((seg) => seg.data_source === system));
    setSummary(systemSummary);
    // Congestion updates less frequently than per-route data.
  }, [system, isKnownSystem]);

  // Poll on the same cadence as the network status page.
  usePolling(fetchData, [system], { intervalMs: 60_000, enabled: isKnownSystem });

  if (!isKnownSystem) {
    return <ErrorMessage message="Unknown system" onRetry={() => navigate('/status')} />;
  }

  const routes = getRoutesForSystem(system);

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <button
          onClick={goBack}
          className="text-accent hover:text-accent/80 mb-4 flex items-center gap-2 font-semibold"
        >
          ← Back
        </button>
        <h2 className="text-2xl font-bold text-text-primary text-center">
          {SYSTEM_NAMES[system]}
        </h2>
      </div>

      {/* Service alerts (only alert-capable systems fetch) */}
      <ServiceAlertBanner dataSource={system} />

      {/* Operations summary */}
      {summary && (
        <div className="mb-4 bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4">
          <div className="text-sm font-medium text-text-primary mb-1">{summary.headline}</div>
          <p className="text-xs text-text-muted whitespace-pre-line">{summary.body}</p>
        </div>
      )}

      {/* System congestion map (lazy-loaded) */}
      {segments.length > 0 && (
        <ErrorBoundary fallback={null}>
          <Suspense fallback={null}>
            <CongestionMap segments={segments} />
          </Suspense>
        </ErrorBoundary>
      )}

      {/* Routes list */}
      {routes.length > 0 && (
        <div className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl overflow-hidden">
          <div className="flex items-center justify-between px-4 pt-4 pb-2">
            <h3 className="text-sm font-semibold text-text-primary">Routes</h3>
            <span className="text-xs text-text-muted">{routes.length}</span>
          </div>
          <div className="divide-y divide-text-muted/10">
            {routes.map((route) => (
              <RouteRow
                key={route.id}
                route={route}
                color={SYSTEM_COLORS[system]}
                delay={averageRouteDelay(route.stations, segments)}
                onClick={() => navigate(`/line/${route.id}`)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/** A single route row: brand swatch, name, terminal subtitle, delay pill, chevron. */
function RouteRow({
  route,
  color,
  delay,
  onClick,
}: {
  route: RouteDefinition;
  color: string;
  delay: number | null;
  onClick: () => void;
}) {
  const first = route.stations[0];
  const last = route.stations[route.stations.length - 1];
  const subtitle =
    first && last && first !== last
      ? `${getStationByCode(first)?.name ?? first} → ${getStationByCode(last)?.name ?? last}`
      : null;

  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface/50 transition-colors"
    >
      <span className="w-1 h-8 rounded-full shrink-0" style={{ backgroundColor: color }} />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-text-primary truncate">{route.name}</div>
        {subtitle && <div className="text-xs text-text-muted truncate">{subtitle}</div>}
      </div>
      {delay != null && <DelayPill delay={delay} />}
      <ChevronIcon direction="right" size={16} className="text-text-muted shrink-0" />
    </button>
  );
}

/** Average-delay pill, thresholds mirroring the iOS SystemRouteListRow. */
function DelayPill({ delay }: { delay: number }) {
  if (delay < 0.5) {
    return <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-success/15 text-success">On time</span>;
  }
  const label = `+${Math.round(delay)} min`;
  const tone = delay < 5 ? 'bg-warning/15 text-warning' : 'bg-error/15 text-error';
  return <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${tone}`}>{label}</span>;
}
