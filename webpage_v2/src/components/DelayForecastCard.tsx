import { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import { DelayForecastResponse } from '../types';

interface DelayForecastCardProps {
  trainId: string;
  stationCode: string;
  journeyDate: string;
}

function getProbabilityColor(probability: number): string {
  if (probability < 0.2) return 'text-success';
  if (probability < 0.5) return 'text-warning';
  return 'text-error';
}

function getProbabilityBg(probability: number): string {
  if (probability < 0.2) return 'bg-success/15';
  if (probability < 0.5) return 'bg-warning/15';
  return 'bg-error/15';
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function DelayForecastCard({ trainId, stationCode, journeyDate }: DelayForecastCardProps) {
  const [forecast, setForecast] = useState<DelayForecastResponse | null>(null);

  useEffect(() => {
    apiService.getDelayForecast(trainId, stationCode, journeyDate)
      .then(setForecast)
      .catch(() => {});
  }, [trainId, stationCode, journeyDate]);

  if (!forecast) return null;

  const onTimePct = forecast.delay_probabilities.on_time;
  const cancellationPct = forecast.cancellation_probability;
  const hasDelayConcern = onTimePct < 0.8;
  const hasCancellationConcern = cancellationPct >= 0.05;

  return (
    <div className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4">
      <h4 className="text-sm font-semibold text-text-primary mb-3">Delay Forecast</h4>

      <div className="flex items-center gap-4 flex-wrap">
        {/* On-time probability */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted">On time</span>
          <span className={`text-sm font-semibold ${getProbabilityColor(1 - onTimePct)}`}>
            {formatPercent(onTimePct)}
          </span>
        </div>

        {/* Cancellation probability — only show if notable */}
        {hasCancellationConcern && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted">Cancellation</span>
            <span className={`text-sm font-semibold ${getProbabilityColor(cancellationPct)}`}>
              {formatPercent(cancellationPct)}
            </span>
          </div>
        )}

        {/* Expected delay — only show when there's actual concern */}
        {hasDelayConcern && forecast.expected_delay_minutes > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted">Expected delay</span>
            <span className="text-sm font-semibold text-warning">
              {forecast.expected_delay_minutes} min
            </span>
          </div>
        )}

        {/* Confidence badge */}
        <span className={`ml-auto text-xs px-2 py-0.5 rounded-full ${getProbabilityBg(1 - onTimePct)} ${getProbabilityColor(1 - onTimePct)}`}>
          {forecast.confidence} confidence
        </span>
      </div>

      {/* Delay breakdown bar — compact visual */}
      {hasDelayConcern && (
        <div className="mt-3">
          <div className="flex h-2 rounded-full overflow-hidden">
            <div
              className="bg-success"
              style={{ width: formatPercent(forecast.delay_probabilities.on_time) }}
              title={`On time: ${formatPercent(forecast.delay_probabilities.on_time)}`}
            />
            <div
              className="bg-warning/70"
              style={{ width: formatPercent(forecast.delay_probabilities.slight) }}
              title={`5-15 min: ${formatPercent(forecast.delay_probabilities.slight)}`}
            />
            <div
              className="bg-warning"
              style={{ width: formatPercent(forecast.delay_probabilities.significant) }}
              title={`15-30 min: ${formatPercent(forecast.delay_probabilities.significant)}`}
            />
            <div
              className="bg-error"
              style={{ width: formatPercent(forecast.delay_probabilities.major) }}
              title={`30+ min: ${formatPercent(forecast.delay_probabilities.major)}`}
            />
          </div>
          <div className="flex justify-between mt-1 text-[10px] text-text-muted">
            <span>On time</span>
            <span>5-15m</span>
            <span>15-30m</span>
            <span>30m+</span>
          </div>
        </div>
      )}
    </div>
  );
}
