import { SUBWAY_LINE_COLORS, contrastingTextColor, linesForStationCode, transferLinesForStationCode } from '../data/subwayLines';

interface SubwayLineChipsProps {
  stationCode: string;
  excludeLine?: string;
  size?: number;
}

export function SubwayLineChips({ stationCode, excludeLine, size = 16 }: SubwayLineChipsProps) {
  const lines = excludeLine
    ? transferLinesForStationCode(stationCode, excludeLine)
    : linesForStationCode(stationCode);

  if (lines.length === 0) return null;

  return (
    <span className="inline-flex items-center gap-[3px]">
      {lines.map(line => {
        const bg = SUBWAY_LINE_COLORS[line] ?? '#808183';
        const fg = contrastingTextColor(bg);
        return (
          <span
            key={line}
            className="inline-flex items-center justify-center rounded-full font-bold shrink-0"
            style={{
              width: size,
              height: size,
              backgroundColor: bg,
              color: fg,
              fontSize: size * 0.62,
              lineHeight: 1,
            }}
          >
            {line}
          </span>
        );
      })}
    </span>
  );
}
