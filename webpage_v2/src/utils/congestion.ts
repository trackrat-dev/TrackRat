import type { FeatureCollection, LineString } from 'geojson';
import { CongestionCause, CongestionLevel, SegmentCongestion } from '../types';
import { getStationByCode } from '../data/stations';

// ---------------------------------------------------------------------------
// Level → visual mapping
//
// Single source of truth shared by the Network Status page badges and the
// congestion map. Keeping the badge classes and the map's line colors here
// (rather than duplicated across components) guarantees the two views stay
// consistent as levels are added or recolored.
// ---------------------------------------------------------------------------

/** Tailwind text-color class for a congestion level. */
export function getCongestionColor(level: CongestionLevel): string {
  switch (level) {
    case 'normal': return 'text-success';
    case 'moderate': return 'text-warning';
    case 'heavy': return 'text-error';
    case 'severe': return 'text-error';
  }
}

/** Tailwind background-tint class for a congestion level. */
export function getCongestionBg(level: CongestionLevel): string {
  switch (level) {
    case 'normal': return 'bg-success/15';
    case 'moderate': return 'bg-warning/15';
    case 'heavy': return 'bg-error/15';
    case 'severe': return 'bg-error/20';
  }
}

/**
 * What the backend says is wrong with this segment, defaulting to 'delays' for
 * older responses that predate the field.
 */
export function segmentCause(segment: SegmentCongestion): CongestionCause {
  return segment.congestion_cause ?? 'delays';
}

/** True when this segment's colour owes anything to cancellations. */
export function hasCancellationCause(segment: SegmentCongestion): boolean {
  return segmentCause(segment) !== 'delays';
}

/**
 * Full descriptive label (status-page badges).
 *
 * The tier adjective is always kept — it is what the colour shows — while the
 * noun names the actual cause. Calling a segment whose trains ran on time
 * "Severe delays" is false (#1638), and so is calling a segment that is both
 * delayed *and* cancelled "Severe cancellations", which would make the caption
 * contradict the non-zero delay shown beside it.
 */
export function getCongestionLabel(level: CongestionLevel, cause: CongestionCause = 'delays'): string {
  // A normal segment was not escalated by anything, so there is no cause to name.
  if (level === 'normal') return 'Normal';
  const tier = getCongestionShortLabel(level);
  switch (cause) {
    case 'delays': return `${tier} delays`;
    case 'cancellations': return `${tier} cancellations`;
    case 'both': return `${tier} delays and cancellations`;
  }
}

/** One-word label for compact surfaces (map legend), mirroring iOS's "Delay Levels" legend. */
export function getCongestionShortLabel(level: CongestionLevel): string {
  switch (level) {
    case 'normal': return 'Normal';
    case 'moderate': return 'Moderate';
    case 'heavy': return 'Heavy';
    case 'severe': return 'Severe';
  }
}

/**
 * Hex line/legend color per congestion level. `normal`/`moderate`/`heavy`
 * mirror the theme tokens used by the badges (--color-success / --color-warning
 * / --color-error, see index.css). `severe` escalates to a deeper red so all
 * four levels read distinctly on the map, matching the iOS map's four-tier
 * "Delay Levels" legend.
 */
export const CONGESTION_HEX: Record<CongestionLevel, string> = {
  normal: '#6B8E23',
  moderate: '#D4753E',
  heavy: '#A52A2A',
  severe: '#7A1F1F',
};

/** Congestion levels in ascending severity — legend + iteration order. */
export const CONGESTION_LEVELS: CongestionLevel[] = ['normal', 'moderate', 'heavy', 'severe'];

/**
 * Factor at which each tier's colour is reached, matching the backend's
 * bucket boundaries (`congestion_types.CONGESTION_THRESHOLD_*`). `severe` has
 * no upper bound as a tier, so 2.0 — twice the baseline transit time — anchors
 * the end of the ramp; beyond it the colour simply stays at full severe.
 */
const CONGESTION_RAMP_STOPS: ReadonlyArray<readonly [number, CongestionLevel]> = [
  [1.1, 'normal'],
  [1.25, 'moderate'],
  [1.5, 'heavy'],
  [2.0, 'severe'],
];

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff];
}

/** Uppercase to match CONGESTION_HEX, so an interpolated colour that lands on a
 *  tier is byte-identical to that tier's constant. */
