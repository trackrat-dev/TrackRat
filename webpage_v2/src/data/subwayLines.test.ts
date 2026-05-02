import { describe, it, expect } from 'vitest';
import {
  displayBullet,
  sortBullets,
  contrastingTextColor,
  linesForStationCode,
  transferLinesForStationCode,
  SUBWAY_LINE_COLORS,
} from './subwayLines';

describe('displayBullet', () => {
  it('normalizes express variants by stripping X suffix', () => {
    expect(displayBullet('7X')).toBe('7');
    expect(displayBullet('6X')).toBe('6');
    expect(displayBullet('FX')).toBe('F');
  });

  it('normalizes all shuttle variants to S', () => {
    expect(displayBullet('FS')).toBe('S');
    expect(displayBullet('GS')).toBe('S');
    expect(displayBullet('H')).toBe('S');
  });

  it('preserves SI as-is', () => {
    expect(displayBullet('SI')).toBe('SI');
  });

  it('uppercases single-letter lines', () => {
    expect(displayBullet('A')).toBe('A');
    expect(displayBullet('1')).toBe('1');
  });

  it('handles lowercase inputs correctly', () => {
    expect(displayBullet('fs')).toBe('S');
    expect(displayBullet('gs')).toBe('S');
    expect(displayBullet('h')).toBe('S');
    expect(displayBullet('7x')).toBe('7');
    expect(displayBullet('si')).toBe('SI');
    expect(displayBullet('a')).toBe('A');
  });
});

describe('sortBullets', () => {
  it('sorts numerals before letters before S before SI', () => {
    const result = sortBullets(['SI', 'S', 'A', '7', '1', 'N']);
    expect(result).toEqual(['1', '7', 'A', 'N', 'S', 'SI']);
  });

  it('sorts numerals in numeric order', () => {
    expect(sortBullets(['7', '4', '1', '2'])).toEqual(['1', '2', '4', '7']);
  });

  it('sorts letters alphabetically', () => {
    expect(sortBullets(['N', 'A', 'C', 'E'])).toEqual(['A', 'C', 'E', 'N']);
  });

  it('returns empty array for empty input', () => {
    expect(sortBullets([])).toEqual([]);
  });
});

describe('contrastingTextColor', () => {
  it('returns black for bright yellow (N/Q/R/W)', () => {
    expect(contrastingTextColor('#FCCC0A')).toBe('black');
  });

  it('returns black for green (G)', () => {
    expect(contrastingTextColor('#6CBE45')).toBe('black');
  });

  it('returns black for gray (L)', () => {
    expect(contrastingTextColor('#A7A9AC')).toBe('black');
  });

  it('returns white for dark blue (A/C/E)', () => {
    expect(contrastingTextColor('#0039A6')).toBe('white');
  });

  it('returns white for red (1/2/3)', () => {
    expect(contrastingTextColor('#EE352E')).toBe('white');
  });

  it('returns white for dark green (4/5/6)', () => {
    expect(contrastingTextColor('#00933C')).toBe('white');
  });
});

