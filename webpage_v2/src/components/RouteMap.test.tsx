import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { RouteMap } from './RouteMap';
import { Station } from '../types';

// Mock maplibre-gl since jsdom has no WebGL
vi.mock('maplibre-gl', () => ({
  default: {
    Map: vi.fn(),
    NavigationControl: vi.fn(),
    Marker: vi.fn(),
  },
}));

// Mock react-map-gl/maplibre to render children without WebGL
vi.mock('react-map-gl/maplibre', () => ({
  default: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
    <div data-testid="map-container" data-interactive={String(props.interactive)}>
      {children}
    </div>
  ),
  Source: ({ children }: React.PropsWithChildren) => <div data-testid="map-source">{children}</div>,
  Layer: (props: Record<string, unknown>) => <div data-testid="map-layer" data-layer-id={props.id} />,
  Marker: ({ children, longitude, latitude }: React.PropsWithChildren<{ longitude: number; latitude: number }>) => (
    <div data-testid="map-marker" data-lon={longitude} data-lat={latitude}>
      {children}
    </div>
  ),
  NavigationControl: () => <div data-testid="nav-control" />,
}));

const stationWithCoords = (code: string, name: string, lat: number, lon: number, system: Station['system'] = 'NJT'): Station => ({
  code,
  name,
  system,
  coordinates: { lat, lon },
});

const stationWithoutCoords = (code: string, name: string): Station => ({
  code,
  name,
  system: 'NJT',
});

describe('RouteMap', () => {
  // TR → NY: 14 intermediate NEC stations (SE, NP, NA, NZ, EZ, LI, RH, MP, MU, ED, NB, JA, PJ, HL)
  const fromStation = stationWithCoords('TR', 'Trenton', 40.2185, -74.7539);
  const toStation = stationWithCoords('NY', 'New York Penn Station', 40.7500, -73.9924);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders map with from/to markers, intermediate stops, and a route line', () => {
    render(<RouteMap fromStation={fromStation} toStation={toStation} />);

    expect(screen.getByTestId('map-container')).toBeInTheDocument();
    expect(screen.getByTestId('map-source')).toBeInTheDocument();
    expect(screen.getByTestId('map-layer')).toBeInTheDocument();

    const markers = screen.getAllByTestId('map-marker');
    // 14 intermediate + 2 endpoints = 16
    expect(markers.length).toBeGreaterThanOrEqual(2);
    expect(markers.length).toBe(16);

    // Last two markers should be from/to endpoints (rendered after intermediates)
    const fromMarker = markers[markers.length - 2];
    const toMarker = markers[markers.length - 1];
    expect(fromMarker).toHaveAttribute('data-lon', String(fromStation.coordinates!.lon));
    expect(fromMarker).toHaveAttribute('data-lat', String(fromStation.coordinates!.lat));
    expect(toMarker).toHaveAttribute('data-lon', String(toStation.coordinates!.lon));
    expect(toMarker).toHaveAttribute('data-lat', String(toStation.coordinates!.lat));
  });

  it('renders only 2 markers for adjacent stations with no intermediates', () => {
    // PJ and HL are adjacent on NEC
    const pj = stationWithCoords('PJ', 'Princeton Junction', 40.3163, -74.6238);
    const hl = stationWithCoords('HL', 'Hamilton', 40.2553, -74.7041);

    render(<RouteMap fromStation={pj} toStation={hl} />);

    const markers = screen.getAllByTestId('map-marker');
    expect(markers).toHaveLength(2);
  });

  it('renders only 2 markers for stations not on the same route', () => {
    // Station on a different system with no shared route
    const bart = stationWithCoords('BART_EMBR', 'Embarcadero', 37.7929, -122.3970, 'BART');
    render(<RouteMap fromStation={fromStation} toStation={bart} />);

    const markers = screen.getAllByTestId('map-marker');
    expect(markers).toHaveLength(2);
  });

  it('returns null when fromStation has no coordinates', () => {
    const noCoords = stationWithoutCoords('XX', 'Unknown');
    const { container } = render(<RouteMap fromStation={noCoords} toStation={toStation} />);
    expect(container.innerHTML).toBe('');
  });

  it('returns null when toStation has no coordinates', () => {
    const noCoords = stationWithoutCoords('YY', 'Unknown');
    const { container } = render(<RouteMap fromStation={fromStation} toStation={noCoords} />);
    expect(container.innerHTML).toBe('');
  });

  it('starts collapsed and expands on button click', () => {
    render(<RouteMap fromStation={fromStation} toStation={toStation} />);

    const toggle = screen.getByRole('button', { name: /expand/i });
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveTextContent('Expand');

    // Map should be non-interactive when collapsed
    expect(screen.getByTestId('map-container')).toHaveAttribute('data-interactive', 'false');

    // Expand
    fireEvent.click(toggle);
    expect(screen.getByRole('button', { name: /collapse/i })).toHaveTextContent('Collapse');

    // Map should be interactive when expanded
    expect(screen.getByTestId('map-container')).toHaveAttribute('data-interactive', 'true');

    // Navigation control appears when expanded
    expect(screen.getByTestId('nav-control')).toBeInTheDocument();
  });

  it('collapses back when clicking collapse button', () => {
    render(<RouteMap fromStation={fromStation} toStation={toStation} />);

    // Expand first
    fireEvent.click(screen.getByRole('button', { name: /expand/i }));
    expect(screen.getByTestId('nav-control')).toBeInTheDocument();

    // Collapse
    fireEvent.click(screen.getByRole('button', { name: /collapse/i }));
    expect(screen.getByRole('button', { name: /expand/i })).toBeInTheDocument();
    expect(screen.queryByTestId('nav-control')).not.toBeInTheDocument();
  });

  it('uses custom lineColor for endpoint markers', () => {
    render(
      <RouteMap fromStation={fromStation} toStation={toStation} lineColor="#003DA5" />,
    );

    const markers = screen.getAllByTestId('map-marker');
    // Check the from/to endpoint markers (last 2)
    const fromDot = markers[markers.length - 2].querySelector('div');
    const toDot = markers[markers.length - 1].querySelector('div');
    expect(fromDot).toHaveStyle({ backgroundColor: '#003DA5' });
    expect(toDot).toHaveStyle({ backgroundColor: '#003DA5' });
  });

  it('uses default accent color when no lineColor provided', () => {
    render(<RouteMap fromStation={fromStation} toStation={toStation} />);

    const markers = screen.getAllByTestId('map-marker');
    const fromDot = markers[markers.length - 2].querySelector('div');
    const toDot = markers[markers.length - 1].querySelector('div');
    expect(fromDot).toHaveStyle({ backgroundColor: '#CC5500' });
    expect(toDot).toHaveStyle({ backgroundColor: '#CC5500' });
  });

  it('intermediate stop markers are smaller than endpoint markers', () => {
    render(<RouteMap fromStation={fromStation} toStation={toStation} />);

    const markers = screen.getAllByTestId('map-marker');
    // First marker is an intermediate stop (smaller: w-2 h-2)
    const intermediateDot = markers[0].querySelector('div');
    expect(intermediateDot).toHaveClass('w-2', 'h-2');

    // Last markers are endpoints (larger: w-3.5 h-3.5)
    const endpointDot = markers[markers.length - 1].querySelector('div');
    expect(endpointDot).toHaveClass('w-3.5', 'h-3.5');
  });

  it('renders route line layer with correct id', () => {
    render(<RouteMap fromStation={fromStation} toStation={toStation} />);

    const layer = screen.getByTestId('map-layer');
    expect(layer).toHaveAttribute('data-layer-id', 'route-line-layer');
  });
});
