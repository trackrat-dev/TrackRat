import { describe, it, expect } from 'vitest';
import { getIntermediateStations } from './routeTopology';

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
