import type { FeatureCollection, LineString } from 'geojson';
import { CongestionLevel, SegmentCongestion } from '../types';
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

/** Full descriptive label (status-page badges). */
export function getCongestionLabel(level: CongestionLevel): string {
  switch (level) {
    case 'normal': return 'Normal';
    case 'moderate': return 'Moderate delays';
    case 'heavy': return 'Heavy delays';
    case 'severe': return 'Severe delays';
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

export interface SegmentFeatureProperties {
  from_station: string;
  to_station: string;
  segment_name: string;
  congestion_level: CongestionLevel;
  average_delay_minutes: number;
  color: string;
}

/**
 * One straight-line GeoJSON `LineString` feature per renderable segment,
 * carrying the properties the map layer and popup read (`color` drives the
 * data-driven line paint; `from_station`/`to_station` drive tap navigation).
 */
export function buildSegmentFeatureCollection(
  renderable: RenderableSegment[],
): FeatureCollection<LineString, SegmentFeatureProperties> {
  return {
    type: 'FeatureCollection',
    features: renderable.map(({ segment, from, to }) => ({
      type: 'Feature',
      properties: {
        from_station: segment.from_station,
        to_station: segment.to_station,
        segment_name: `${segment.from_station_name} → ${segment.to_station_name}`,
        congestion_level: segment.congestion_level,
        average_delay_minutes: segment.average_delay_minutes,
        color: CONGESTION_HEX[segment.congestion_level],
      },
      geometry: {
        type: 'LineString',
        coordinates: [
          [from.lon, from.lat],
          [to.lon, to.lat],
        ],
      },
    })),
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