function rgbToHex([r, g, b]: [number, number, number]): string {
  return (
    '#' + [r, g, b].map(c => Math.round(c).toString(16).padStart(2, '0')).join('')
  ).toUpperCase();
}

/**
 * Map-line colour for a congestion factor, interpolated continuously between
 * the tier colours instead of snapping to one of four.
 *
 * The tier colours still land exactly on their own thresholds, so the legend
 * keeps describing the map truthfully; only the space *between* thresholds is
 * filled in. This is what issue #1715 asked for: adjacent segments whose delays
 * differ slightly now differ slightly in colour, rather than one sitting at
 * 1.24 (full orange) beside one at 1.26 (full red).
 *
 * Everything at or below the `normal` threshold is flat green — that plateau is
 * the backend's "trains are on time" statement (see MIN_CONGESTION_DELAY_MINUTES,
 * which pins sub-minute noise to exactly 1.0) and must not be shaded, or ordinary
 * on-time track would read as faintly congested.
 *
 * Pass `effective_congestion_factor`, not `congestion_factor`, for aggregated
 * segments: the former is what `congestion_level` is bucketed from, so a segment
 * escalated by cancellations keeps its colour.
 */
export function congestionRampColor(factor: number): string {
  const [firstStop, firstLevel] = CONGESTION_RAMP_STOPS[0];
  if (!Number.isFinite(factor) || factor <= firstStop) return CONGESTION_HEX[firstLevel];

  for (let i = 1; i < CONGESTION_RAMP_STOPS.length; i++) {
    const [stop, level] = CONGESTION_RAMP_STOPS[i];
    if (factor >= stop) continue;
    const [prevStop, prevLevel] = CONGESTION_RAMP_STOPS[i - 1];
    const t = (factor - prevStop) / (stop - prevStop);
    const from = hexToRgb(CONGESTION_HEX[prevLevel]);
    const to = hexToRgb(CONGESTION_HEX[level]);
    return rgbToHex([
      from[0] + (to[0] - from[0]) * t,
      from[1] + (to[1] - from[1]) * t,
      from[2] + (to[2] - from[2]) * t,
    ]);
  }
  return CONGESTION_HEX[CONGESTION_RAMP_STOPS[CONGESTION_RAMP_STOPS.length - 1][1]];
}

/**
 * The factor a segment's colour should be ramped from. Falls back to the
 * delay-only factor when the backend predates `effective_congestion_factor`
 * (issue #1715), which only loses the cancellation shading, never the tier.
 */
export function segmentColorFactor(segment: SegmentCongestion): number {
  return segment.effective_congestion_factor ?? segment.congestion_factor;
}

/**
 * Average delay (minutes) across the segments that make up a route, or `null`
 * when no segment covers any of the route's consecutive station pairs.
 *
 * Congestion segments are undirected: the backend may return a pair as A→B or
 * B→A, so both collapse to a single canonical key (alphabetical order). On a
 * duplicate key we keep the segment with the larger sample count. Mirrors the
 * iOS `TrainSystemDetailView.averageDelay` computation so the two apps agree.
 */
export function averageRouteDelay(
  stationCodes: string[],
  segments: SegmentCongestion[],
): number | null {
  if (stationCodes.length < 2) return null;

  const canonicalKey = (a: string, b: string) => (a < b ? `${a}|${b}` : `${b}|${a}`);

  const byPair = new Map<string, SegmentCongestion>();
  for (const segment of segments) {
    const key = canonicalKey(segment.from_station, segment.to_station);
    const existing = byPair.get(key);
    if (existing && existing.sample_count >= segment.sample_count) continue;
    byPair.set(key, segment);
  }

  const delays: number[] = [];
  for (let i = 0; i < stationCodes.length - 1; i++) {
    const segment = byPair.get(canonicalKey(stationCodes[i], stationCodes[i + 1]));
    if (segment) delays.push(segment.average_delay_minutes);
  }
  if (delays.length === 0) return null;
  return delays.reduce((sum, d) => sum + d, 0) / delays.length;
}

// ---------------------------------------------------------------------------
// Map data preparation (pure — kept out of the component so it's unit-testable
// without a WebGL/MapLibre context).
// ---------------------------------------------------------------------------

