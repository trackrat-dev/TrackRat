/**
 * Shared inline SVG icon set.
 *
 * The app deliberately hand-rolls its icons instead of pulling in an icon
 * library (see webpage_v2/CLAUDE.md: "No Component Libraries"). Keeping every
 * icon here ensures one consistent visual language: 24×24 viewBox, 20px default
 * render size, `stroke="currentColor"` at strokeWidth 2 so icons inherit text
 * color. StarIcon is the one filled exception.
 */

interface IconProps {
  className?: string;
  size?: number;
}

/** Base props shared by every stroke-style icon. */
function strokeProps({ className, size = 20 }: IconProps) {
  return {
    className,
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  };
}

export function DeparturesIcon(props: IconProps) {
  return (
    <svg {...strokeProps(props)}>
      <rect x="4" y="3" width="16" height="16" rx="2" />
      <path d="M4 11h16" />
      <path d="M12 3v8" />
      <circle cx="8" cy="21" r="1" />
      <circle cx="16" cy="21" r="1" />
      <path d="M8 19V11" />
      <path d="M16 19V11" />
    </svg>
  );
}

export function StatusIcon(props: IconProps) {
  return (
    <svg {...strokeProps(props)}>
      <path d="M3 3v18h18" />
      <path d="M7 16l4-8 4 4 4-6" />
    </svg>
  );
}

export function StarIcon({ className, size = 20 }: IconProps) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      stroke="currentColor"
      strokeWidth={1}
    >
      <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
    </svg>
  );
}

export function HistoryIcon(props: IconProps) {
  return (
    <svg {...strokeProps(props)}>
      <path d="M3 12a9 9 0 1 0 3-6.7" />
      <path d="M3 4v5h5" />
      <path d="M12 7v5l3 3" />
    </svg>
  );
}

export function RefreshIcon(props: IconProps) {
  return (
    <svg {...strokeProps(props)}>
      <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
      <path d="M3 21v-5h5" />
    </svg>
  );
}

const CHEVRON_ROTATION: Record<'up' | 'down' | 'left' | 'right', number> = {
  up: 180,
  down: 0,
  left: 90,
  right: -90,
};

export function ChevronIcon({
  direction = 'down',
  ...props
}: IconProps & { direction?: 'up' | 'down' | 'left' | 'right' }) {
  return (
    <svg
      {...strokeProps(props)}
      style={{ transform: `rotate(${CHEVRON_ROTATION[direction]}deg)` }}
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

/** Real-time service alert (exclamation in a circle). */
export function AlertIcon(props: IconProps) {
  return (
    <svg {...strokeProps(props)}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v4" />
      <path d="M12 16h.01" />
    </svg>
  );
}

/** Elevator/escalator outage (cab with up/down direction). */
export function ElevatorIcon(props: IconProps) {
  return (
    <svg {...strokeProps(props)}>
      <rect x="4" y="3" width="16" height="18" rx="2" />
      <path d="M8 11l1.5-2 1.5 2" />
      <path d="M13 13l1.5 2 1.5-2" />
    </svg>
  );
}

/** Planned work / generic warning (exclamation in a triangle). */
export function WarningIcon(props: IconProps) {
  return (
    <svg {...strokeProps(props)}>
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </svg>
  );
}
