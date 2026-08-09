import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { TrackPredictionBar } from './TrackPredictionBar';
import { apiService } from '../services/api';
import { PlatformPrediction } from '../types';

// Mirrors PREDICTION_POLL_MS in TrackPredictionBar.tsx.
const POLL_MS = 60_000;

function makePrediction(overrides: Partial<PlatformPrediction> = {}): PlatformPrediction {
  return {
    platform_probabilities: { '3': 0.6, '4': 0.4 },
    primary_prediction: '3',
    confidence: 0.6,
    top_3: ['3', '4'],
    model_version: 'test',
    station_code: 'NY',
    train_id: '3515',
    ...overrides,
  };
}

function renderBar() {
  return render(
    <TrackPredictionBar trainId="3515" originStationCode="NY" journeyDate="2025-01-15" />
  );
}

/** Flush the promise chain of the on-mount fetch without advancing the poll. */
async function flushMountFetch() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
}

async function advancePolls(count: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(POLL_MS * count);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  // usePolling checks document.hidden; jsdom defaults to visible, but be explicit.
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('TrackPredictionBar', () => {
  it('renders the segmented bar when the fetch succeeds, and keeps polling', async () => {
    const spy = vi.spyOn(apiService, 'getPlatformPrediction').mockResolvedValue(makePrediction());

    renderBar();
    await flushMountFetch();

    expect(screen.getByText('Track Predictions')).toBeInTheDocument();
    expect(spy).toHaveBeenCalledTimes(1);

    // Track assignments firm up as departure nears — the 200 case keeps polling.
    await advancePolls(2);
    expect(spy).toHaveBeenCalledTimes(3);
  });

  it('stops polling after a 404 (terminal arrival / unserved station)', async () => {
    // apiService maps a 404 from /predictions/track to null. That answer is
    // permanent for this train at this station (it terminates here or never
    // calls here), so the bar must not re-ask every minute forever.
    const spy = vi.spyOn(apiService, 'getPlatformPrediction').mockResolvedValue(null);

    renderBar();
    await flushMountFetch();

    // Nothing rendered — 404 means "no prediction here", not a failure.
    expect(screen.queryByText('Track Predictions')).not.toBeInTheDocument();
    expect(spy).toHaveBeenCalledTimes(1);

    // The poll interval elapses repeatedly; no further requests are made.
    await advancePolls(3);
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('keeps polling through transient failures', async () => {
    // A thrown error (network, 500) is transient — unlike a 404 it must NOT
    // halt the poll, or a blip would permanently hide the prediction.
    const spy = vi
      .spyOn(apiService, 'getPlatformPrediction')
      .mockRejectedValueOnce(new Error('network down'))
      .mockResolvedValue(makePrediction());

    renderBar();
    await flushMountFetch();

    expect(screen.getByText('Couldn’t load track predictions')).toBeInTheDocument();
    expect(spy).toHaveBeenCalledTimes(1);

    await advancePolls(1);
    expect(spy).toHaveBeenCalledTimes(2);
    expect(screen.getByText('Track Predictions')).toBeInTheDocument();
  });
});
