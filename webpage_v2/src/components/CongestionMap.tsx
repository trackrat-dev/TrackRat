import { useState, useMemo, useCallback, useRef } from 'react';
import Map, { Source, Layer, Popup, NavigationControl } from 'react-map-gl/maplibre';
import type { MapLayerMouseEvent } from 'react-map-gl/maplibre';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useNavigate } from 'react-router-dom';
import { SegmentCongestion } from '../types';
import {
  partitionRenderableSegments,
  buildSegmentFeatureCollection,
  computeSegmentBounds,
  CONGESTION_HEX,
  CONGESTION_LEVELS,
  getCongestionShortLabel,
  SegmentFeatureProperties,
} from '../utils/congestion';

// Same tile source and containment approach as RouteMap so both maps share the
// lazy MapLibre chunk (no API key needed, CARTO Dark Matter raster style).
const DARK_TILES = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

const SOURCE_ID = 'congestion-segments';
const LINE_LAYER_ID = 'congestion-line-layer';
// A wide, fully-transparent line above the visible one gives a comfortable
// tap/hover target on mobile without changing how segments look.
const HIT_LAYER_ID = 'congestion-hit-layer';

// Default framing when no segment can be placed on the map: NYC metro area.
const NYC_FALLBACK = { longitude: -73.97, latitude: 40.73, zoom: 8.5 };

interface CongestionMapProps {
  segments: SegmentCongestion[];
}

interface HoverInfo {
  lng: number;
  lat: number;
  name: string;
  delay: number;
}

export function CongestionMap({ segments }: CongestionMapProps) {
  const navigate = useNavigate();
  const [isExpanded, setIsExpanded] = useState(false);
  const [cursor, setCursor] = useState('');
  const [hover, setHover] = useState<HoverInfo | null>(null);
  // Track the currently-highlighted feature so we can clear its hover state
  // before highlighting the next one.
  const hoveredIdRef = useRef<number | string | null>(null);

  const { featureCollection, bounds } = useMemo(() => {
    const { renderable, skipped } = partitionRenderableSegments(segments);
    if (skipped > 0) {
      // Surface coverage gaps rather than silently dropping segments; the list
      // on the status page still shows every segment.
      console.debug(
        `[CongestionMap] skipped ${skipped}/${segments.length} segment(s) missing station coordinates`,
      );
    }
    return {
      featureCollection: buildSegmentFeatureCollection(renderable),
      bounds: computeSegmentBounds(renderable),
    };
  }, [segments]);

  // `initialViewState` is only read once, at mount — later polls swap the
  // GeoJSON data without yanking the camera away from the user.
  const initialViewState = bounds
    ? { bounds, fitBoundsOptions: { padding: 40 } }
    : NYC_FALLBACK;

  const clearHover = useCallback((map: maplibregl.Map) => {
    if (hoveredIdRef.current !== null) {
      map.setFeatureState({ source: SOURCE_ID, id: hoveredIdRef.current }, { hover: false });
      hoveredIdRef.current = null;
    }
  }, []);

  const onMouseMove = useCallback(
    (e: MapLayerMouseEvent) => {
      const map = e.target;
      clearHover(map);
      const feature = e.features?.[0];
      if (feature && feature.id != null) {
        hoveredIdRef.current = feature.id;
        map.setFeatureState({ source: SOURCE_ID, id: feature.id }, { hover: true });
        const props = feature.properties as SegmentFeatureProperties;
        setHover({
          lng: e.lngLat.lng,
          lat: e.lngLat.lat,
          name: props.segment_name,
          delay: props.average_delay_minutes,
        });
        setCursor('pointer');
      } else {
        setHover(null);
        setCursor('');
      }
    },
    [clearHover],
  );

  const onMouseLeave = useCallback(
    (e: MapLayerMouseEvent) => {
      clearHover(e.target);
      setHover(null);
      setCursor('');
    },
    [clearHover],
  );

  const onClick = useCallback(
    (e: MapLayerMouseEvent) => {
      const feature = e.features?.[0];
      if (!feature) return;
      const props = feature.properties as SegmentFeatureProperties;
      navigate(`/trains/${props.from_station}/${props.to_station}`);
    },
    [navigate],
  );

  const toggleExpand = useCallback(() => setIsExpanded((v) => !v), []);

  return (
    <div className="relative rounded-xl overflow-hidden border border-text-muted/20 mb-4">
      <div
        className="transition-[height] duration-300 ease-in-out"
        style={{ height: isExpanded ? 320 : 160 }}
      >
        <Map
          mapLib={maplibregl}
          mapStyle={DARK_TILES}
          initialViewState={initialViewState}
          interactive={isExpanded}
          scrollZoom={isExpanded}
          dragPan={isExpanded}
          dragRotate={false}
          touchZoomRotate={isExpanded}
          doubleClickZoom={isExpanded}
          attributionControl={false}
          interactiveLayerIds={[HIT_LAYER_ID]}
          cursor={cursor}
          onClick={onClick}
          onMouseMove={onMouseMove}
          onMouseLeave={onMouseLeave}
          style={{ width: '100%', height: '100%' }}
        >
          {isExpanded && <NavigationControl position="top-right" showCompass={false} />}

          <Source id={SOURCE_ID} type="geojson" data={featureCollection} generateId>
            <Layer
              id={LINE_LAYER_ID}
              type="line"
              paint={{
                'line-color': ['get', 'color'],
                'line-width': ['case', ['boolean', ['feature-state', 'hover'], false], 6, 4],
                'line-opacity': 0.85,
              }}
              layout={{ 'line-cap': 'round', 'line-join': 'round' }}
            />
            <Layer
              id={HIT_LAYER_ID}
              type="line"
              paint={{ 'line-color': '#000000', 'line-width': 18, 'line-opacity': 0 }}
            />
          </Source>

          {hover && (
            <Popup
              longitude={hover.lng}
              latitude={hover.lat}
              closeButton={false}
              closeOnClick={false}
              offset={12}
              className="text-xs"
            >
              <div className="font-medium text-text-primary">{hover.name}</div>
              {hover.delay > 0 && (
                <div className="text-text-muted">+{hover.delay.toFixed(0)}m avg delay</div>
              )}
            </Popup>
          )}
        </Map>
      </div>

      {/* Legend — mirrors iOS's "Delay Levels" legend. */}
      <div className="absolute bottom-2 left-2 bg-black/60 backdrop-blur-sm rounded-md px-2 py-1.5 pointer-events-none">
        <div className="flex flex-col gap-1">
          {CONGESTION_LEVELS.map((level) => (
            <div key={level} className="flex items-center gap-1.5">
              <span
                className="w-3 h-1 rounded-full"
                style={{ backgroundColor: CONGESTION_HEX[level] }}
              />
              <span className="text-[10px] leading-none text-white/80">
                {getCongestionShortLabel(level)}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Expand/collapse toggle */}
      <button
        onClick={toggleExpand}
        className="absolute bottom-2 right-2 bg-black/60 backdrop-blur-sm text-white/80 text-xs px-2 py-1 rounded-md hover:bg-black/80 transition-colors"
        aria-label={isExpanded ? 'Collapse map' : 'Expand map'}
      >
        {isExpanded ? 'Collapse' : 'Expand'}
      </button>
    </div>
  );
}
