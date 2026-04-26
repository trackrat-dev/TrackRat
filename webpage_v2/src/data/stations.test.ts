import { describe, it, expect } from 'vitest';
import {
  STATIONS,
  getStationByCode,
  searchStations,
  searchStationsPartitioned,
  getGroupedPrimaryStations,
  SYSTEM_ORDER,
  PRIMARY_STATIONS,
} from './stations';

describe('STATIONS', () => {
  it('contains stations sorted alphabetically by name', () => {
    for (let i = 1; i < STATIONS.length; i++) {
      expect(
        STATIONS[i - 1].name.localeCompare(STATIONS[i].name),
      ).toBeLessThanOrEqual(0);
    }
  });

  it('has no more than 5 duplicate station codes', () => {
    const codes = STATIONS.map(s => s.code);
    const dupes = codes.length - new Set(codes).size;
    expect(dupes).toBeLessThanOrEqual(5);
  });

  it('contains more than 1000 stations', () => {
    expect(STATIONS.length).toBeGreaterThan(1000);
  });
});

describe('getStationByCode', () => {
  it('returns NY Penn Station for code "NY"', () => {
    const station = getStationByCode('NY');
    expect(station).toBeDefined();
    expect(station!.name).toContain('Penn');
    expect(station!.code).toBe('NY');
  });

  it('returns undefined for unknown code', () => {
    expect(getStationByCode('ZZZZZ_NONEXISTENT')).toBeUndefined();
  });

  it('returns correct station for each system', () => {
    const cases: [string, string][] = [
      ['NP', 'NJT'],
      ['PHO', 'PATH'],
      ['MANS', 'MNR'],
      ['JAM', 'LIRR'],
      ['CUS', 'METRA'],
    ];
    for (const [code, expectedSystem] of cases) {
      const station = getStationByCode(code);
      expect(station).toBeDefined();
      expect(station!.system).toBe(expectedSystem);
    }
  });
});

describe('searchStations', () => {
  it('returns empty array for empty query', () => {
    expect(searchStations('')).toEqual([]);
    expect(searchStations('   ')).toEqual([]);
  });

  it('finds stations by name substring (case-insensitive)', () => {
    const results = searchStations('penn');
    expect(results.length).toBeGreaterThan(0);
    for (const station of results) {
      const match =
        station.name.toLowerCase().includes('penn') ||
        station.code.toLowerCase().includes('penn');
      expect(match).toBe(true);
    }
  });

  it('finds stations by code', () => {
    const results = searchStations('NY');
    expect(results.length).toBeGreaterThan(0);
    expect(results.some(s => s.code === 'NY')).toBe(true);
  });

  it('limits results to 15 by default', () => {
    const results = searchStations('a');
    expect(results.length).toBeLessThanOrEqual(15);
  });

  it('respects custom limit', () => {
    const results = searchStations('a', undefined, 5);
    expect(results.length).toBeLessThanOrEqual(5);
  });

  it('filters by transit system', () => {
    const results = searchStations('new', ['PATH']);
    for (const station of results) {
      expect(station.system).toBe('PATH');
    }
  });

  it('returns same matches regardless of query case', () => {
    const lower = searchStations('trenton');
    const upper = searchStations('TRENTON');
    const mixed = searchStations('TreNtOn');
    expect(lower.map(s => s.code)).toEqual(upper.map(s => s.code));
    expect(lower.map(s => s.code)).toEqual(mixed.map(s => s.code));
  });

  it('finds stations across multiple systems when no filter', () => {
    const results = searchStations('penn', undefined, 100);
    const systems = new Set(results.map(s => s.system));
    expect(systems.size).toBeGreaterThan(1);
  });
});

describe('searchStationsPartitioned', () => {
  it('returns empty arrays for empty query', () => {
    const { matched, other } = searchStationsPartitioned('', ['NJT']);
    expect(matched).toEqual([]);
    expect(other).toEqual([]);
  });

  it('returns empty arrays when systems is empty', () => {
    const { matched, other } = searchStationsPartitioned('penn', []);
    expect(matched).toEqual([]);
    expect(other).toEqual([]);
  });

  it('partitions results into matched and other systems', () => {
    const { matched, other } = searchStationsPartitioned('new', ['NJT'], 100);
    for (const station of matched) {
      expect(station.system).toBe('NJT');
    }
    for (const station of other) {
      expect(station.system).not.toBe('NJT');
    }
  });

  it('does not duplicate stations between matched and other', () => {
    const { matched, other } = searchStationsPartitioned('penn', ['NJT'], 100);
    const matchedCodes = new Set(matched.map(s => s.code));
    for (const station of other) {
      expect(matchedCodes.has(station.code)).toBe(false);
    }
  });

  it('combined results match unfiltered searchStations', () => {
    const query = 'new';
    const systems: ('NJT' | 'AMTRAK')[] = ['NJT', 'AMTRAK'];
    const { matched, other } = searchStationsPartitioned(query, systems, 100);
    const all = searchStations(query, undefined, 100);
    const partitionedCodes = new Set([...matched, ...other].map(s => s.code));
    for (const station of all) {
      expect(partitionedCodes.has(station.code)).toBe(true);
    }
  });

  it('limits each partition independently', () => {
    const { matched, other } = searchStationsPartitioned('a', ['NJT'], 5);
    expect(matched.length).toBeLessThanOrEqual(5);
    expect(other.length).toBeLessThanOrEqual(5);
  });
});

describe('getGroupedPrimaryStations', () => {
  it('returns groups for all systems when no filter', () => {
    const groups = getGroupedPrimaryStations();
    const systems = groups.map(g => g.system);
    for (const system of SYSTEM_ORDER) {
      if (PRIMARY_STATIONS[system].length > 0) {
        expect(systems).toContain(system);
      }
    }
  });

  it('respects system filter', () => {
    const groups = getGroupedPrimaryStations(['PATH']);
    expect(groups.length).toBe(1);
    expect(groups[0].system).toBe('PATH');
  });

  it('returns only valid Station objects', () => {
    const groups = getGroupedPrimaryStations();
    for (const group of groups) {
      for (const station of group.stations) {
        expect(station.code).toBeTruthy();
        expect(station.name).toBeTruthy();
      }
    }
  });

  it('uses SYSTEM_NAMES for group names', () => {
    const groups = getGroupedPrimaryStations(['NJT']);
    expect(groups[0].name).toBe('NJ Transit');
  });
});