describe('linesForStationCode', () => {
  it('returns lines for a simple single-route station', () => {
    const lines = linesForStationCode('SL29');
    expect(lines).toEqual(['L']);
  });

  it('returns empty array for non-subway station code', () => {
    expect(linesForStationCode('TR')).toEqual([]);
    expect(linesForStationCode('NONEXISTENT')).toEqual([]);
  });

  it('includes manual additions for SQ01 (Canal St BMT Broadway)', () => {
    const lines = linesForStationCode('SQ01');
    expect(lines).toContain('N');
    expect(lines).toContain('Q');
  });

  it('returns union of lines for station complex members', () => {
    // S128 and SA28 are in the same complex (34 St-Penn Station)
    // S128 is on 1/2/3, SA28 is on A/C/E
    const linesS128 = linesForStationCode('S128');
    const linesSA28 = linesForStationCode('SA28');
    expect(linesS128).toEqual(linesSA28);
    expect(linesS128).toContain('1');
    expect(linesS128).toContain('A');
  });

  it('returns union across full Times Square complex', () => {
    // Times Sq complex: S127, S725, SA27, SR16, S902
    const linesS127 = linesForStationCode('S127');
    const linesSR16 = linesForStationCode('SR16');
    expect(linesS127).toEqual(linesSR16);
    expect(linesS127).toContain('1');
    expect(linesS127).toContain('7');
    expect(linesS127).toContain('N');
    expect(linesS127).toContain('S');
  });

  it('returns sorted bullets', () => {
    const lines = linesForStationCode('S127');
    for (let i = 1; i < lines.length; i++) {
      const prevIsNum = /^\d$/.test(lines[i - 1]);
      const currIsNum = /^\d$/.test(lines[i]);
      if (prevIsNum && currIsNum) {
        expect(parseInt(lines[i - 1])).toBeLessThanOrEqual(parseInt(lines[i]));
      }
    }
  });

  it('includes all lines for 125 St complex', () => {
    // S116, S225, S621, SA15
    const lines = linesForStationCode('S116');
    expect(lines).toContain('1');
    expect(lines).toContain('2');
    expect(lines).toContain('A');
    expect(lines).toContain('4');
  });

  it('returns union across Chambers St-WTC / Fulton / Oculus complex', () => {
    // S228 (Chambers St-WTC, 2/3), S138 (WTC Cortlandt, 1),
    // SA36 (Chambers St, A/C/E via shared platform), SE01 (World Trade Center, E),
    // SR25 (Cortlandt St, N/R/W), PWC (PATH WTC).
    const codes = ['S228', 'S138', 'SA36', 'SE01', 'SR25', 'PWC'];
    const lineSets = codes.map(c => linesForStationCode(c));
    for (let i = 1; i < lineSets.length; i++) {
      expect(lineSets[i]).toEqual(lineSets[0]);
    }
    expect(lineSets[0]).toContain('1');
    expect(lineSets[0]).toContain('2');
    expect(lineSets[0]).toContain('3');
    expect(lineSets[0]).toContain('A');
    expect(lineSets[0]).toContain('E');
    expect(lineSets[0]).toContain('N');
  });

  it('returns union across Livonia Av (L) / Junius St (3) complex', () => {
    const linesS254 = linesForStationCode('S254');
    const linesSL26 = linesForStationCode('SL26');
    expect(linesS254).toEqual(linesSL26);
    expect(linesS254).toContain('3');
    expect(linesS254).toContain('L');
  });

  it('returns union across Penn Station / 34 St-Penn complex', () => {
    // S128 (1/2/3), SA28 (A/C/E), NY (NJT/Amtrak/LIRR Penn Station).
    const codes = ['S128', 'SA28', 'NY'];
    const lineSets = codes.map(c => linesForStationCode(c));
    for (let i = 1; i < lineSets.length; i++) {
      expect(lineSets[i]).toEqual(lineSets[0]);
    }
    expect(lineSets[0]).toContain('1');
    expect(lineSets[0]).toContain('A');
  });

  it('returns union across Grand Central / Grand Central-42 St complex', () => {
    // S631 (4/5/6), S723 (7), S901 (GS shuttle), GCT (MNR/LIRR Grand Central).
    const codes = ['S631', 'S723', 'S901', 'GCT'];
    const lineSets = codes.map(c => linesForStationCode(c));
    for (let i = 1; i < lineSets.length; i++) {
      expect(lineSets[i]).toEqual(lineSets[0]);
    }
    expect(lineSets[0]).toContain('4');
    expect(lineSets[0]).toContain('7');
    expect(lineSets[0]).toContain('S');
  });
});

describe('transferLinesForStationCode', () => {
  it('excludes the current line from results', () => {
    const transfers = transferLinesForStationCode('S127', '1');
    expect(transfers).not.toContain('1');
    expect(transfers).toContain('7');
    expect(transfers).toContain('N');
  });

  it('normalizes express line codes before excluding', () => {
    const transfers = transferLinesForStationCode('S127', '7X');
    expect(transfers).not.toContain('7');
    expect(transfers).toContain('1');
  });

  it('returns empty array when station only has the current line', () => {
    const transfers = transferLinesForStationCode('SL29', 'L');
    expect(transfers).toEqual([]);
  });
});

describe('SUBWAY_LINE_COLORS', () => {
  it('has colors for all standard lines', () => {
    const expectedLines = ['1', '2', '3', '4', '5', '6', '7', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'J', 'L', 'M', 'N', 'Q', 'R', 'S', 'SI', 'W', 'Z'];
    for (const line of expectedLines) {
      expect(SUBWAY_LINE_COLORS[line], `Missing color for line ${line}`).toBeDefined();
      expect(SUBWAY_LINE_COLORS[line]).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
  });

  it('groups lines by correct color families', () => {
    expect(SUBWAY_LINE_COLORS['1']).toBe(SUBWAY_LINE_COLORS['2']);
    expect(SUBWAY_LINE_COLORS['2']).toBe(SUBWAY_LINE_COLORS['3']);
    expect(SUBWAY_LINE_COLORS['A']).toBe(SUBWAY_LINE_COLORS['C']);
    expect(SUBWAY_LINE_COLORS['C']).toBe(SUBWAY_LINE_COLORS['E']);
    expect(SUBWAY_LINE_COLORS['N']).toBe(SUBWAY_LINE_COLORS['Q']);
    expect(SUBWAY_LINE_COLORS['Q']).toBe(SUBWAY_LINE_COLORS['R']);
    expect(SUBWAY_LINE_COLORS['R']).toBe(SUBWAY_LINE_COLORS['W']);
  });
});
