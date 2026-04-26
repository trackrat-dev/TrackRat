import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { StationPicker } from './StationPicker';

describe('StationPicker', () => {
  let onSelect: ReturnType<typeof vi.fn>;
  let onClose: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onSelect = vi.fn();
    onClose = vi.fn();
  });

  afterEach(() => {
    document.body.style.overflow = '';
  });

  function renderPicker(title = 'Select Station') {
    return render(
      <StationPicker title={title} onSelect={onSelect} onClose={onClose} />
    );
  }

  describe('dialog semantics', () => {
    it('renders with role="dialog" and aria-modal="true"', () => {
      renderPicker();
      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
      expect(dialog).toHaveAttribute('aria-modal', 'true');
    });

    it('has aria-labelledby pointing to the title', () => {
      renderPicker('Pick a Station');
      const dialog = screen.getByRole('dialog');
      const titleId = dialog.getAttribute('aria-labelledby');
      expect(titleId).toBe('stationpicker-title');
      const heading = document.getElementById(titleId!);
      expect(heading).toHaveTextContent('Pick a Station');
    });

    it('close button has aria-label', () => {
      renderPicker();
      const closeBtn = screen.getByRole('button', { name: 'Close' });
      expect(closeBtn).toBeInTheDocument();
    });
  });

  describe('Escape-to-close', () => {
    it('calls onClose when Escape is pressed', () => {
      renderPicker();
      const dialog = screen.getByRole('dialog');
      fireEvent.keyDown(dialog, { key: 'Escape' });
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('does not call onClose for other keys', () => {
      renderPicker();
      const dialog = screen.getByRole('dialog');
      fireEvent.keyDown(dialog, { key: 'Enter' });
      fireEvent.keyDown(dialog, { key: 'a' });
      expect(onClose).not.toHaveBeenCalled();
    });
  });

  describe('body scroll lock', () => {
    it('sets body overflow to hidden on mount', () => {
      renderPicker();
      expect(document.body.style.overflow).toBe('hidden');
    });

    it('restores previous body overflow on unmount', () => {
      document.body.style.overflow = 'auto';
      const { unmount } = renderPicker();
      expect(document.body.style.overflow).toBe('hidden');
      unmount();
      expect(document.body.style.overflow).toBe('auto');
    });

    it('restores empty string when body had no overflow set', () => {
      document.body.style.overflow = '';
      const { unmount } = renderPicker();
      expect(document.body.style.overflow).toBe('hidden');
      unmount();
      expect(document.body.style.overflow).toBe('');
    });
  });

  describe('focus trap', () => {
    it('wraps focus from last to first element on Tab', () => {
      renderPicker();
      const dialog = screen.getByRole('dialog');
      const focusableElements = dialog.querySelectorAll<HTMLElement>('button, input');
      const lastElement = focusableElements[focusableElements.length - 1];

      lastElement.focus();
      expect(document.activeElement).toBe(lastElement);

      fireEvent.keyDown(dialog, { key: 'Tab' });
      expect(document.activeElement).toBe(focusableElements[0]);
    });

    it('wraps focus from first to last element on Shift+Tab', () => {
      renderPicker();
      const dialog = screen.getByRole('dialog');
      const focusableElements = dialog.querySelectorAll<HTMLElement>('button, input');
      const firstElement = focusableElements[0];

      firstElement.focus();
      expect(document.activeElement).toBe(firstElement);

      fireEvent.keyDown(dialog, { key: 'Tab', shiftKey: true });
      expect(document.activeElement).toBe(focusableElements[focusableElements.length - 1]);
    });
  });

  describe('auto-focus', () => {
    it('focuses the search input on mount', () => {
      renderPicker();
      const searchInput = screen.getByPlaceholderText('Search stations...');
      expect(document.activeElement).toBe(searchInput);
    });
  });

  describe('close button', () => {
    it('calls onClose when close button is clicked', () => {
      renderPicker();
      fireEvent.click(screen.getByRole('button', { name: 'Close' }));
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });
});
