import { describe, it, expect, vi, afterEach } from 'vitest';
import { formatTime, getDelayMinutes, getTodayDateString, isToday, formatDate } from './date';

describe('formatTime', () => {
  it('formats ISO datetime to 12-hour time', () => {
    expect(formatTime('2025-01-15T14:30:00Z')).toMatch(/2:30|9:30/); // depends on timezone
  });

  it('returns "N/A" for invalid date strings', () => {
    expect(formatTime('not-a-date')).toBe('N/A');
    expect(formatTime('')).toBe('N/A');
  });
});

describe('getDelayMinutes', () => {
  it('returns 0 when either arg is missing', () => {
    expect(getDelayMinutes(undefined, '2025-01-15T14:30:00Z')).toBe(0);
    expect(getDelayMinutes('2025-01-15T14:30:00Z', undefined)).toBe(0);
    expect(getDelayMinutes(undefined, undefined)).toBe(0);
  });

  it('calculates positive delay (actual after scheduled)', () => {
    const scheduled = '2025-01-15T14:00:00Z';
    const actual = '2025-01-15T14:05:00Z';
    expect(getDelayMinutes(scheduled, actual)).toBe(5);
  });

  it('calculates negative delay (early arrival)', () => {
    const scheduled = '2025-01-15T14:10:00Z';
    const actual = '2025-01-15T14:05:00Z';
    expect(getDelayMinutes(scheduled, actual)).toBe(-5);
  });

  it('returns 0 for matching times', () => {
    const time = '2025-01-15T14:00:00Z';
    expect(getDelayMinutes(time, time)).toBe(0);
  });

  it('returns 0 for invalid date strings', () => {
    expect(getDelayMinutes('bad', 'data')).toBe(0);
  });
});

describe('getTodayDateString', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns date in YYYY-MM-DD format', () => {
    const result = getTodayDateString();
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it('returns local calendar date, not UTC date', () => {
    vi.useFakeTimers();
    // Jan 15 at 23:30 UTC = Jan 15 in UTC, but could be Jan 16 in UTC+1.
    // getTodayDateString uses local time, so with fake timers (which default
    // to UTC internally in vitest/jsdom), this should return "2025-01-15".
    vi.setSystemTime(new Date('2025-01-15T23:30:00Z'));
    expect(getTodayDateString()).toBe('2025-01-15');
  });
});

describe('isToday', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns true for today as bare date string (backend format)', () => {
    const today = getTodayDateString();
    expect(isToday(today)).toBe(true);
  });

  it('returns true for today as full ISO string', () => {
    const today = new Date().toISOString();
    expect(isToday(today)).toBe(true);
  });

  it('returns false for a past date', () => {
    expect(isToday('2020-01-01')).toBe(false);
    expect(isToday('2020-01-01T00:00:00Z')).toBe(false);
  });

  it('returns true for invalid strings (defaults to today)', () => {
    expect(isToday('not-a-date')).toBe(true);
    expect(isToday('')).toBe(true);
  });

  it('uses string comparison, not parseISO — avoids UTC midnight bug', () => {
    vi.useFakeTimers();
    // Simulate Jan 14 at 23:30 local time (via fake timers in UTC).
    // The old parseISO("2025-01-15") would produce UTC midnight Jan 15,
    // which date-fns isToday() would compare against the local day (Jan 14)
    // and incorrectly return false in some timezones. With string comparison,
    // "2025-01-15" !== "2025-01-14" correctly returns false.
    vi.setSystemTime(new Date('2025-01-14T23:30:00Z'));
    expect(getTodayDateString()).toBe('2025-01-14');
    expect(isToday('2025-01-14')).toBe(true);
    expect(isToday('2025-01-15')).toBe(false);
  });

  it('correctly handles bare date vs full ISO for the same day', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2025-06-20T12:00:00Z'));
    expect(isToday('2025-06-20')).toBe(true);
    expect(isToday('2025-06-20T00:00:00Z')).toBe(true);
    expect(isToday('2025-06-20T23:59:59Z')).toBe(true);
    expect(isToday('2025-06-21')).toBe(false);
    expect(isToday('2025-06-19')).toBe(false);
  });
});

describe('formatDate', () => {
  it('formats ISO date to readable format', () => {
    expect(formatDate('2025-01-15T14:30:00Z')).toBe('Jan 15, 2025');
  });

  it('returns original string for invalid dates', () => {
    expect(formatDate('not-a-date')).toBe('not-a-date');
  });
});
