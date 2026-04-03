import { describe, expect, it } from 'vitest';
import { getTrainSearchCandidates, inferTrainSearchSystem } from './trainSearch';

describe('getTrainSearchCandidates', () => {
  it('returns numeric candidates for active train systems', () => {
    expect(getTrainSearchCandidates('3515', ['NJT', 'AMTRAK', 'LIRR', 'MNR'])).toEqual([
      '3515',
      'A3515',
      'L3515',
      'M3515',
    ]);
  });

  it('falls back to the core supported systems when no preference is set', () => {
    expect(getTrainSearchCandidates('3515')).toEqual([
      '3515',
      'A3515',
      'L3515',
      'M3515',
    ]);
  });

  it('keeps explicit prefixed searches intact', () => {
    expect(getTrainSearchCandidates('a174', ['NJT'])).toEqual(['A174']);
  });

  it('returns an empty array for non-train-like input', () => {
    expect(getTrainSearchCandidates('New York')).toEqual([]);
  });
});

describe('inferTrainSearchSystem', () => {
  it('infers the matching system from a prefixed train number', () => {
    expect(inferTrainSearchSystem('L602')).toBe('LIRR');
  });

  it('treats numeric train numbers as NJ Transit by default', () => {
    expect(inferTrainSearchSystem('3923')).toBe('NJT');
  });
});
