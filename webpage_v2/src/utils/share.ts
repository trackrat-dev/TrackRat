import { buildTrainUrl } from './routes';

/**
 * Share utilities using Web Share API with clipboard fallback
 */

export interface ShareData {
  title: string;
  text: string;
  url: string;
}

/**
 * Check if Web Share API is supported
 */
export function isShareSupported(): boolean {
  return typeof navigator !== 'undefined' && 'share' in navigator;
}

/**
 * Share content using Web Share API or fallback to clipboard
 * Returns true if share was successful, false otherwise
 */
export async function share(data: ShareData): Promise<boolean> {
  try {
    if (isShareSupported()) {
      await navigator.share({
        title: data.title,
        text: data.text,
        url: data.url,
      });
      return true;
    } else {
      // Fallback: copy URL to clipboard
      await copyToClipboard(data.url);
      return true;
    }
  } catch (error) {
    // User cancelled share or clipboard failed
    if (error instanceof Error && error.name === 'AbortError') {
      // User cancelled, not an error
      return false;
    }
    return false;
  }
}

/**
 * Copy text to clipboard
 */
async function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    await navigator.clipboard.writeText(text);
  } else {
    // Fallback for older browsers
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
  }
}

/**
 * Build share data for a train
 */
export function buildTrainShareData(params: {
  trainId: string;
  origin: string;
  destination: string;
  from?: string;
  to?: string;
  journeyDate?: string;
  dataSource?: string;
}): ShareData {
  const { trainId, origin, destination, from, to, journeyDate, dataSource } = params;
  const basePath = import.meta.env.BASE_URL || '/';
  const normalizedBasePath = basePath === '/' ? '' : basePath.replace(/\/$/, '');
  const routeUrl = buildTrainUrl({
    trainId,
    from,
    to,
    date: journeyDate,
    dataSource,
  });
  const url = new URL(`${normalizedBasePath}${routeUrl}`, window.location.origin);

  // Keep from/to in the query string for shared links so route context survives
  // even when the canonical path already encodes both stations.
  if (from) url.searchParams.set('from', from);
  if (to) url.searchParams.set('to', to);

  return {
    title: `Train ${trainId} - TrackRat`,
    text: `Check out Train ${trainId} from ${origin} to ${destination} on TrackRat`,
    url: url.toString(),
  };
}
