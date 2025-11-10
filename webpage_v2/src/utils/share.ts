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
    console.error('Share failed:', error);
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
}): ShareData {
  const { trainId, origin, destination, from, to } = params;

  // Build URL with optional from/to params
  const baseUrl = window.location.origin + window.location.pathname.replace(/\/[^/]*$/, '');
  let url = `${baseUrl}/train/${trainId}`;

  const queryParams: string[] = [];
  if (from) queryParams.push(`from=${from}`);
  if (to) queryParams.push(`to=${to}`);
  if (queryParams.length > 0) {
    url += `?${queryParams.join('&')}`;
  }

  return {
    title: `Train ${trainId} - TrackRat`,
    text: `Check out Train ${trainId} from ${origin} to ${destination} on TrackRat`,
    url,
  };
}
