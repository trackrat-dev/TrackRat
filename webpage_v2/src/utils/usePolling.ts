import { useEffect, useRef } from 'react';

/**
 * Default polling interval used across the app for real-time train data.
 * Matches the backend's typical update cadence.
 */
export const DEFAULT_POLLING_INTERVAL_MS = 30_000;

interface UsePollingOptions {
  /** Polling interval in milliseconds. */
  intervalMs?: number;
  /**
   * If false, no polling happens (the callback is not invoked at all).
   * Use for cases like "future-dated views" where polling is meaningless.
   * Defaults to true.
   */
  enabled?: boolean;
}

/**
 * Run an async callback on mount, then on a recurring interval, with three
 * properties that the previous setInterval-based pattern lacked:
 *
 * 1. The callback receives an `AbortSignal` that is aborted on unmount, on
 *    dependency change, and just before each new tick fires. Pass it to
 *    `fetch`/api methods so in-flight requests are cancelled instead of
 *    racing to set state on an unmounted component.
 * 2. When the document becomes hidden the interval pauses; when it becomes
 *    visible again the callback runs immediately and the interval resumes.
 *    This avoids burning battery and API quota on background tabs.
 * 3. AbortError is silently swallowed (cancellation is not a failure), but
 *    other rejections are still surfaced to the caller's own handlers.
 *
 * The callback is intentionally not memoized internally — the caller passes
 * a `deps` array that mirrors React's standard effect contract. Treat the
 * callback like the body of a `useEffect`: capture state via closures, and
 * include any reactive values used inside `deps`.
 */
export function usePolling(
  callback: (signal: AbortSignal) => Promise<void> | void,
  deps: ReadonlyArray<unknown>,
  options: UsePollingOptions = {}
): void {
  const { intervalMs = DEFAULT_POLLING_INTERVAL_MS, enabled = true } = options;

  // Hold the latest callback in a ref so visibilitychange handlers always
  // call the most recent version without us having to re-bind listeners.
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useEffect(() => {
    if (!enabled) return;

    let intervalId: ReturnType<typeof setInterval> | null = null;
    let currentController: AbortController | null = null;
    let cancelled = false;

    const runOnce = () => {
      // Abort any prior in-flight request before starting a new one.
      currentController?.abort();
      const controller = new AbortController();
      currentController = controller;

      Promise.resolve(callbackRef.current(controller.signal)).catch((err) => {
        // Cancellation is not a failure — only real errors propagate.
        if (err instanceof DOMException && err.name === 'AbortError') return;
        // Surface unexpected errors via console; the callback's own try/catch
        // is responsible for user-visible error UI.
        console.error('[usePolling] callback rejected:', err);
      });
    };

    const startInterval = () => {
      if (intervalId !== null) return;
      intervalId = setInterval(runOnce, intervalMs);
    };

    const stopInterval = () => {
      if (intervalId !== null) {
        clearInterval(intervalId);
        intervalId = null;
      }
    };

    const onVisibilityChange = () => {
      if (cancelled) return;
      if (document.hidden) {
        stopInterval();
        // Don't abort the in-flight request — let it complete and update state
        // so the user sees fresh data when they return.
      } else {
        runOnce();
        startInterval();
      }
    };

    // Initial run + interval
    runOnce();
    if (!document.hidden) {
      startInterval();
    }

    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      cancelled = true;
      document.removeEventListener('visibilitychange', onVisibilityChange);
      stopInterval();
      currentController?.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, intervalMs, ...deps]);
}
