import { describe, it, expect } from 'vitest';
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
  it('returns date in YYYY-MM-DD format', () => {
    const result = getTodayDateString();
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

describe('isToday', () => {
  it('returns true for today', () => {
    const today = new Date().toISOString();
    expect(isToday(today)).toBe(true);
  });

  it('returns false for a past date', () => {
    expect(isToday('2020-01-01T00:00:00Z')).toBe(false);
  });

  it('returns true for invalid strings (defaults to today)', () => {
    expect(isToday('not-a-date')).toBe(true);
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
