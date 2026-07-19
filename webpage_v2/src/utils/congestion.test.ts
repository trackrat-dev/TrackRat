import { describe, it, expect } from 'vitest';
import { CongestionLevel, SegmentCongestion } from '../types';
import { getStationByCode } from '../data/stations';
import {
  getCongestionColor,
  getCongestionBg,
  getCongestionLabel,
  getCongestionShortLabel,
  CONGESTION_HEX,
  CONGESTION_LEVELS,
  partitionRenderableSegments,
  buildSegmentFeatureCollection,
  computeSegmentBounds,
  averageRouteDelay,
} from './congestion';

// Real stations (all carry coordinates in data/stations.ts) so the tests
// exercise the actual code path instead of mocked lookups.
const NY = getStationByCode('NY')!.coordinates!; // New York Penn
const NP = getStationByCode('NP')!.coordinates!; // Newark Penn
const HB = getStationByCode('HB')!.coordinates!; // Hoboken
// A code the static station list doesn't know about — simulates a backend
// coverage gap (segment present, coordinates absent).
const MISSING = '__NO_SUCH_STATION__';

function makeSegment(overrides: Partial<SegmentCongestion> = {}): SegmentCongestion {
  return {
    from_station: 'NY',
    to_station: 'NP',
    from_station_name: 'New York Penn Station',
    to_station_name: 'Newark Penn Station',
    data_source: 'NJT',
    congestion_level: 'moderate',
    congestion_factor: 1.2,
    average_delay_minutes: 5,
    sample_count: 10,
    baseline_minutes: 20,
    current_average_minutes: 25,
    cancellation_count: 0,
    cancellation_rate: 0,
    train_count: 8,
    baseline_train_count: 10,
    frequency_factor: 0.8,
    frequency_level: 'healthy',
    ...overrides,
  };
}

const ALL_LEVELS: CongestionLevel[] = ['normal', 'moderate', 'heavy', 'severe'];

