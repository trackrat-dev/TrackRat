import { describe, it, expect } from 'vitest';
import { getIntermediateStations, getRouteById, getRoutesForSystem, ROUTES } from './routeTopology';

describe('getIntermediateStations', () => {
  it('returns intermediate NEC stations between Trenton and NY Penn', () => {
    const intermediates = getIntermediateStations('TR', 'NY', 'NJT');
    // TR → NY on NEC should include key stations in order
    expect(intermediates.length).toBeGreaterThan(0);
    expect(intermediates).toContain('PJ'); // Princeton Junction
    expect(intermediates).toContain('NB'); // New Brunswick
    expect(intermediates).toContain('NP'); // Newark Penn
    expect(intermediates).toContain('SE'); // Secaucus

    // Verify order: HL before PJ before NB before NP before SE
    const hlIdx = intermediates.indexOf('HL');
    const pjIdx = intermediates.indexOf('PJ');
    const nbIdx = intermediates.indexOf('NB');
    const npIdx = intermediates.indexOf('NP');
    const seIdx = intermediates.indexOf('SE');
    expect(hlIdx).toBeLessThan(pjIdx);
    expect(pjIdx).toBeLessThan(nbIdx);
    expect(nbIdx).toBeLessThan(npIdx);
    expect(npIdx).toBeLessThan(seIdx);
  });

  it('returns stations in reverse order when going NY to TR', () => {
    const intermediates = getIntermediateStations('NY', 'TR', 'NJT');
    expect(intermediates.length).toBeGreaterThan(0);

    // Order should be reversed: SE before NP before NB before PJ before HL
    const seIdx = intermediates.indexOf('SE');
    const npIdx = intermediates.indexOf('NP');
    const nbIdx = intermediates.indexOf('NB');
    const pjIdx = intermediates.indexOf('PJ');
    const hlIdx = intermediates.indexOf('HL');
    expect(seIdx).toBeLessThan(npIdx);
    expect(npIdx).toBeLessThan(nbIdx);
    expect(nbIdx).toBeLessThan(pjIdx);
    expect(pjIdx).toBeLessThan(hlIdx);
  });

  it('returns empty array for adjacent stations', () => {
    const intermediates = getIntermediateStations('PJ', 'HL', 'NJT');
    expect(intermediates).toEqual([]);
  });

  it('returns empty array for stations not on the same route', () => {
    const intermediates = getIntermediateStations('TR', 'BART_EMBR', 'NJT');
    expect(intermediates).toEqual([]);
  });

  it('returns empty array for unknown station codes', () => {
    const intermediates = getIntermediateStations('ZZZZZ', 'YYYYY');
    expect(intermediates).toEqual([]);
  });

  it('works for PATH system', () => {
    const intermediates = getIntermediateStations('PNP', 'P33', 'PATH');
    expect(intermediates.length).toBeGreaterThan(0);
  });

  it('works without specifying dataSource', () => {
    // Should still find NEC route without explicit system
    const intermediates = getIntermediateStations('TR', 'NY');
    expect(intermediates.length).toBeGreaterThan(0);
    expect(intermediates).toContain('PJ');
  });

  it('returns intermediates for LIRR Babylon line', () => {
    // Jamaica to Babylon (BTA) on LIRR
    const intermediates = getIntermediateStations('JAM', 'BTA', 'LIRR');
    expect(intermediates.length).toBeGreaterThan(0);
  });
});

describe('getRouteById', () => {
  it('returns the route with the matching id', () => {
    const route = getRouteById('njt-nec');
    expect(route).toBeDefined();
    expect(route!.name).toBe('Northeast Corridor');
    expect(route!.dataSource).toBe('NJT');
    expect(route!.stations[0]).toBe('NY');
    expect(route!.stations[route!.stations.length - 1]).toBe('TR');
  });

  it('returns undefined for an unknown id', () => {
    expect(getRouteById('does-not-exist')).toBeUndefined();
  });
});

