import { ROUTES } from './routeTopology';

export const SUBWAY_LINE_COLORS: Record<string, string> = {
  '1': '#EE352E', '2': '#EE352E', '3': '#EE352E',
  '4': '#00933C', '5': '#00933C', '6': '#00933C',
  '7': '#B933AD',
  'A': '#0039A6', 'C': '#0039A6', 'E': '#0039A6',
  'B': '#FF6319', 'D': '#FF6319', 'F': '#FF6319', 'M': '#FF6319',
  'G': '#6CBE45',
  'J': '#996633', 'Z': '#996633',
  'L': '#A7A9AC',
  'N': '#FCCC0A', 'Q': '#FCCC0A', 'R': '#FCCC0A', 'W': '#FCCC0A',
  'S': '#808183',
  'SI': '#1D2E86',
};

const MANUAL_LINE_ADDITIONS: Record<string, string[]> = {
  'SQ01': ['N'],
};

const STATION_COMPLEXES: string[][] = [
  ['S109', 'SA03'],
  ['S111', 'SA06'],
  ['S112', 'SA09'],
  ['S114', 'S302', 'SA12', 'SD13'],
  ['S116', 'S225', 'S621', 'SA15'],
  ['S118', 'SA17'],
  ['S119', 'SA18'],
  ['S120', 'SA19'],
  ['S125', 'SA24'],
  ['S126', 'SA25'],
  ['S128', 'SA28'],
  ['S127', 'S725', 'SA27', 'SR16', 'S902'],
  ['S132', 'SD19', 'SL02'],
  ['S135', 'S639', 'SA34', 'SM20', 'SQ01', 'SR23'],
  ['S208', 'S503'],
  ['S211', 'S504'],
  ['S222', 'S415'],
  ['S229', 'S418', 'SA38', 'SM22'],
  ['S232', 'S423', 'SR28'],
  ['S235', 'SD24', 'SR31'],
  ['S239', 'SS04'],
  ['S414', 'SD11'],
  ['S629', 'SB08', 'SR11'],
  ['S630', 'SF11'],
  ['S631', 'S723', 'S901'],
  ['S635', 'SL03', 'SR20'],
  ['S637', 'SD21'],
  ['S640', 'SM21'],
  ['S710', 'SG14'],
  ['S718', 'SR09'],
  ['S719', 'SF09', 'SG22'],
  ['S724', 'SD16'],
  ['SA11', 'SD12'],
  ['SA31', 'SL01'],
  ['SA32', 'SD20'],
  ['SA41', 'SR29'],
  ['SA45', 'SS01'],
  ['SA51', 'SJ27', 'SL22'],
  ['SB16', 'SN04'],
  ['SD17', 'SR17'],
  ['SD25', 'SF24'],
  ['SF15', 'SM18'],
  ['SF23', 'SR33'],
  ['SG29', 'SL10'],
  ['SL17', 'SM08'],
];

export function displayBullet(lineCode: string): string {
  const code = lineCode.toUpperCase();
  if (code === 'FS' || code === 'GS' || code === 'H') return 'S';
  if (code === 'SI') return 'SI';
  if (code.length === 2 && code[1] === 'X') return code[0];
  return code;
}

function bulletSortRank(bullet: string): number {
  if (bullet === 'SI') return 3;
  if (bullet === 'S') return 2;
  if (/^\d$/.test(bullet)) return 0;
  return 1;
}

export function sortBullets(bullets: string[]): string[] {
  return [...bullets].sort((a, b) => {
    const ra = bulletSortRank(a);
    const rb = bulletSortRank(b);
    if (ra !== rb) return ra - rb;
    if (ra === 0) return parseInt(a) - parseInt(b);
    return a.localeCompare(b);
  });
}

export function contrastingTextColor(hex: string): 'black' | 'white' {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  const brightness = (r * 299 + g * 587 + b * 114) / 1000;
  return brightness > 150 ? 'black' : 'white';
}

const complexLookup: Map<string, string[]> = new Map();
for (const group of STATION_COMPLEXES) {
  for (const code of group) {
    complexLookup.set(code, group);
  }
}

function buildLinesByCode(): Map<string, string[]> {
  const raw = new Map<string, Set<string>>();
  const subwayRoutes = ROUTES.filter(r => r.dataSource === 'SUBWAY');

  for (const route of subwayRoutes) {
    const bullet = displayBullet(route.lineCodes[0]);
    for (const station of route.stations) {
      let set = raw.get(station);
      if (!set) {
        set = new Set();
        raw.set(station, set);
      }
      set.add(bullet);
    }
  }

  for (const [code, additions] of Object.entries(MANUAL_LINE_ADDITIONS)) {
    let set = raw.get(code);
    if (!set) {
      set = new Set();
      raw.set(code, set);
    }
    for (const line of additions) {
      set.add(line);
    }
  }

  for (const group of STATION_COMPLEXES) {
    const union = new Set<string>();
    for (const code of group) {
      const set = raw.get(code);
      if (set) {
        for (const line of set) union.add(line);
      }
    }
    for (const code of group) {
      raw.set(code, union);
    }
  }

  const result = new Map<string, string[]>();
  for (const [code, set] of raw) {
    result.set(code, sortBullets([...set]));
  }
  return result;
}

const linesByCode = buildLinesByCode();

export function linesForStationCode(code: string): string[] {
  return linesByCode.get(code) ?? [];
}

export function transferLinesForStationCode(code: string, currentLine: string): string[] {
  const all = linesForStationCode(code);
  const currentBullet = displayBullet(currentLine);
  return all.filter(b => b !== currentBullet);
}
