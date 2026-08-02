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
  navStationCodes,
  segmentCause,
  hasCancellationCause,
  computeSegmentBounds,
  averageRouteDelay,
  congestionRampColor,
  segmentRampColor,
  RenderableSegment,
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

  // #1638: a segment the backend escalated on cancellations has an average
  // delay of zero, so "Severe delays" is simply untrue. Keep the tier adjective
  // (it is what the color shows) and change the noun.
  it('names cancellations, not delays, when cancellations alone drove the level', () => {
    expect(getCongestionLabel('moderate', 'cancellations')).toBe('Moderate cancellations');
    expect(getCongestionLabel('heavy', 'cancellations')).toBe('Heavy cancellations');
    expect(getCongestionLabel('severe', 'cancellations')).toBe('Severe cancellations');
  });

  // Raised in review of #1681: a segment can be genuinely delayed AND pushed a
  // tier further by cancellations. Naming only one cause either contradicts the
  // non-zero delay shown beside it or hides the cancellations.
  it('names both causes when the segment is delayed and cancelled', () => {
    expect(getCongestionLabel('moderate', 'both')).toBe('Moderate delays and cancellations');
    expect(getCongestionLabel('heavy', 'both')).toBe('Heavy delays and cancellations');
    expect(getCongestionLabel('severe', 'both')).toBe('Severe delays and cancellations');
  });

  it('keeps the normal label unchanged whatever the cause', () => {
    // A normal segment was not escalated by definition, so no cause should
    // invent a story for it.
    for (const cause of ['delays', 'cancellations', 'both'] as const) {
      expect(getCongestionLabel('normal', cause)).toBe('Normal');
    }
  });

  it('defaults to delay wording when the cause is omitted', () => {
    // Older backend responses omit congestion_cause; the label must stay
    // exactly as it was rather than becoming undefined.
    expect(getCongestionLabel('severe')).toBe(getCongestionLabel('severe', 'delays'));
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

describe('segmentCause', () => {
  it("defaults to 'delays' for backends that predate the field", () => {
    expect(segmentCause(makeSegment())).toBe('delays');
    expect(hasCancellationCause(makeSegment())).toBe(false);
  });

  it('reports whichever cause the backend supplied', () => {
    expect(segmentCause(makeSegment({ congestion_cause: 'both' }))).toBe('both');
    expect(segmentCause(makeSegment({ congestion_cause: 'cancellations' }))).toBe('cancellations');
  });

  it("treats 'both' as involving cancellations", () => {
    // A mixed segment must still surface its cancellation count; counting only
    // the pure-cancellation case would drop it from the caption entirely.
    expect(hasCancellationCause(makeSegment({ congestion_cause: 'both' }))).toBe(true);
    expect(hasCancellationCause(makeSegment({ congestion_cause: 'cancellations' }))).toBe(true);
    expect(hasCancellationCause(makeSegment({ congestion_cause: 'delays' }))).toBe(false);
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

  // #1638: the hover popup only prints a delay line, so on a cancellation-
  // escalated segment (delay 0) it rendered a bare name over a red stroke.
  // These properties are what let it say why the line is colored.
  it('carries the cancellation cause onto the map feature', () => {
    const { renderable } = partitionRenderableSegments([
      makeSegment({
        congestion_level: 'severe',
        average_delay_minutes: 0,
        cancellation_count: 3,
        congestion_cause: 'cancellations',
      }),
    ]);
    const props = buildSegmentFeatureCollection(renderable).features[0].properties;
    expect(props.congestion_cause).toBe('cancellations');
    expect(props.cancellation_count).toBe(3);
  });

  it('carries the mixed cause through so the popup can show both facts', () => {
    const { renderable } = partitionRenderableSegments([
      makeSegment({
        congestion_level: 'heavy',
        average_delay_minutes: 2,
        cancellation_count: 3,
        congestion_cause: 'both',
      }),
    ]);
    const props = buildSegmentFeatureCollection(renderable).features[0].properties;
    expect(props.congestion_cause).toBe('both');
    expect(props.average_delay_minutes).toBe(2);
  });

  it("defaults congestion_cause to 'delays' when the backend omits it", () => {
    // MapLibre feature properties round-trip through the style spec, so an
    // undefined here would read back as a missing property.
    const { renderable } = partitionRenderableSegments([makeSegment()]);
    const props = buildSegmentFeatureCollection(renderable).features[0].properties;
    expect(props.congestion_cause).toBe('delays');
  });

  it('carries the properties the map layer and popup read', () => {
    const { renderable } = partitionRenderableSegments([
      makeSegment({
        from_station: 'NY',
        to_station: 'NP',
        from_station_name: 'New York Penn Station',
        to_station_name: 'Newark Penn Station',
        congestion_level: 'severe',
        // Consistent with the level: the stroke is ramped from the factor, so a
        // fixture whose factor said 1.2 while its level said 'severe' was only
        // ever asserting the old level→colour lookup.
        congestion_factor: 2.0,
        effective_congestion_factor: 2.0,
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
      congestion_cause: 'delays',
      cancellation_count: 0,
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

  it('navigation endpoints resolve to the real served pair, display stays canonical', () => {
    // Issue #1560: a skip-stop canonical sub-segment (Amtrak CWH→PHN — stations
    // no train stops at) draws on the CWH→PHN stretch but its tap must target
    // the real served leg TR→PH so the departures board is populated.
    const renderable: RenderableSegment[] = [
      {
        segment: makeSegment({
          from_station: 'CWH',
          to_station: 'PHN',
          from_station_name: 'Cornwells Heights',
          to_station_name: 'North Philadelphia',
          data_source: 'AMTRAK',
          real_from_station: 'TR',
          real_to_station: 'PH',
        }),
        from: { lon: NY.lon, lat: NY.lat },
        to: { lon: NP.lon, lat: NP.lat },
      },
    ];
    const [feature] = buildSegmentFeatureCollection(renderable).features;
    // Tap target = the served pair.
    expect(feature.properties.from_station).toBe('TR');
    expect(feature.properties.to_station).toBe('PH');
    // Hover label = the canonical stretch the user is pointing at.
    expect(feature.properties.segment_name).toBe(
      'Cornwells Heights → North Philadelphia',
    );
  });
});

describe('navStationCodes', () => {
  it('returns the real served pair when the backend supplies it', () => {
    const seg = makeSegment({
      from_station: 'CWH',
      to_station: 'PHN',
      real_from_station: 'TR',
      real_to_station: 'PH',
    });
    expect(navStationCodes(seg)).toEqual(['TR', 'PH']);
  });

  it('falls back to the segment endpoints when no real pair is present', () => {
    const seg = makeSegment({ from_station: 'NY', to_station: 'NP' });
    expect(navStationCodes(seg)).toEqual(['NY', 'NP']);
  });

  it('falls back per-endpoint when only one real code is present', () => {
    const seg = makeSegment({
      from_station: 'NY',
      to_station: 'NP',
      real_from_station: 'TR',
    });
    expect(navStationCodes(seg)).toEqual(['TR', 'NP']);
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

// ---------------------------------------------------------------------------
// Continuous colour ramp (issue #1715)
//
// The report was that the map jumps "from green directly to red directly back
// to green". Part of that is the backend's ratio amplifying short hops (fixed
// separately); the rest is that four hard buckets turn any difference at all
// into a full colour cliff. These tests pin the ramp that removes the cliff
// without moving where the named tiers actually sit.
// ---------------------------------------------------------------------------

/** '#rrggbb' → [r, g, b], so tests can reason about direction of travel. */
function rgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff];
}

/** Euclidean distance in RGB — a proxy for "how different do these look". */
function colorDistance(a: string, b: string): number {
  const [ar, ag, ab] = rgb(a);
  const [br, bg, bb] = rgb(b);
  return Math.hypot(ar - br, ag - bg, ab - bb);
}

describe('congestionRampColor', () => {
  it('renders every tier threshold as exactly that tier colour', () => {
    // The legend names four tiers; the ramp must still hit those exact colours
    // at the thresholds the backend buckets on, or the legend lies about the map.
    expect(congestionRampColor(1.1)).toBe(CONGESTION_HEX.normal);
    expect(congestionRampColor(1.25)).toBe(CONGESTION_HEX.moderate);
    expect(congestionRampColor(1.5)).toBe(CONGESTION_HEX.heavy);
    expect(congestionRampColor(2.0)).toBe(CONGESTION_HEX.severe);
  });

  it('keeps the on-time plateau flat green', () => {
    // Sub-minute noise is pinned to exactly 1.0 by the backend, and the great
    // majority of segments sit there. Shading that band would make ordinary
    // on-time track read as faintly congested.
    for (const factor of [0, 0.5, 0.82, 1.0, 1.05, 1.1]) {
      expect(congestionRampColor(factor)).toBe(CONGESTION_HEX.normal);
    }
  });

  it('clamps above the ramp instead of wrapping around', () => {
    // A stuck train can produce a factor of 5+; it must stay severe, not
    // overflow into some other colour.
    for (const factor of [2.0, 3.0, 5.21, 100]) {
      expect(congestionRampColor(factor)).toBe(CONGESTION_HEX.severe);
    }
  });

  it('interpolates between tiers instead of snapping', () => {
    // The midpoint of the moderate→heavy span must be a real blend: distinct
    // from both endpoints, and roughly equidistant from them.
    const mid = congestionRampColor(1.375);
    expect(mid).not.toBe(CONGESTION_HEX.moderate);
    expect(mid).not.toBe(CONGESTION_HEX.heavy);
    const toModerate = colorDistance(mid, CONGESTION_HEX.moderate);
    const toHeavy = colorDistance(mid, CONGESTION_HEX.heavy);
    expect(Math.abs(toModerate - toHeavy)).toBeLessThan(12);
  });

  it('moves smoothly across a threshold rather than cliff-edging', () => {
    // This is the actual defect: 1.24 vs 1.26 used to be two completely
    // different colours. Either side of a threshold must now look near-identical
    // — and much closer to each other than the tier colours are to each other.
    const below = congestionRampColor(1.24);
    const above = congestionRampColor(1.26);
    expect(colorDistance(below, above)).toBeLessThan(
      colorDistance(CONGESTION_HEX.moderate, CONGESTION_HEX.heavy) / 4,
    );
  });

  it('is continuous — no cliff anywhere along the ramp', () => {
    // This is the property the issue is actually about. Walking the ramp in
    // small steps, no step may produce a large colour jump; the four-bucket
    // version jumped the full tier-to-tier distance at three points.
    //
    // Deliberately not asserted as "distance from green increases": this
    // palette runs olive → orange → brick → dark red, and RGB distance from
    // either endpoint is genuinely non-monotonic across it. Continuity is the
    // real invariant; the tier-anchor test above pins the direction.
    const tierGap = colorDistance(CONGESTION_HEX.moderate, CONGESTION_HEX.heavy);
    let previous = congestionRampColor(1.1);
    for (let factor = 1.11; factor <= 2.0001; factor += 0.01) {
      const color = congestionRampColor(factor);
      expect(colorDistance(previous, color)).toBeLessThan(tierGap / 4);
      previous = color;
    }
  });

  it('always emits a well-formed hex colour', () => {
    for (let factor = 0.5; factor <= 2.5; factor += 0.017) {
      expect(congestionRampColor(factor)).toMatch(/^#[0-9A-F]{6}$/);
    }
  });

  it('falls back to green for a non-finite factor', () => {
    // Defensive: a malformed payload must not produce '#NaNNaNNaN'. Green
    // rather than red for both — a garbage factor is missing information, and
    // painting the map red on missing information invents an outage. The
    // backend already reports 1.0 when there is no baseline to divide by, so
    // neither value should reach here in practice.
    expect(congestionRampColor(NaN)).toBe(CONGESTION_HEX.normal);
    expect(congestionRampColor(Infinity)).toBe(CONGESTION_HEX.normal);
  });
});

describe('segmentRampColor', () => {
  it('ramps the cancellation-blended factor the backend bucketed from', () => {
    // A segment whose trains ran on time but were heavily cancelled is coloured
    // by the blended factor (#1638). Ramping the delay-only factor would drop
    // that escalation and paint it green.
    const segment = makeSegment({
      congestion_factor: 1.0,
      effective_congestion_factor: 1.75,
      congestion_level: 'severe',
    });
    expect(segmentRampColor(segment)).toBe(congestionRampColor(1.75));
    expect(segmentRampColor(segment)).not.toBe(CONGESTION_HEX.normal);
  });

  it('falls back to the tier colour, not the delay factor, when the blended one is absent', () => {
    // Regression guard for the pre-deployment cache window: a congestion cache
    // entry minted before effective_congestion_factor existed is still served
    // until its TTL expires. A cancellation-escalated segment in that payload
    // has congestion_level 'severe' with congestion_factor 1.0 — ramping the
    // factor would paint it green beside a status list reading "Severe
    // cancellations", which is exactly the #1638 contradiction.
    const segment = makeSegment({
      congestion_factor: 1.0,
      congestion_level: 'severe',
      congestion_cause: 'cancellations',
    });
    delete segment.effective_congestion_factor;
    expect(segmentRampColor(segment)).toBe(CONGESTION_HEX.severe);
  });

  it('falls back to each tier colour exactly', () => {
    for (const level of CONGESTION_LEVELS) {
      const segment = makeSegment({ congestion_level: level });
      delete segment.effective_congestion_factor;
      expect(segmentRampColor(segment)).toBe(CONGESTION_HEX[level]);
    }
  });

  it('prefers the blended factor even when it is lower than the tier suggests', () => {
    // The served field is authoritative: it is what the backend bucketed, so it
    // cannot disagree with the level on a fresh response.
    const segment = makeSegment({
      congestion_factor: 2.0,
      effective_congestion_factor: 1.0,
      congestion_level: 'normal',
    });
    expect(segmentRampColor(segment)).toBe(CONGESTION_HEX.normal);
  });
});
