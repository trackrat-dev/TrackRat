import { format, parseISO, isToday as fnsIsToday } from 'date-fns';

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
  try {
    const date = parseISO(dateString);
    if (Number.isNaN(date.getTime())) return true; // default to "today" if parsing fails
    return fnsIsToday(date);
  } catch {
    return true;
  }
}

export function formatDate(dateString: string): string {
  try {
    return format(parseISO(dateString), 'MMM d, yyyy');
  } catch {
    return dateString;
  }
}
