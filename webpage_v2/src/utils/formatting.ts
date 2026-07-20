export function formatDelayText(delayMinutes: number): string {
  if (delayMinutes <= 0) return 'On time';
  if (delayMinutes === 1) return '1 min late';
  return `${delayMinutes} mins late`;
}

/**
 * Pill label for a train that departs on time but arrives late (issue
 * #1527) — distinguishes an en-route slip from a delayed departure.
 * Callers gate on delayMinutes > 0; at 0 this would read "Arrives On time".
 */
export function formatArrivalDelayText(delayMinutes: number): string {
  return `Arrives ${formatDelayText(delayMinutes)}`;
}

export function getStatusBadgeClass(status: string): string {
  const baseClass = 'px-2 py-1 rounded-full text-xs font-semibold';
  switch (status.toLowerCase()) {
    case 'on time':
      return `${baseClass} bg-success/20 text-success`;
    case 'boarding':
      return `${baseClass} bg-accent/20 text-accent`;
    case 'departed':
      return `${baseClass} bg-info/15 text-info`;
    case 'delayed':
      return `${baseClass} bg-warning/20 text-warning`;
    case 'cancelled':
      return `${baseClass} bg-error/20 text-error`;
    case 'arrived':
      return `${baseClass} bg-success/20 text-success`;
    default:
      return `${baseClass} bg-text-muted/15 text-text-secondary`;
  }
}
