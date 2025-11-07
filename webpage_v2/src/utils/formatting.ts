export function formatDelayText(delayMinutes: number): string {
  if (delayMinutes <= 0) return 'On time';
  if (delayMinutes === 1) return '1 min late';
  return `${delayMinutes} mins late`;
}

export function formatStopCount(count: number): string {
  return `${count} ${count === 1 ? 'stop' : 'stops'}`;
}

export function getStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case 'on time':
    case 'scheduled':
      return 'text-success';
    case 'boarding':
      return 'text-accent';
    case 'departed':
      return 'text-blue-400';
    case 'delayed':
      return 'text-warning';
    case 'cancelled':
      return 'text-error';
    case 'arrived':
      return 'text-success';
    default:
      return 'text-white';
  }
}

export function getStatusBadgeClass(status: string): string {
  const baseClass = 'px-2 py-1 rounded-full text-xs font-semibold';
  switch (status.toLowerCase()) {
    case 'on time':
    case 'scheduled':
      return `${baseClass} bg-success/20 text-success`;
    case 'boarding':
      return `${baseClass} bg-accent/20 text-accent`;
    case 'departed':
      return `${baseClass} bg-blue-500/20 text-blue-400`;
    case 'delayed':
      return `${baseClass} bg-warning/20 text-warning`;
    case 'cancelled':
      return `${baseClass} bg-error/20 text-error`;
    case 'arrived':
      return `${baseClass} bg-success/20 text-success`;
    default:
      return `${baseClass} bg-white/10 text-white`;
  }
}