describe('getRoutesForSystem', () => {
  it('returns only routes for the requested system', () => {
    const njt = getRoutesForSystem('NJT');
    expect(njt.length).toBeGreaterThan(0);
    expect(njt.every((r) => r.dataSource === 'NJT')).toBe(true);
  });

  it('preserves ROUTES definition order', () => {
    const path = getRoutesForSystem('PATH');
    const inOrder = ROUTES.filter((r) => r.dataSource === 'PATH');
    expect(path).toEqual(inOrder);
  });

  it('returns an empty array for an unrecognized system', () => {
    expect(getRoutesForSystem('NOPE' as never)).toEqual([]);
  });
});

describe('Port Jervis Line ordering (issue #1660)', () => {
  // The reporter saw no line drawn between Harriman and Salisbury Mills-Cornwall.
  // RouteMap draws the base network only between *consecutive* stations, so with
  // Middletown wedged between them the real RM→CW leg was never drawn at all —
  // the map instead ran two long straight lines out to Middletown and back.
  const portJervis = () => getRouteById('njt-port-jervis')!;

  it('lists stations in published timetable order', () => {
    expect(portJervis().stations).toEqual([
      'SF', 'XG', 'TC', 'RM', 'CW', 'CB', 'MD', 'OS', 'PO',
    ]);
  });

  it('makes Harriman and Salisbury Mills-Cornwall adjacent', () => {
    const { stations } = portJervis();
    expect(stations.indexOf('CW') - stations.indexOf('RM')).toBe(1);
  });

  it('places Middletown between Campbell Hall and Otisville', () => {
    const { stations } = portJervis();
    const md = stations.indexOf('MD');
    expect(stations[md - 1]).toBe('CB');
    expect(stations[md + 1]).toBe('OS');
  });

  it('returns no intermediates between Harriman and Salisbury Mills-Cornwall', () => {
    // Under the broken order this returned ['MD'], which is how a real
    // adjacency became two fabricated segments.
    expect(getIntermediateStations('RM', 'CW', 'NJT')).toEqual([]);
  });

  it('does not zig-zag geographically', () => {
    // The general form of the bug: swapping any two adjacent stations must not
    // shorten the line. Under the old order, swapping MD and CW shortened it by
    // 8.4 miles. Scoped to this route deliberately — real lines elsewhere
    // (Amtrak detours, LIRR branches) legitimately backtrack.
    const { stations } = portJervis();
    const coords: Record<string, [number, number]> = {
      SF: [41.11354, -74.153442], XG: [41.157138, -74.191307],
      TC: [41.194208, -74.18446], RM: [41.293354, -74.13987],
      CW: [41.437073, -74.101871], CB: [41.450917, -74.266554],
      MD: [41.4459, -74.4222], OS: [41.471784, -74.529212],
      PO: [41.374899, -74.694622],
    };
    const miles = (a: string, b: string) => {
      const toRad = (d: number) => (d * Math.PI) / 180;
      const [la1, lo1] = coords[a].map(toRad);
      const [la2, lo2] = coords[b].map(toRad);
      return 3958.8 * 2 * Math.asin(Math.sqrt(
        Math.sin((la2 - la1) / 2) ** 2 +
        Math.cos(la1) * Math.cos(la2) * Math.sin((lo2 - lo1) / 2) ** 2));
    };
    const length = (seq: string[]) =>
      seq.slice(0, -1).reduce((sum, s, i) => sum + miles(s, seq[i + 1]), 0);

    const baseline = length(stations);
    for (let i = 0; i < stations.length - 1; i++) {
      const swapped = [...stations];
      [swapped[i], swapped[i + 1]] = [swapped[i + 1], swapped[i]];
      expect(
        length(swapped),
        `swapping ${stations[i]} and ${stations[i + 1]} shortens the line`,
      ).toBeGreaterThanOrEqual(baseline - 0.5);
    }
  });
});
