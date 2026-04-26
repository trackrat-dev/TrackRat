import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePolling } from './usePolling';

beforeEach(() => {
  vi.useFakeTimers();
  // jsdom defaults document.hidden to false; reset visibility for each test.
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
});

afterEach(() => {
  vi.useRealTimers();
});

function setVisibility(hidden: boolean) {
  Object.defineProperty(document, 'hidden', { configurable: true, value: hidden });
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    value: hidden ? 'hidden' : 'visible',
  });
  document.dispatchEvent(new Event('visibilitychange'));
}

describe('usePolling', () => {
  it('runs callback immediately on mount', () => {
    const cb = vi.fn().mockResolvedValue(undefined);

    renderHook(() => usePolling(cb, [], { intervalMs: 1000 }));

    expect(cb).toHaveBeenCalledTimes(1);
    expect(cb.mock.calls[0][0]).toBeInstanceOf(AbortSignal);
  });

  it('runs callback on the configured interval', () => {
    const cb = vi.fn().mockResolvedValue(undefined);

    renderHook(() => usePolling(cb, [], { intervalMs: 1000 }));

    expect(cb).toHaveBeenCalledTimes(1);

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(cb).toHaveBeenCalledTimes(2);

    act(() => {
      vi.advanceTimersByTime(2500);
    });
    expect(cb).toHaveBeenCalledTimes(4);
  });

  it('does not run callback when enabled is false', () => {
    const cb = vi.fn().mockResolvedValue(undefined);

    renderHook(() => usePolling(cb, [], { intervalMs: 1000, enabled: false }));

    expect(cb).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(cb).not.toHaveBeenCalled();
  });

  it('aborts the previous in-flight request when interval fires', () => {
    const signals: AbortSignal[] = [];
    const cb = vi.fn(async (signal: AbortSignal) => {
      signals.push(signal);
      // never resolve — simulate slow request
      await new Promise(() => {});
    });

    renderHook(() => usePolling(cb, [], { intervalMs: 1000 }));

    expect(signals.length).toBe(1);
    expect(signals[0].aborted).toBe(false);

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(signals.length).toBe(2);
    expect(signals[0].aborted).toBe(true); // previous fetch aborted
    expect(signals[1].aborted).toBe(false);
  });

  it('aborts the in-flight request on unmount', () => {
    const signals: AbortSignal[] = [];
    const cb = vi.fn(async (signal: AbortSignal) => {
      signals.push(signal);
      await new Promise(() => {});
    });

    const { unmount } = renderHook(() => usePolling(cb, [], { intervalMs: 1000 }));

    expect(signals[0].aborted).toBe(false);

    unmount();

    expect(signals[0].aborted).toBe(true);
  });

  it('clears the interval on unmount (no further calls)', () => {
    const cb = vi.fn().mockResolvedValue(undefined);

    const { unmount } = renderHook(() => usePolling(cb, [], { intervalMs: 1000 }));

    expect(cb).toHaveBeenCalledTimes(1);
    unmount();

    act(() => {
      vi.advanceTimersByTime(10_000);
    });
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it('pauses interval when document becomes hidden', () => {
    const cb = vi.fn().mockResolvedValue(undefined);

    renderHook(() => usePolling(cb, [], { intervalMs: 1000 }));
    expect(cb).toHaveBeenCalledTimes(1);

    act(() => {
      setVisibility(true);
    });

    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(cb).toHaveBeenCalledTimes(1); // no extra calls while hidden
  });

  it('runs immediately and resumes interval when document becomes visible', () => {
    const cb = vi.fn().mockResolvedValue(undefined);

    renderHook(() => usePolling(cb, [], { intervalMs: 1000 }));
    expect(cb).toHaveBeenCalledTimes(1);

    act(() => {
      setVisibility(true);
    });
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(cb).toHaveBeenCalledTimes(1);

    act(() => {
      setVisibility(false);
    });
    expect(cb).toHaveBeenCalledTimes(2); // immediate fetch on visible

    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(cb).toHaveBeenCalledTimes(4); // interval resumed
  });

  it('re-runs when deps change and aborts previous request', () => {
    const signals: AbortSignal[] = [];
    const cb = vi.fn(async (signal: AbortSignal) => {
      signals.push(signal);
      await new Promise(() => {});
    });

    const { rerender } = renderHook(
      ({ key }: { key: string }) => usePolling(cb, [key], { intervalMs: 1000 }),
      { initialProps: { key: 'a' } }
    );

    expect(signals.length).toBe(1);

    rerender({ key: 'b' });

    expect(signals.length).toBe(2);
    expect(signals[0].aborted).toBe(true);
    expect(signals[1].aborted).toBe(false);
  });

  it('does not crash when the callback rejects with AbortError', async () => {
    const cb = vi.fn(async () => {
      throw new DOMException('Aborted', 'AbortError');
    });

    renderHook(() => usePolling(cb, [], { intervalMs: 1000 }));

    // Let the rejected promise settle without throwing
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(cb).toHaveBeenCalledTimes(1);
  });

  it('logs other rejections to console.error', async () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const cb = vi.fn().mockRejectedValue(new Error('boom'));

    renderHook(() => usePolling(cb, [], { intervalMs: 1000 }));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(errSpy).toHaveBeenCalled();
    errSpy.mockRestore();
  });
});
