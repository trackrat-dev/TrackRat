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
