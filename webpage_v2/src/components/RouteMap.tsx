import { useState, useMemo, useCallback } from 'react';
import Map, { Source, Layer, Marker, NavigationControl } from 'react-map-gl/maplibre';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Station } from '../types';
import { getStationByCode } from '../data/stations';
import { getIntermediateStations } from '../data/routeTopology';
import { storageService } from '../services/storage';

// CARTO Positron: light basemap that matches the app's cream theme (no API key required).
const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';

const ROUTE_LINE_COLOR = '#CC5500'; // Accent/burnt orange fallback (dark enough for light tiles)

const MAP_HEIGHT = 260; // px, map height when expanded
const HEADER_HEIGHT = 44; // px, always-present toggle row (reserves space, no layout shift)

interface RouteMapProps {
  fromStation: Station;
  toStation: Station;
  lineColor?: string;
}

interface StopCoord {
  code: string;
  name: string;
  lon: number;
  lat: number;
}

/** Build the ordered list of all stops (from, intermediates, to) with coordinates. */
function buildRouteStops(from: Station, to: Station): StopCoord[] {
  const fromCoords = from.coordinates!;
  const toCoords = to.coordinates!;
  const stops: StopCoord[] = [{ code: from.code, name: from.name, lon: fromCoords.lon, lat: fromCoords.lat }];

  const intermediateCodes = getIntermediateStations(from.code, to.code, from.system);
  for (const code of intermediateCodes) {
    const station = getStationByCode(code);
    if (station?.coordinates) {
      stops.push({ code, name: station.name, lon: station.coordinates.lon, lat: station.coordinates.lat });
    }
  }

  stops.push({ code: to.code, name: to.name, lon: toCoords.lon, lat: toCoords.lat });
  return stops;
}

function getBounds(stops: StopCoord[]): [[number, number], [number, number]] {
  const lats = stops.map((s) => s.lat);
  const lons = stops.map((s) => s.lon);
  return [
    [Math.min(...lons), Math.min(...lats)],
    [Math.max(...lons), Math.max(...lats)],
  ];
}

export function RouteMap({ fromStation, toStation, lineColor }: RouteMapProps) {
  const [isExpanded, setIsExpanded] = useState(() => storageService.getMapExpanded());

  const fromCoords = fromStation.coordinates;
  const toCoords = toStation.coordinates;

  const color = lineColor || ROUTE_LINE_COLOR;

  const stops = useMemo(
    () => (fromCoords && toCoords ? buildRouteStops(fromStation, toStation) : []),
    [fromStation, toStation, fromCoords, toCoords],
  );
  const intermediateStops = stops.slice(1, -1);
  const bounds = useMemo(() => getBounds(stops), [stops]);

  const routeGeoJSON = useMemo(
    () => ({
      type: 'Feature' as const,
      properties: {},
      geometry: {
        type: 'LineString' as const,
        coordinates: stops.map((s) => [s.lon, s.lat]),
      },
    }),
    [stops],
  );

  const toggleExpand = useCallback(() => {
    setIsExpanded((v) => {
      const next = !v;
      storageService.setMapExpanded(next);
      return next;
    });
  }, []);

  // Don't render if either station lacks coordinates
  if (!fromCoords || !toCoords) return null;

  return (
    <div className="rounded-xl overflow-hidden border border-text-muted/20 mb-3">
      {/* Always-present toggle row: keeps the map opt-in and reserves a fixed height */}
      <button
        onClick={toggleExpand}
        className="w-full px-4 flex items-center justify-between bg-surface/50 backdrop-blur-xl hover:bg-surface transition-colors"
        style={{ height: HEADER_HEIGHT }}
        aria-expanded={isExpanded}
        aria-label={isExpanded ? 'Hide route map' : 'Show route map'}
      >
        <span className="text-sm font-medium text-text-primary flex items-center gap-2">
          <span aria-hidden="true">🗺️</span> Route map
        </span>
        <span className="text-text-muted text-xs">{isExpanded ? '▲' : '▼'}</span>
      </button>

      {isExpanded && (
        <div style={{ height: MAP_HEIGHT }}>
          <Map
            mapLib={maplibregl}
            mapStyle={MAP_STYLE}
            initialViewState={{
              bounds,
              fitBoundsOptions: { padding: 50 },
            }}
            dragRotate={false}
            attributionControl={false}
            style={{ width: '100%', height: '100%' }}
          >
            <NavigationControl position="top-right" showCompass={false} />

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

            {/* Intermediate stop markers */}
            {intermediateStops.map((stop) => (
              <Marker key={stop.code} longitude={stop.lon} latitude={stop.lat}>
                <div
                  className="w-2 h-2 rounded-full border border-white/60"
                  style={{ backgroundColor: color, opacity: 0.7 }}
                  title={stop.name}
                />
              </Marker>
            ))}

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
      )}
    </div>
  );
}
