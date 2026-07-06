import { differenceInMinutes, format, parseISO } from 'date-fns';

export function formatTime(dateString: string): string {
  try {
    const date = parseISO(dateString);
    return format(date, 'h:mm a');
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
    const result = Math.round(diffMs / 60000);
    return Number.isNaN(result) ? 0 : result;
  } catch {
    return 0;
  }
}

export function getTodayDateString(): string {
  const today = new Date();
  return format(today, 'yyyy-MM-dd');
}

export function isToday(dateString: string): boolean {
  const bare = dateString.slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(bare)) return true;
  return bare === getTodayDateString();
}

/**
 * Human-readable countdown to a departure/arrival.
 * Returns `null` when the time is in the past or more than 90 minutes away,
 * `'now'` when it is 0-1 minutes out, and `'in N min'` otherwise.
 */
export function formatRelativeMinutes(dateString: string, now: Date = new Date()): string | null {
  try {
    const minutes = differenceInMinutes(parseISO(dateString), now);
    if (Number.isNaN(minutes) || minutes < 0 || minutes > 90) return null;
    if (minutes <= 1) return 'now';
    return `in ${minutes} min`;
  } catch {
    return null;
  }
}

export function formatDate(dateString: string): string {
  try {
    return format(parseISO(dateString), 'MMM d, yyyy');
  } catch {
    return dateString;
  }
}