interface Coordinates {
  lon: number;
  lat: number;
}

export interface RenderableSegment {
  segment: SegmentCongestion;
  from: Coordinates;
  to: Coordinates;
}

/**
 * Split segments into those renderable on the map (both endpoints resolve to
 * station coordinates) and a count of those skipped for lack of coordinates.
 *
 * Skipped segments are still shown in the status-page list; they're only
 * dropped from the map. Returning the count lets the caller surface coverage
 * gaps (e.g. via console.debug) rather than silently hiding data.
 */
export function partitionRenderableSegments(
  segments: SegmentCongestion[],
): { renderable: RenderableSegment[]; skipped: number } {
  const renderable: RenderableSegment[] = [];
  let skipped = 0;
  for (const segment of segments) {
    const from = getStationByCode(segment.from_station)?.coordinates;
    const to = getStationByCode(segment.to_station)?.coordinates;
    if (!from || !to) {
      skipped++;
      continue;
    }
    renderable.push({ segment, from, to });
  }
  return { renderable, skipped };
}

/**
 * Station pair a tap on this segment should navigate to. Skip-stop expansion
 * yields canonical sub-segments whose endpoints no train stops at (e.g. Amtrak
 * CWH→PHN); the backend supplies the real served leg the segment was derived
 * from so the tap lands on a populated departures board instead of an empty one
 * (#1560). Falls back to the segment's own endpoints when the backend omits it.
 */
export function navStationCodes(segment: SegmentCongestion): [string, string] {
  return [
    segment.real_from_station ?? segment.from_station,
    segment.real_to_station ?? segment.to_station,
  ];
}

export interface SegmentFeatureProperties {
  from_station: string;
  to_station: string;
  segment_name: string;
  congestion_level: CongestionLevel;
  average_delay_minutes: number;
  // Carried so the popup can explain a colored line whose trains ran on time,
  // instead of showing only the segment name over a red stroke (#1638).
  congestion_cause: CongestionCause;
  cancellation_count: number;
  color: string;
}

/**
 * One straight-line GeoJSON `LineString` feature per renderable segment,
 * carrying the properties the map layer and popup read (`color` drives the
 * data-driven line paint; `from_station`/`to_station` are the resolved served
 * pair that drives tap navigation, while `segment_name` keeps the canonical
 * stretch the user is hovering).
 */
export function buildSegmentFeatureCollection(
  renderable: RenderableSegment[],
): FeatureCollection<LineString, SegmentFeatureProperties> {
  return {
    type: 'FeatureCollection',
    features: renderable.map(({ segment, from, to }) => {
      const [navFrom, navTo] = navStationCodes(segment);
      return {
        type: 'Feature',
        properties: {
          from_station: navFrom,
          to_station: navTo,
          segment_name: `${segment.from_station_name} → ${segment.to_station_name}`,
          congestion_level: segment.congestion_level,
          average_delay_minutes: segment.average_delay_minutes,
          congestion_cause: segmentCause(segment),
          cancellation_count: segment.cancellation_count,
          color: congestionRampColor(segmentColorFactor(segment)),
        },
        geometry: {
          type: 'LineString',
          coordinates: [
            [from.lon, from.lat],
            [to.lon, to.lat],
          ],
        },
      };
    }),
  };
}

/** Bounding box as MapLibre expects it: `[[minLon, minLat], [maxLon, maxLat]]`. */
export type LngLatBounds = [[number, number], [number, number]];

/**
 * Bounding box covering every renderable segment endpoint, or `null` when
 * there's nothing to fit (the caller then falls back to a default view).
 */
export function computeSegmentBounds(renderable: RenderableSegment[]): LngLatBounds | null {
  if (renderable.length === 0) return null;
  let minLon = Infinity;
  let minLat = Infinity;
  let maxLon = -Infinity;
  let maxLat = -Infinity;
  for (const { from, to } of renderable) {
    for (const point of [from, to]) {
      if (point.lon < minLon) minLon = point.lon;
      if (point.lat < minLat) minLat = point.lat;
      if (point.lon > maxLon) maxLon = point.lon;
      if (point.lat > maxLat) maxLat = point.lat;
    }
  }
  return [
    [minLon, minLat],
    [maxLon, maxLat],
  ];
}
