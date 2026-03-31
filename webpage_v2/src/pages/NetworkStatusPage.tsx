import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { SegmentCongestion, CongestionLevel, OperationsSummaryResponse } from '../types';
import { apiService } from '../services/api';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { formatTimeAgo } from '../utils/date';

const SYSTEM_LABELS: Record<string, string> = {
  NJT: 'NJ Transit',
  AMTRAK: 'Amtrak',
  PATH: 'PATH',
  PATCO: 'PATCO',
  LIRR: 'LIRR',
  MNR: 'Metro-North',
  SUBWAY: 'NYC Subway',
  WMATA: 'Washington Metro',
  METRA: 'Metra',
  BART: 'BART',
  MBTA: 'MBTA',
};

const SYSTEM_ORDER = ['NJT', 'AMTRAK', 'PATH', 'LIRR', 'MNR', 'SUBWAY', 'PATCO', 'WMATA', 'METRA', 'BART', 'MBTA'];

function getCongestionColor(level: CongestionLevel): string {
  switch (level) {
    case 'normal': return 'text-success';
    case 'moderate': return 'text-warning';
    case 'heavy': return 'text-error';
    case 'severe': return 'text-error';
  }
}

function getCongestionBg(level: CongestionLevel): string {
  switch (level) {
    case 'normal': return 'bg-success/15';
    case 'moderate': return 'bg-warning/15';
    case 'heavy': return 'bg-error/15';
    case 'severe': return 'bg-error/20';
  }
}

function getCongestionLabel(level: CongestionLevel): string {
  switch (level) {
    case 'normal': return 'Normal';
    case 'moderate': return 'Moderate delays';
    case 'heavy': return 'Heavy delays';
    case 'severe': return 'Severe delays';
  }
}

/** Determine overall system status from its segments */
function getSystemStatus(segments: SegmentCongestion[]): CongestionLevel {
  if (segments.some(s => s.congestion_level === 'severe')) return 'severe';
  if (segments.some(s => s.congestion_level === 'heavy')) return 'heavy';
  if (segments.some(s => s.congestion_level === 'moderate')) return 'moderate';
  return 'normal';
}

export function NetworkStatusPage() {
  const navigate = useNavigate();
  const [segments, setSegments] = useState<SegmentCongestion[]>([]);
  const [summary, setSummary] = useState<OperationsSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [expandedSystem, setExpandedSystem] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setError(null);
      const [congestion, networkSummary] = await Promise.all([
        apiService.getCongestion(),
        apiService.getNetworkSummary(),
      ]);
      setSegments(congestion.aggregated_segments);
      setGeneratedAt(congestion.generated_at);
      setSummary(networkSummary);
      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load network status');
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000); // Refresh every 60 seconds
    return () => clearInterval(interval);
  }, []);

  const { systemGroups, orderedSystems } = useMemo(() => {
    const groups: Record<string, SegmentCongestion[]> = {};
    for (const seg of segments) {
      if (!groups[seg.data_source]) groups[seg.data_source] = [];
      groups[seg.data_source].push(seg);
    }
    // Sort segments within each group by delay (most delayed first)
    for (const key of Object.keys(groups)) {
      groups[key].sort((a, b) => b.average_delay_minutes - a.average_delay_minutes);
    }
    // Show known systems in preferred order, then any others alphabetically
    const knownSystems = SYSTEM_ORDER.filter(sys => groups[sys]);
    const otherSystems = Object.keys(groups)
      .filter(sys => !SYSTEM_ORDER.includes(sys))
      .sort();
    return { systemGroups: groups, orderedSystems: [...knownSystems, ...otherSystems] };
  }, [segments]);

  if (loading && segments.length === 0) return <LoadingSpinner />;
  if (error) return <ErrorMessage message={error} onRetry={fetchData} />;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-text-primary text-center">Network Status</h2>
        {generatedAt && (
          <div className="text-sm text-text-muted mt-1 text-center">
            Updated {formatTimeAgo(new Date(generatedAt).toISOString())}
          </div>
        )}
      </div>

      {/* Network summary */}
      {summary && (
        <div className="mb-4 bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4">
          <div className="text-sm font-medium text-text-primary">{summary.headline}</div>
          <p className="text-xs text-text-muted mt-1 whitespace-pre-line">{summary.body}</p>
        </div>
      )}

      {/* System list */}
      <div className="space-y-3">
        {orderedSystems.map(system => {
          const segs = systemGroups[system];
          const status = getSystemStatus(segs);
          const delayedCount = segs.filter(s => s.congestion_level !== 'normal').length;
          const isExpanded = expandedSystem === system;

          return (
            <div key={system} className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl overflow-hidden">
              <button
                onClick={() => setExpandedSystem(isExpanded ? null : system)}
                className="w-full p-4 flex items-center justify-between text-left"
                aria-expanded={isExpanded}
              >
                <div className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${getCongestionBg(status)} border-2 ${status === 'normal' ? 'border-success' : status === 'moderate' ? 'border-warning' : 'border-error'}`} />
                  <div>
                    <div className="font-semibold text-text-primary">{SYSTEM_LABELS[system] || system}</div>
                    <div className="text-xs text-text-muted">
                      {segs.length} segment{segs.length !== 1 ? 's' : ''}
                      {delayedCount > 0 && (
                        <span className={`ml-2 ${getCongestionColor(status)}`}>
                          {delayedCount} delayed
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${getCongestionBg(status)} ${getCongestionColor(status)} font-medium`}>
                    {getCongestionLabel(status)}
                  </span>
                  <span className="text-text-muted text-xs">{isExpanded ? '▲' : '▼'}</span>
                </div>
              </button>

              {isExpanded && (
                <div className="border-t border-text-muted/10 divide-y divide-text-muted/10">
                  {segs.map(seg => (
                    <button
                      key={`${seg.from_station}-${seg.to_station}`}
                      onClick={() => navigate(`/trains/${seg.from_station}/${seg.to_station}`)}
                      className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-surface/50 transition-colors"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-text-primary truncate">
                          {seg.from_station_name} → {seg.to_station_name}
                        </div>
                        <div className="text-xs text-text-muted mt-0.5">
                          {seg.sample_count} trains
                          {seg.train_count != null && seg.baseline_train_count != null && seg.baseline_train_count > 0 && (
                            <span className="ml-2">
                              ({Math.round((seg.train_count / seg.baseline_train_count) * 100)}% of expected)
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0 ml-3">
                        {seg.average_delay_minutes > 0 && (
                          <span className={`text-xs font-medium ${getCongestionColor(seg.congestion_level)}`}>
                            +{seg.average_delay_minutes.toFixed(0)}m
                          </span>
                        )}
                        <span className={`w-2 h-2 rounded-full ${seg.congestion_level === 'normal' ? 'bg-success' : seg.congestion_level === 'moderate' ? 'bg-warning' : 'bg-error'}`} />
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
