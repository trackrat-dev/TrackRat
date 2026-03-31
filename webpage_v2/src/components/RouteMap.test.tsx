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

const stationWithCoords = (code: string, name: string, lat: number, lon: number): Station => ({
  code,
  name,
  system: 'NJT',
  coordinates: { lat, lon },
});

const stationWithoutCoords = (code: string, name: string): Station => ({
  code,
  name,
  system: 'NJT',
});

describe('RouteMap', () => {
  const fromStation = stationWithCoords('TR', 'Trenton', 40.2185, -74.7539);
  const toStation = stationWithCoords('NY', 'New York Penn Station', 40.7500, -73.9924);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders map with two markers and a route line when both stations have coordinates', () => {
    render(<RouteMap fromStation={fromStation} toStation={toStation} />);

    expect(screen.getByTestId('map-container')).toBeInTheDocument();
    expect(screen.getByTestId('map-source')).toBeInTheDocument();
    expect(screen.getByTestId('map-layer')).toBeInTheDocument();

    const markers = screen.getAllByTestId('map-marker');
    expect(markers).toHaveLength(2);

    // Verify marker positions
    expect(markers[0]).toHaveAttribute('data-lon', String(fromStation.coordinates!.lon));
    expect(markers[0]).toHaveAttribute('data-lat', String(fromStation.coordinates!.lat));
    expect(markers[1]).toHaveAttribute('data-lon', String(toStation.coordinates!.lon));
    expect(markers[1]).toHaveAttribute('data-lat', String(toStation.coordinates!.lat));
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

  it('uses custom lineColor when provided', () => {
    render(
      <RouteMap fromStation={fromStation} toStation={toStation} lineColor="#003DA5" />,
    );

    // Markers should use the custom color
    const markers = screen.getAllByTestId('map-marker');
    const markerDots = markers.map((m) => m.querySelector('div'));
    markerDots.forEach((dot) => {
      expect(dot).toHaveStyle({ backgroundColor: '#003DA5' });
    });
  });

  it('uses default accent color when no lineColor provided', () => {
    render(<RouteMap fromStation={fromStation} toStation={toStation} />);

    const markers = screen.getAllByTestId('map-marker');
    const markerDots = markers.map((m) => m.querySelector('div'));
    markerDots.forEach((dot) => {
      expect(dot).toHaveStyle({ backgroundColor: '#CC5500' });
    });
  });

  it('renders route line layer with correct id', () => {
    render(<RouteMap fromStation={fromStation} toStation={toStation} />);

    const layer = screen.getByTestId('map-layer');
    expect(layer).toHaveAttribute('data-layer-id', 'route-line-layer');
  });
});