describe('congestion level → visual mapping', () => {
  it('maps every level to a text-color class', () => {
    expect(getCongestionColor('normal')).toBe('text-success');
    expect(getCongestionColor('moderate')).toBe('text-warning');
    expect(getCongestionColor('heavy')).toBe('text-error');
    expect(getCongestionColor('severe')).toBe('text-error');
  });

  it('maps every level to a background-tint class', () => {
    expect(getCongestionBg('normal')).toBe('bg-success/15');
    expect(getCongestionBg('moderate')).toBe('bg-warning/15');
    expect(getCongestionBg('heavy')).toBe('bg-error/15');
    expect(getCongestionBg('severe')).toBe('bg-error/20');
  });

  it('gives full descriptive labels for badges', () => {
    expect(getCongestionLabel('normal')).toBe('Normal');
    expect(getCongestionLabel('moderate')).toBe('Moderate delays');
    expect(getCongestionLabel('heavy')).toBe('Heavy delays');
    expect(getCongestionLabel('severe')).toBe('Severe delays');
  });

  it('gives one-word labels for the compact map legend', () => {
    expect(getCongestionShortLabel('normal')).toBe('Normal');
    expect(getCongestionShortLabel('moderate')).toBe('Moderate');
    expect(getCongestionShortLabel('heavy')).toBe('Heavy');
    expect(getCongestionShortLabel('severe')).toBe('Severe');
  });

  it('has a hex color for every level, each a valid #RRGGBB', () => {
    for (const level of ALL_LEVELS) {
      expect(CONGESTION_HEX[level]).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
  });

  it('escalates severe to a distinct, darker red than heavy', () => {
    // normal/moderate/heavy mirror the theme tokens; severe must stand apart so
    // all four legend rows read distinctly.
    expect(CONGESTION_HEX.heavy).toBe('#A52A2A');
    expect(CONGESTION_HEX.severe).not.toBe(CONGESTION_HEX.heavy);
    const distinct = new Set(Object.values(CONGESTION_HEX));
    expect(distinct.size).toBe(4);
  });

  it('lists levels in ascending severity', () => {
    expect(CONGESTION_LEVELS).toEqual(['normal', 'moderate', 'heavy', 'severe']);
  });
});

describe('partitionRenderableSegments', () => {
  it('keeps segments whose endpoints both resolve to coordinates', () => {
    const segments = [
      makeSegment({ from_station: 'NY', to_station: 'NP' }),
      makeSegment({ from_station: 'NP', to_station: 'HB' }),
    ];
    const { renderable, skipped } = partitionRenderableSegments(segments);
    expect(skipped).toBe(0);
    expect(renderable).toHaveLength(2);
    expect(renderable[0].from).toEqual(NY);
    expect(renderable[0].to).toEqual(NP);
  });

  it('skips and counts segments missing coordinates on either endpoint', () => {
    const segments = [
      makeSegment({ from_station: MISSING, to_station: 'NP' }),
      makeSegment({ from_station: 'NY', to_station: MISSING }),
    ];
    const { renderable, skipped } = partitionRenderableSegments(segments);
    expect(renderable).toHaveLength(0);
    expect(skipped).toBe(2);
  });

  it('partitions a mixed list, preserving renderable order', () => {
    const segments = [
      makeSegment({ from_station: 'NY', to_station: 'NP' }),
      makeSegment({ from_station: MISSING, to_station: 'HB' }),
      makeSegment({ from_station: 'NP', to_station: 'HB' }),
    ];
    const { renderable, skipped } = partitionRenderableSegments(segments);
    expect(skipped).toBe(1);
    expect(renderable.map((r) => r.segment.from_station)).toEqual(['NY', 'NP']);
  });

  it('returns empty result for an empty input', () => {
    expect(partitionRenderableSegments([])).toEqual({ renderable: [], skipped: 0 });
  });
});

describe('buildSegmentFeatureCollection', () => {
  it('produces exactly one LineString feature per renderable segment', () => {
    const { renderable } = partitionRenderableSegments([
      makeSegment({ from_station: 'NY', to_station: 'NP' }),
      makeSegment({ from_station: 'NP', to_station: 'HB' }),
    ]);
    const fc = buildSegmentFeatureCollection(renderable);
    expect(fc.type).toBe('FeatureCollection');
    expect(fc.features).toHaveLength(2);
    for (const feature of fc.features) {
      expect(feature.geometry.type).toBe('LineString');
    }
  });

  it('carries the properties the map layer and popup read', () => {
    const { renderable } = partitionRenderableSegments([
      makeSegment({
        from_station: 'NY',
        to_station: 'NP',
        from_station_name: 'New York Penn Station',
        to_station_name: 'Newark Penn Station',
        congestion_level: 'severe',
        average_delay_minutes: 12,
      }),
    ]);
    const [feature] = buildSegmentFeatureCollection(renderable).features;
    expect(feature.properties).toEqual({
      from_station: 'NY',
      to_station: 'NP',
      segment_name: 'New York Penn Station → Newark Penn Station',
      congestion_level: 'severe',
      average_delay_minutes: 12,
      color: CONGESTION_HEX.severe,
    });
  });

  it('orders coordinates [lon, lat] from → to', () => {
    const { renderable } = partitionRenderableSegments([
      makeSegment({ from_station: 'NY', to_station: 'NP' }),
    ]);
    const [feature] = buildSegmentFeatureCollection(renderable).features;
    expect(feature.geometry.coordinates).toEqual([
      [NY.lon, NY.lat],
      [NP.lon, NP.lat],
    ]);
  });

  it('produces an empty FeatureCollection for no renderable segments', () => {
    const fc = buildSegmentFeatureCollection([]);
    expect(fc.features).toHaveLength(0);
  });
});

describe('computeSegmentBounds', () => {
  it('returns null when there is nothing to fit', () => {
    expect(computeSegmentBounds([])).toBeNull();
  });

  it('computes the bounding box across all endpoints', () => {
    const { renderable } = partitionRenderableSegments([
      makeSegment({ from_station: 'NY', to_station: 'NP' }),
      makeSegment({ from_station: 'NP', to_station: 'HB' }),
    ]);
    const bounds = computeSegmentBounds(renderable);
    expect(bounds).not.toBeNull();
    const [[minLon, minLat], [maxLon, maxLat]] = bounds!;
    expect(minLon).toBeCloseTo(Math.min(NY.lon, NP.lon, HB.lon), 6);
    expect(maxLon).toBeCloseTo(Math.max(NY.lon, NP.lon, HB.lon), 6);
    expect(minLat).toBeCloseTo(Math.min(NY.lat, NP.lat, HB.lat), 6);
    expect(maxLat).toBeCloseTo(Math.max(NY.lat, NP.lat, HB.lat), 6);
  });

  it('handles a single segment (bounds are its two endpoints)', () => {
    const { renderable } = partitionRenderableSegments([
      makeSegment({ from_station: 'NY', to_station: 'HB' }),
    ]);
    const bounds = computeSegmentBounds(renderable)!;
    expect(bounds).toEqual([
      [Math.min(NY.lon, HB.lon), Math.min(NY.lat, HB.lat)],
      [Math.max(NY.lon, HB.lon), Math.max(NY.lat, HB.lat)],
    ]);
  });
});

describe('averageRouteDelay', () => {
  const seg = (from: string, to: string, delay: number, samples = 10) =>
    makeSegment({ from_station: from, to_station: to, average_delay_minutes: delay, sample_count: samples });

  it('returns null for a route with fewer than two stations', () => {
    expect(averageRouteDelay([], [])).toBeNull();
    expect(averageRouteDelay(['NY'], [seg('NY', 'NP', 5)])).toBeNull();
  });

  it('returns null when no segment covers a consecutive pair', () => {
    expect(averageRouteDelay(['NY', 'NP', 'HB'], [seg('AA', 'BB', 5)])).toBeNull();
  });

  it('averages delays across the route’s consecutive pairs', () => {
    // NY→NP = 4, NP→HB = 8  → mean 6
    const delay = averageRouteDelay(['NY', 'NP', 'HB'], [seg('NY', 'NP', 4), seg('NP', 'HB', 8)]);
    expect(delay).toBeCloseTo(6, 6);
  });

  it('matches segments regardless of direction (undirected pairs)', () => {
    // Route is NY→NP but the segment is reported as NP→NY; it must still match.
    const delay = averageRouteDelay(['NY', 'NP'], [seg('NP', 'NY', 5)]);
    expect(delay).toBeCloseTo(5, 6);
  });

  it('prefers the segment with more samples on a duplicate pair', () => {
    const delay = averageRouteDelay(
      ['NY', 'NP'],
      [seg('NY', 'NP', 2, 5), seg('NP', 'NY', 9, 50)],
    );
    expect(delay).toBeCloseTo(9, 6);
  });

  it('ignores pairs with no segment and averages only the covered ones', () => {
    // Only NY→NP is covered (delay 6); NP→HB has no segment.
    const delay = averageRouteDelay(['NY', 'NP', 'HB'], [seg('NY', 'NP', 6)]);
    expect(delay).toBeCloseTo(6, 6);
  });
});
