import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CongestionMap } from './CongestionMap';
import { SegmentCongestion } from '../types';

const navigateMock = vi.fn();

// Mock react-router's navigation so we can assert tap-through targets.
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => navigateMock };
});

// jsdom has no WebGL, so stub MapLibre. The Map stub forwards its onClick with a
// synthetic feature event so the click→navigate wiring is exercised for real.
vi.mock('maplibre-gl', () => ({ default: { Map: vi.fn() } }));

vi.mock('react-map-gl/maplibre', () => ({
  default: ({
    children,
    onClick,
    interactive,
    interactiveLayerIds,
    cursor,
  }: {
    children?: React.ReactNode;
    onClick?: (e: unknown) => void;
    interactive?: boolean;
    interactiveLayerIds?: string[];
    cursor?: string;
  }) => (
    <div
      data-testid="map-container"
      data-interactive={String(interactive)}
      data-interactive-layers={(interactiveLayerIds ?? []).join(',')}
      data-cursor={cursor ?? ''}
      onClick={() =>
        onClick?.({
          target: { setFeatureState: () => {} },
          lngLat: { lng: -74, lat: 40.7 },
          features: [
            {
              id: 1,
              properties: {
                from_station: 'NY',
                to_station: 'NP',
                segment_name: 'New York Penn Station → Newark Penn Station',
                congestion_level: 'moderate',
                average_delay_minutes: 5,
                color: '#D4753E',
              },
            },
          ],
        })
      }
    >
      {children}
    </div>
  ),
  Source: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="map-source">{children}</div>
  ),
  Layer: (props: { id: string }) => <div data-testid="map-layer" data-layer-id={props.id} />,
  Popup: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="map-popup">{children}</div>
  ),
  NavigationControl: () => <div data-testid="nav-control" />,
}));

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

const segments = [
  makeSegment({ from_station: 'NY', to_station: 'NP' }),
  makeSegment({ from_station: 'NP', to_station: 'HB', congestion_level: 'severe' }),
];

describe('CongestionMap', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the visible and hit-target line layers', () => {
    render(<CongestionMap segments={segments} />);
    const layerIds = screen.getAllByTestId('map-layer').map((el) => el.getAttribute('data-layer-id'));
    expect(layerIds).toEqual(['congestion-line-layer', 'congestion-hit-layer']);
  });

  it('routes interaction through the wide hit layer', () => {
    render(<CongestionMap segments={segments} />);
    expect(screen.getByTestId('map-container')).toHaveAttribute(
      'data-interactive-layers',
      'congestion-hit-layer',
    );
  });

  it('renders a legend row for all four congestion levels', () => {
    render(<CongestionMap segments={segments} />);
    expect(screen.getByText('Normal')).toBeInTheDocument();
    expect(screen.getByText('Moderate')).toBeInTheDocument();
    expect(screen.getByText('Heavy')).toBeInTheDocument();
    expect(screen.getByText('Severe')).toBeInTheDocument();
  });

  it('starts collapsed and non-interactive, then expands on click', () => {
    render(<CongestionMap segments={segments} />);
    const container = screen.getByTestId('map-container');
    expect(container).toHaveAttribute('data-interactive', 'false');
    expect(screen.queryByTestId('nav-control')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /expand/i }));
    expect(screen.getByTestId('map-container')).toHaveAttribute('data-interactive', 'true');
    expect(screen.getByTestId('nav-control')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /collapse/i }));
    expect(screen.getByTestId('map-container')).toHaveAttribute('data-interactive', 'false');
  });

  it('navigates to the segment train list when a segment is tapped', () => {
    render(<CongestionMap segments={segments} />);
    fireEvent.click(screen.getByTestId('map-container'));
    expect(navigateMock).toHaveBeenCalledWith('/trains/NY/NP');
  });

  it('renders without crashing when no segment has coordinates', () => {
    const orphan = makeSegment({ from_station: '__NOPE__', to_station: '__ALSO_NOPE__' });
    render(<CongestionMap segments={[orphan]} />);
    // Map still mounts (falls back to the default view); no line features.
    expect(screen.getByTestId('map-container')).toBeInTheDocument();
  });
});
