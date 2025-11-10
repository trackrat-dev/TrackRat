import { format, formatDistance, parseISO } from 'date-fns';

export function formatTime(dateString: string): string {
  try {
    const date = parseISO(dateString);
    return format(date, 'h:mm a');
  } catch {
    return 'N/A';
  }
}

export function formatDateTime(dateString: string): string {
  try {
    const date = parseISO(dateString);
    return format(date, 'MMM d, h:mm a');
  } catch {
    return 'N/A';
  }
}

export function formatTimeAgo(dateString: string): string {
  try {
    const date = parseISO(dateString);
    return formatDistance(date, new Date(), { addSuffix: true });
  } catch {
    return 'N/A';
  }
}

export function getDelayMinutes(scheduled?: string, actual?: string): number {
  if (!scheduled || !actual) return 0;
  try {
    const scheduledDate = parseISO(scheduled);
    const actualDate = parseISO(actual);
    const diffMs = actualDate.getTime() - scheduledDate.getTime();
    return Math.round(diffMs / 60000);
  } catch {
    return 0;
  }
}

export function getTodayDateString(): string {
  const today = new Date();
  return format(today, 'yyyy-MM-dd');
}
