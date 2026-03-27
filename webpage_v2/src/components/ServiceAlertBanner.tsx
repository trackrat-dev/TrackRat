import { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import { ServiceAlert } from '../types';

interface ServiceAlertBannerProps {
  dataSource: string;
  /** Optional route/line IDs to filter alerts by relevance */
  routeIds?: string[];
}

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

  useEffect(() => {
    // Only fetch for MTA systems that have service alerts
    const mtaSystems = ['SUBWAY', 'LIRR', 'MNR'];
    if (!mtaSystems.includes(dataSource)) return;

    apiService.getServiceAlerts(dataSource)
      .then(res => {
        let filtered = res.alerts;
        // If routeIds provided, only show relevant alerts
        if (routeIds && routeIds.length > 0) {
          filtered = filtered.filter(alert =>
            alert.affected_route_ids.length === 0 ||
            alert.affected_route_ids.some(id => routeIds.includes(id))
          );
        }
        setAlerts(filtered);
      })
      .catch(() => {}); // Fail silently
  }, [dataSource, routeIds?.join(',')]);

  if (alerts.length === 0) return null;

  // Sort: real-time alerts first, then planned work, then elevator
  const sortedAlerts = [...alerts].sort((a, b) => {
    const order: Record<string, number> = { alert: 0, planned_work: 1, elevator: 2 };
    return (order[a.alert_type] ?? 3) - (order[b.alert_type] ?? 3);
  });

  return (
    <div className="space-y-2 mb-4">
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
            >
              <span className={`${style.icon} text-lg leading-none mt-0.5`}>
                {alert.alert_type === 'alert' ? '!' : alert.alert_type === 'elevator' ? '⬆' : '⚠'}
              </span>
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
              <span className="text-text-muted text-xs shrink-0">{isExpanded ? '▲' : '▼'}</span>
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
  );
}
