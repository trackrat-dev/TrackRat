import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Skeleton, TrainCardSkeleton, TrainDetailsSkeleton } from './Skeleton';

describe('Skeleton', () => {
  it('renders the pulse/rounded/muted-background building block', () => {
    const { container } = render(<Skeleton />);
    const el = container.firstElementChild as HTMLElement;
    expect(el).not.toBeNull();
    expect(el).toHaveClass('animate-pulse', 'rounded', 'bg-text-muted/10');
    // Decorative — must not be announced to screen readers.
    expect(el).toHaveAttribute('aria-hidden', 'true');
  });

  it('merges caller-provided sizing classes without dropping the base classes', () => {
    const { container } = render(<Skeleton className="h-4 w-24" />);
    const el = container.firstElementChild as HTMLElement;
    expect(el).toHaveClass('animate-pulse', 'rounded', 'bg-text-muted/10', 'h-4', 'w-24');
  });
});

describe('TrainCardSkeleton', () => {
  it('mirrors a TrainCard: card shell plus title, badge and three body rows', () => {
    const { container } = render(<TrainCardSkeleton />);
    // Outer shell matches TrainCard's rounded-2xl bordered card.
    const shell = container.firstElementChild as HTMLElement;
    expect(shell).toHaveClass('rounded-2xl', 'border', 'p-4');
    // 2 header lines + 1 badge + 3 rows x 2 = 9 pulse blocks.
    expect(container.querySelectorAll('.animate-pulse')).toHaveLength(9);
  });
});

describe('TrainDetailsSkeleton', () => {
  it('announces loading and renders title card, forecast block and three stop cards', () => {
    const { container } = render(<TrainDetailsSkeleton />);
    const region = screen.getByRole('status');
    expect(region).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByText('Loading train details')).toBeInTheDocument();
    // 4 (title card) + 1 (forecast) + 3 x 3 (stop cards) = 14 pulse blocks.
    expect(container.querySelectorAll('.animate-pulse')).toHaveLength(14);
  });
});
