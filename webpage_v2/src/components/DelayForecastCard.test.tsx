import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { DelayForecastCard } from './DelayForecastCard';
import { apiService } from '../services/api';
import { DelayForecastResponse } from '../types';

// Mirrors FORECAST_POLL_MS in DelayForecastCard.tsx.
const POLL_MS = 60_000;
// Exact text (including the typographic apostrophe) rendered by the widget.
const NOTE = 'Couldn’t load delay forecast';

function makeForecast(overrides: Partial<DelayForecastResponse> = {}): DelayForecastResponse {
  return {
    train_id: '3515',
    station_code: 'NY',
    journey_date: '2025-01-15',
    cancellation_probability: 0.02,
    delay_probabilities: { on_time: 0.9, slight: 0.06, significant: 0.03, major: 0.01 },
    expected_delay_minutes: 0,
    confidence: 'high',
    sample_count: 42,
    factors: [],
    ...overrides,
  };
}

function renderCard() {
  return render(
    <DelayForecastCard trainId="3515" stationCode="NY" journeyDate="2025-01-15" />
  );
}

/** Flush the promise chain of the on-mount fetch without advancing the poll. */
async function flushMountFetch() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
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

describe('DelayForecastCard', () => {
  it('renders the forecast when the fetch succeeds', async () => {
    vi.spyOn(apiService, 'getDelayForecast').mockResolvedValue(makeForecast());

    renderCard();
    await flushMountFetch();

    expect(screen.getByText('Delay Forecast')).toBeInTheDocument();
    expect(screen.queryByText(NOTE)).not.toBeInTheDocument();
  });

  it('renders nothing when the forecast is unavailable here (null, not an error)', async () => {
    vi.spyOn(apiService, 'getDelayForecast').mockResolvedValue(null);

    const { container } = renderCard();
    await flushMountFetch();

    // A missing forecast is not an error — the slot stays empty, no note.
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText(NOTE)).not.toBeInTheDocument();
  });

  it('shows a muted note when the fetch fails, then clears it on the next successful poll', async () => {
    const spy = vi
      .spyOn(apiService, 'getDelayForecast')
      .mockRejectedValueOnce(new Error('network down'))
      .mockResolvedValue(makeForecast());

    renderCard();
    await flushMountFetch();

    // Failed initial load → inline note (never a blank page or unhandled rejection).
    expect(screen.getByText(NOTE)).toBeInTheDocument();
    expect(screen.queryByText('Delay Forecast')).not.toBeInTheDocument();

    // Next poll recovers on its own, with no user action.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS);
    });

    expect(spy).toHaveBeenCalledTimes(2);
    expect(screen.queryByText(NOTE)).not.toBeInTheDocument();
    expect(screen.getByText('Delay Forecast')).toBeInTheDocument();
  });

  it('keeps showing prior data (no note) when a later poll fails (stale-while-error)', async () => {
    const spy = vi
      .spyOn(apiService, 'getDelayForecast')
      .mockResolvedValueOnce(makeForecast())
      .mockRejectedValue(new Error('network down'));

    renderCard();
    await flushMountFetch();
    expect(screen.getByText('Delay Forecast')).toBeInTheDocument();

    // A later poll fails: keep the last-known forecast, do not flash the note.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS);
    });

    expect(spy).toHaveBeenCalledTimes(2);
    expect(screen.getByText('Delay Forecast')).toBeInTheDocument();
    expect(screen.queryByText(NOTE)).not.toBeInTheDocument();
  });

  it('passes the abort signal from the poller to the api call', async () => {
    const spy = vi.spyOn(apiService, 'getDelayForecast').mockResolvedValue(makeForecast());

    renderCard();
    await flushMountFetch();

    expect(spy).toHaveBeenCalledWith('3515', 'NY', '2025-01-15', expect.any(AbortSignal));
  });
});
