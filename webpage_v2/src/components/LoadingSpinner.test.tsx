import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LoadingSpinner } from './LoadingSpinner';

describe('LoadingSpinner', () => {
  it('renders with role="status" for screen reader announcements', () => {
    render(<LoadingSpinner />);
    const status = screen.getByRole('status');
    expect(status).toBeInTheDocument();
  });

  it('has default aria-label "Loading"', () => {
    render(<LoadingSpinner />);
    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-label', 'Loading');
  });

  it('accepts a custom label prop', () => {
    render(<LoadingSpinner label="Loading departures" />);
    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-label', 'Loading departures');
  });

  it('includes sr-only text matching the label', () => {
    render(<LoadingSpinner label="Loading trains" />);
    const srText = screen.getByText('Loading trains');
    expect(srText).toBeInTheDocument();
    expect(srText).toHaveClass('sr-only');
  });

  it('hides the spinner animation from screen readers', () => {
    const { container } = render(<LoadingSpinner />);
    const spinner = container.querySelector('.animate-spin');
    expect(spinner).toHaveAttribute('aria-hidden', 'true');
  });
});
