import { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import { PlatformPrediction } from '../types';

interface TrackPredictionBarProps {
  trainId: string;
  originStationCode: string;
  journeyDate: string;
}

interface PlatformSegment {
  platformName: string;
  probability: number;
}

export function TrackPredictionBar({ trainId, originStationCode, journeyDate }: TrackPredictionBarProps) {
  const [prediction, setPrediction] = useState<PlatformPrediction | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchPrediction() {
      setLoading(true);
      const result = await apiService.getPlatformPrediction(
        originStationCode,
        trainId,
        journeyDate
      );
      setPrediction(result);
      setLoading(false);
    }

    fetchPrediction();
  }, [originStationCode, trainId, journeyDate]);

  if (loading) {
    return (
      <div className="mt-3 p-3 bg-accent/5 border border-accent/20 rounded-xl">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-lg">🚋</span>
          <span className="text-sm font-semibold text-text-primary">Track Predictions</span>
        </div>
        <div className="h-16 bg-text-muted/10 rounded-lg animate-pulse" />
      </div>
    );
  }

  if (!prediction || !prediction.platform_probabilities) {
    return null; // Fail silently if no predictions
  }

  // Convert to segments and sort by platform number
  const segments: PlatformSegment[] = Object.entries(prediction.platform_probabilities)
    .map(([platformName, probability]) => ({
      platformName,
      probability,
    }))
    .sort((a, b) => {
      const getFirstNumber = (name: string) => {
        const match = name.match(/\d+/);
        return match ? parseInt(match[0]) : 999;
      };
      return getFirstNumber(a.platformName) - getFirstNumber(b.platformName);
    });

  // Filter out very low probability segments
  const visibleSegments = segments.filter(s => s.probability >= 0.05);

  if (visibleSegments.length === 0) {
    return null;
  }

  // Check if all segments are low confidence (< 17%)
  const hasOnlyLowConfidence = visibleSegments.every(s => s.probability < 0.17);

  return (
    <div className="mt-3 p-3 bg-accent/5 border border-accent/20 rounded-xl">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">🚋</span>
        <span className="text-sm font-semibold text-text-primary">Track Predictions</span>
      </div>

      {hasOnlyLowConfidence ? (
        <div className="py-4 text-center text-sm text-text-muted">
          No clear favorite
        </div>
      ) : (
        <>
          {/* Segmented bar */}
          <div className="flex h-16 rounded-lg overflow-hidden border border-text-muted/30">
            {visibleSegments.map((segment) => {
              const widthPercent = segment.probability * 100;
              const showLabel = segment.probability >= 0.15;

              return (
                <div
                  key={segment.platformName}
                  className="flex flex-col items-center justify-center bg-accent/40 border-r border-text-muted/20 last:border-r-0"
                  style={{ width: `${widthPercent}%` }}
                >
                  {showLabel && (
                    <span className="text-xs font-semibold text-white text-center leading-tight px-1">
                      {segment.platformName.includes('&') ? 'Tracks' : 'Track'}<br />{segment.platformName}
                    </span>
                  )}
                </div>
              );
            })}
          </div>

          {/* Percentages */}
          <div className="flex mt-1">
            {visibleSegments.map((segment) => {
              const widthPercent = segment.probability * 100;
              const showPercentage = segment.probability >= 0.15;

              return (
                <div
                  key={`pct-${segment.platformName}`}
                  className="flex items-center justify-center"
                  style={{ width: `${widthPercent}%` }}
                >
                  {showPercentage && (
                    <span className="text-xs font-medium text-text-secondary">
                      {Math.round(segment.probability * 100)}%
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
