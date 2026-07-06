import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

/**
 * Returns a Back handler that unifies detail-page navigation:
 *
 * - When there is earlier in-app history it pops it (`navigate(-1)`), so Back
 *   returns the user to wherever they actually came from (History, Favorites,
 *   a train list, …) rather than a hard-coded page.
 * - On a cold deep-link (shared URL, new tab) there is nothing to pop, so it
 *   replaces the current entry with a same-origin `fallbackPath`. This keeps
 *   Back inside the app instead of firing a bare `history.back()` that would
 *   exit to the previous site (or do nothing).
 *
 * "In-app history" is detected via the numeric `idx` React Router v7 keeps on
 * `window.history.state`: it is 0 on a fresh page load and incremented on every
 * push, so `idx > 0` means at least one prior in-app entry exists.
 */
export function useBackNavigation(fallbackPath: string): () => void {
  const navigate = useNavigate();

  return useCallback(() => {
    const historyIndex = (window.history.state as { idx?: number } | null)?.idx;
    if (typeof historyIndex === 'number' && historyIndex > 0) {
      navigate(-1);
    } else {
      navigate(fallbackPath, { replace: true });
    }
  }, [navigate, fallbackPath]);
}
