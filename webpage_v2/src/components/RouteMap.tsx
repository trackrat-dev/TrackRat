import { useState, useMemo, useCallback } from 'react';
import Map, { Source, Layer, Marker, NavigationControl } from 'react-map-gl/maplibre';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Station } from '../types';

const DARK_TILES = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

const ROUTE_LINE_COLOR = '#CC5500'; // Accent/burnt orange fallback

interface RouteMapProps {
  fromStation: Station;
  toStation: Station;
  lineColor?: string;
}

function getBounds(from: Station, to: Station): [[number, number], [number, number]] {
  const fromCoords = from.coordinates!;
  const toCoords = to.coordinates!;
  const lats = [fromCoords.lat, toCoords.lat];
  const lons = [fromCoords.lon, toCoords.lon];
  return [
    [Math.min(...lons), Math.min(...lats)],
    [Math.max(...lons), Math.max(...lats)],
  ];
}

export function RouteMap({ fromStation, toStation, lineColor }: RouteMapProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const fromCoords = fromStation.coordinates;
  const toCoords = toStation.coordinates;

  // Don't render if either station lacks coordinates
  if (!fromCoords || !toCoords) return null;

  const color = lineColor || ROUTE_LINE_COLOR;

  const bounds = useMemo(() => getBounds(fromStation, toStation), [fromStation, toStation]);

  const routeGeoJSON = useMemo(
    () => ({
      type: 'Feature' as const,
      properties: {},
      geometry: {
        type: 'LineString' as const,
        coordinates: [
          [fromCoords.lon, fromCoords.lat],
          [toCoords.lon, toCoords.lat],
        ],
      },
    }),
    [fromCoords, toCoords],
  );

  const toggleExpand = useCallback(() => setIsExpanded((v) => !v), []);

  return (
    <div className="relative rounded-xl overflow-hidden border border-text-muted/20 mb-3">
      <div
        className="transition-[height] duration-300 ease-in-out"
        style={{ height: isExpanded ? 280 : 140 }}
      >
        <Map
          mapLib={maplibregl}
          mapStyle={DARK_TILES}
          initialViewState={{
            bounds,
            fitBoundsOptions: { padding: 50 },
          }}
          interactive={isExpanded}
          scrollZoom={isExpanded}
          dragPan={isExpanded}
          dragRotate={false}
          touchZoomRotate={isExpanded}
          doubleClickZoom={isExpanded}
          attributionControl={false}
          style={{ width: '100%', height: '100%' }}
          cursor={isExpanded ? undefined : 'default'}
        >
          {isExpanded && <NavigationControl position="top-right" showCompass={false} />}

          <Source id="route-line" type="geojson" data={routeGeoJSON}>
            <Layer
              id="route-line-layer"
              type="line"
              paint={{
                'line-color': color,
                'line-width': 3,
                'line-opacity': 0.8,
              }}
              layout={{
                'line-cap': 'round',
                'line-join': 'round',
              }}
            />
          </Source>

          {/* From station marker */}
          <Marker longitude={fromCoords.lon} latitude={fromCoords.lat}>
            <div
              className="w-3.5 h-3.5 rounded-full border-2 border-white"
              style={{ backgroundColor: color }}
              title={fromStation.name}
            />
          </Marker>

          {/* To station marker */}
          <Marker longitude={toCoords.lon} latitude={toCoords.lat}>
            <div
              className="w-3.5 h-3.5 rounded-full border-2 border-white"
              style={{ backgroundColor: color }}
              title={toStation.name}
            />
          </Marker>
        </Map>
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
