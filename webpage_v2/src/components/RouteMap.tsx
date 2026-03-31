import { useState, useMemo, useCallback } from 'react';
import Map, { Source, Layer, Marker, NavigationControl } from 'react-map-gl/maplibre';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Station } from '../types';
import { getStationByCode } from '../data/stations';
import { getIntermediateStations } from '../data/routeTopology';

const DARK_TILES = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

const ROUTE_LINE_COLOR = '#CC5500'; // Accent/burnt orange fallback

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
  const [isExpanded, setIsExpanded] = useState(false);

  const fromCoords = fromStation.coordinates;
  const toCoords = toStation.coordinates;

  // Don't render if either station lacks coordinates
  if (!fromCoords || !toCoords) return null;

  const color = lineColor || ROUTE_LINE_COLOR;

  const stops = useMemo(() => buildRouteStops(fromStation, toStation), [fromStation, toStation]);
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
