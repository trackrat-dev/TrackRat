import { getStatusBadgeClass } from '../utils/formatting';

/**
 * Default human-readable label for each known status. Callers may override via
 * the `label` prop (e.g. TrainCard shows "5 mins late" instead of "Delayed").
 */
const STATUS_LABELS: Record<string, string> = {
  'on time': 'On time',
  boarding: 'Boarding',
  departed: 'Departed',
  delayed: 'Delayed',
  cancelled: 'Cancelled',
  arrived: 'Arrived',
};

interface StatusBadgeProps {
  /** Semantic status; drives both color (via getStatusBadgeClass) and default label. */
  status: string;
  /** Optional label override for dynamic text (e.g. delay minutes). */
  label?: string;
}

/**
 * Single source of truth for status pill rendering across the app. Wraps
 * getStatusBadgeClass plus the status→label mapping so every call site
 * (TrainCard, TrainDetailsPage, TripDetailsPage, TransferTripCard) renders an
 * identically shaped `rounded-full px-2 py-1 text-xs font-semibold` chip.
 */
export function StatusBadge({ status, label }: StatusBadgeProps) {
  const text = label ?? STATUS_LABELS[status.toLowerCase()] ?? status;
  return <span className={getStatusBadgeClass(status)}>{text}</span>;
}
