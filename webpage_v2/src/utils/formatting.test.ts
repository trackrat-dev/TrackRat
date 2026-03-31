import { describe, it, expect } from 'vitest';
import { formatDelayText, getStatusBadgeClass } from './formatting';

describe('formatDelayText', () => {
  it('returns "On time" for zero delay', () => {
    expect(formatDelayText(0)).toBe('On time');
  });

  it('returns "On time" for negative delay (early)', () => {
    expect(formatDelayText(-3)).toBe('On time');
  });

  it('returns singular "1 min late" for exactly 1 minute', () => {
    expect(formatDelayText(1)).toBe('1 min late');
  });

  it('returns plural "X mins late" for delays > 1', () => {
    expect(formatDelayText(5)).toBe('5 mins late');
    expect(formatDelayText(30)).toBe('30 mins late');
  });
});

describe('getStatusBadgeClass', () => {
  it('returns success colors for "on time"', () => {
    const cls = getStatusBadgeClass('on time');
    expect(cls).toContain('bg-success/20');
    expect(cls).toContain('text-success');
  });

  it('returns accent colors for "boarding"', () => {
    const cls = getStatusBadgeClass('boarding');
    expect(cls).toContain('bg-accent/20');
    expect(cls).toContain('text-accent');
  });

  it('returns blue colors for "departed"', () => {
    const cls = getStatusBadgeClass('departed');
    expect(cls).toContain('text-blue-400');
  });

  it('returns warning colors for "delayed"', () => {
    const cls = getStatusBadgeClass('delayed');
    expect(cls).toContain('text-warning');
  });

  it('returns error colors for "cancelled"', () => {
    const cls = getStatusBadgeClass('cancelled');
    expect(cls).toContain('text-error');
  });

  it('returns success colors for "arrived"', () => {
    const cls = getStatusBadgeClass('arrived');
    expect(cls).toContain('text-success');
  });

  it('returns visible muted colors for unknown status (light theme)', () => {
    const cls = getStatusBadgeClass('something-unknown');
    expect(cls).toContain('bg-text-muted/15');
    expect(cls).toContain('text-text-secondary');
    // Should NOT have white text (invisible on light background)
    expect(cls).not.toContain('text-white');
  });

  it('is case-insensitive', () => {
    const cls = getStatusBadgeClass('On Time');
    expect(cls).toContain('text-success');
  });

  it('always includes base classes', () => {
    const cls = getStatusBadgeClass('on time');
    expect(cls).toContain('px-2');
    expect(cls).toContain('py-1');
    expect(cls).toContain('rounded-full');
    expect(cls).toContain('text-xs');
    expect(cls).toContain('font-semibold');
  });
});
