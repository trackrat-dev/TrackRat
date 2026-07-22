import { useState, useMemo, useCallback } from 'react';
import { apiService } from '../services/api';
import { ServiceAlert, TransitSystem } from '../types';
import { ALERT_CAPABLE_SYSTEMS } from '../data/stations';
import { usePolling } from '../utils/usePolling';
import { AlertIcon, ElevatorIcon, WarningIcon, ChevronIcon } from './icons';

/** Icon for each alert type; mirrors the ordering in getAlertStyle. */
function AlertTypeIcon({ alertType, className }: { alertType: string; className?: string }) {
  if (alertType === 'alert') return <AlertIcon size={18} className={className} />;
  if (alertType === 'elevator') return <ElevatorIcon size={18} className={className} />;
  return <WarningIcon size={18} className={className} />;
}

interface ServiceAlertBannerProps {
  dataSource: string;
  /** Optional route/line IDs to filter alerts by relevance */
  routeIds?: string[];
}

/** Alerts are cached ~2min server-side, so polling faster buys nothing. */
const ALERTS_POLL_MS = 120_000;

function getAlertStyle(alertType: string): { bg: string; border: string; icon: string } {
  switch (alertType) {
    case 'alert':
      return { bg: 'bg-error/10', border: 'border-error/30', icon: 'text-error' };
    case 'planned_work':
      return { bg: 'bg-warning/10', border: 'border-warning/30', icon: 'text-warning' };
    case 'elevator':
      return { bg: 'bg-text-muted/10', border: 'border-text-muted/30', icon: 'text-text-muted' };
    default:
      return { bg: 'bg-warning/10', border: 'border-warning/30', icon: 'text-warning' };
  }
}

function getAlertTypeLabel(alertType: string): string {
  switch (alertType) {
    case 'alert': return 'Service Alert';
    case 'planned_work': return 'Planned Work';
    case 'elevator': return 'Elevator Outage';
    default: return 'Alert';
  }
}

export function ServiceAlertBanner({ dataSource, routeIds }: ServiceAlertBannerProps) {
  const [alerts, setAlerts] = useState<ServiceAlert[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [sectionExpanded, setSectionExpanded] = useState(false);
  const [failed, setFailed] = useState(false);

  // Stabilize routeIds reference for the polling dependency
  const routeIdsKey = useMemo(() => routeIds?.sort().join(',') ?? '', [routeIds]);
  // Systems with backend service-alert collection (MTA + NJT).
  const isAlertCapable = ALERT_CAPABLE_SYSTEMS.includes(dataSource as TransitSystem);

  const fetchAlerts = useCallback(async (signal?: AbortSignal) => {
    try {
      const res = await apiService.getServiceAlerts(dataSource, undefined, signal);
      let filtered = res.alerts;
      // If routeIds provided, only show relevant alerts
      if (routeIds && routeIds.length > 0) {
        filtered = filtered.filter(alert =>
          alert.affected_route_ids.length === 0 ||
          alert.affected_route_ids.some(id => routeIds.includes(id))
        );
      }
      setAlerts(filtered);
      setFailed(false);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      setFailed(true);
    }
    // routeIdsKey stands in for routeIds' contents (see useMemo above)
  }, [dataSource, routeIdsKey]);

  usePolling(fetchAlerts, [dataSource, routeIdsKey], { intervalMs: ALERTS_POLL_MS, enabled: isAlertCapable });

  if (alerts.length === 0) {
    // Only alert-capable systems fetch; surface a muted note if that fetch failed.
    if (isAlertCapable && failed) {
      return (
        <div className="mb-4 px-3 py-2 rounded-xl border border-text-muted/20 bg-surface/50">
          <p className="text-sm text-text-muted">Couldn’t load service alerts</p>
        </div>
      );
    }
    return null;
  }

  // Sort: real-time alerts first, then planned work, then elevator
  const sortedAlerts = [...alerts].sort((a, b) => {
    const order: Record<string, number> = { alert: 0, planned_work: 1, elevator: 2 };
    return (order[a.alert_type] ?? 3) - (order[b.alert_type] ?? 3);
  });

  // Section is collapsed by default so alert-heavy routes (e.g. HL/NY) don't lead
  // with a wall of alerts (#1543). Keep the highest-priority real-time headline
  // visible in the compact summary so active disruptions are still actionable.
  const topAlert = sortedAlerts[0];
  const topStyle = getAlertStyle(topAlert.alert_type);
  const alertTypeLabels = [...new Set(sortedAlerts.map(alert => getAlertTypeLabel(alert.alert_type)))];
  const summaryLabel = topAlert.alert_type === 'alert'
    ? (sortedAlerts.length === 1 ? 'Service Alert' : 'Service Alerts')
    : (alertTypeLabels.length === 1 ? getAlertTypeLabel(topAlert.alert_type) : 'Service Alerts');
  const summaryContext = topAlert.alert_type === 'alert'
    ? topAlert.header_text
    : alertTypeLabels.join(' and ');

  return (
    <div className="mb-4">
      <button
        onClick={() => setSectionExpanded(prev => !prev)}
        className={`w-full flex items-center gap-2 p-3 rounded-xl border ${topStyle.bg} ${topStyle.border} text-left transition-all`}
        aria-expanded={sectionExpanded}
        aria-label={`${sectionExpanded ? 'Hide' : 'Show'} service alerts (${sortedAlerts.length}): ${summaryContext}`}
      >
        <AlertTypeIcon alertType={topAlert.alert_type} className={`${topStyle.icon} shrink-0`} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-text-primary">{summaryLabel}</span>
            <span className={`text-xs font-semibold shrink-0 ${topStyle.icon}`}>{sortedAlerts.length}</span>
          </div>
          {!sectionExpanded && topAlert.alert_type === 'alert' && (
            <p className="text-xs text-text-secondary line-clamp-2 break-words">{topAlert.header_text}</p>
          )}
        </div>
        <ChevronIcon direction={sectionExpanded ? 'up' : 'down'} size={16} className="text-text-muted shrink-0" />
      </button>

      {sectionExpanded && (
        <div className="space-y-2 mt-2">
          {sortedAlerts.map(alert => {
            const style = getAlertStyle(alert.alert_type);
            const isExpanded = expandedId === alert.alert_id;

            return (
              <div
                key={alert.alert_id}
                className={`${style.bg} border ${style.border} rounded-xl overflow-hidden`}
              >
                <button
                  onClick={() => setExpandedId(isExpanded ? null : alert.alert_id)}
                  className="w-full flex items-start gap-3 p-3 text-left"
                  aria-expanded={isExpanded}
                >
                  <AlertTypeIcon alertType={alert.alert_type} className={`${style.icon} mt-0.5 shrink-0`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className={`text-xs font-semibold ${style.icon}`}>
                        {getAlertTypeLabel(alert.alert_type)}
                      </span>
                      {alert.affected_route_ids.length > 0 && (
                        <span className="text-xs text-text-muted">
                          {alert.affected_route_ids.slice(0, 3).join(', ')}
                          {alert.affected_route_ids.length > 3 && ` +${alert.affected_route_ids.length - 3}`}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-text-primary line-clamp-2">{alert.header_text}</p>
                  </div>
                  <ChevronIcon direction={isExpanded ? 'up' : 'down'} size={16} className="text-text-muted shrink-0 mt-0.5" />
                </button>
                {isExpanded && alert.description_text && (
                  <div className="px-3 pb-3 pl-9">
                    <p className="text-xs text-text-secondary whitespace-pre-line">{alert.description_text}</p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
