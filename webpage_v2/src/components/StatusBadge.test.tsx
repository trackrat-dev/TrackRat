import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { StatusBadge } from './StatusBadge';

describe('StatusBadge', () => {
  // All six statuses the app renders: default label + expected color token.
  const cases = [
    { status: 'on time', label: 'On time', color: 'text-success' },
    { status: 'boarding', label: 'Boarding', color: 'text-accent' },
    { status: 'departed', label: 'Departed', color: 'text-info' },
    { status: 'delayed', label: 'Delayed', color: 'text-warning' },
    { status: 'cancelled', label: 'Cancelled', color: 'text-error' },
    { status: 'arrived', label: 'Arrived', color: 'text-success' },
  ];

  it.each(cases)(
    'renders "$status" with label "$label", $color, and the shared chip shape',
    ({ status, label, color }) => {
      const { getByText } = render(<StatusBadge status={status} />);
      const el = getByText(label);
      expect(el).toBeInTheDocument();
      expect(el.className).toContain(color);
      // One canonical shape for every badge.
      expect(el.className).toContain('rounded-full');
      expect(el.className).toContain('px-2');
      expect(el.className).toContain('py-1');
      expect(el.className).toContain('text-xs');
      expect(el.className).toContain('font-semibold');
    }
  );

  it('uses the on-palette info token for departed (not the old off-palette blue)', () => {
    const { getByText } = render(<StatusBadge status="departed" />);
    const el = getByText('Departed');
    expect(el.className).toContain('bg-info/15');
    expect(el.className).not.toContain('blue');
  });

  it('honors a custom label override for dynamic delay text', () => {
    const { getByText } = render(<StatusBadge status="delayed" label="5 mins late" />);
    const el = getByText('5 mins late');
    // Custom text, but still colored by the delayed status.
    expect(el.className).toContain('text-warning');
  });

  it('is case-insensitive when mapping status to color and label', () => {
    const { getByText } = render(<StatusBadge status="Cancelled" />);
    expect(getByText('Cancelled').className).toContain('text-error');
  });
});
