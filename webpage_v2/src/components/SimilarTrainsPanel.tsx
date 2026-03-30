import { useState, useEffect } from 'react';
import { OperationsSummaryResponse } from '../types';
import { apiService } from '../services/api';
import { TrainDistributionChart } from './TrainDistributionChart';

interface Props {
  trainId: string;
  from: string;
  to: string;
  dataSource?: string;
}

export function SimilarTrainsPanel({ trainId, from, to, dataSource }: Props) {
  const [summary, setSummary] = useState<OperationsSummaryResponse | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    apiService.getTrainSummary(trainId, from, to).then(setSummary);
  }, [trainId, from, to]);

  if (!summary) return null;

  const hasChart = summary.metrics?.trains_by_category || summary.metrics?.trains_by_headway;

  return (
    <div className="mb-6">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl p-4 text-left transition-all hover:bg-surface"
        aria-expanded={expanded}
      >
        <div className="flex items-center justify-between">
          <div className="text-sm font-medium text-text-primary">{summary.headline}</div>
          <span className="text-text-muted text-xs ml-2">{expanded ? '▲' : '▼'}</span>
        </div>
        {expanded && (
          <>
            <div className="mt-3 text-sm text-text-muted whitespace-pre-line">{summary.body}</div>
            {hasChart && (
              <TrainDistributionChart
                trainsByCategory={summary.metrics!.trains_by_category}
                trainsByHeadway={summary.metrics!.trains_by_headway}
                dataSource={dataSource}
                from={from}
                to={to}
              />
            )}
            {summary.metrics && (
              <div className="grid grid-cols-3 gap-2 mt-3">
                {summary.metrics.on_time_percentage != null && (
                  <div className="text-center">
                    <div className={`text-sm font-bold ${summary.metrics.on_time_percentage >= 80 ? 'text-success' : summary.metrics.on_time_percentage >= 60 ? 'text-warning' : 'text-error'}`}>
                      {Math.round(summary.metrics.on_time_percentage)}%
                    </div>
                    <div className="text-[10px] text-text-muted">On time</div>
                  </div>
                )}
                {summary.metrics.average_delay_minutes != null && (
                  <div className="text-center">
                    <div className="text-sm font-bold text-text-primary">
                      {summary.metrics.average_delay_minutes.toFixed(1)}m
                    </div>
                    <div className="text-[10px] text-text-muted">Avg delay</div>
                  </div>
                )}
                {summary.metrics.train_count != null && (
                  <div className="text-center">
                    <div className="text-sm font-bold text-text-primary">
                      {summary.metrics.train_count}
                    </div>
                    <div className="text-[10px] text-text-muted">Similar trains</div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </button>
    </div>
  );
}
