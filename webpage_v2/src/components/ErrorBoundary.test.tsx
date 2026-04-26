import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ErrorBoundary } from './ErrorBoundary';

function ThrowingChild({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error('test error');
  return <div>child rendered</div>;
}

describe('ErrorBoundary', () => {
  it('renders children when no error occurs', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild shouldThrow={false} />
      </ErrorBoundary>
    );
    expect(screen.getByText('child rendered')).toBeInTheDocument();
  });

  it('renders default error UI when child throws', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <ThrowingChild shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText('Reload')).toBeInTheDocument();
    expect(screen.queryByText('child rendered')).not.toBeInTheDocument();
  });

  it('renders custom fallback when provided and child throws', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <ErrorBoundary fallback={<div>custom fallback</div>}>
        <ThrowingChild shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(screen.getByText('custom fallback')).toBeInTheDocument();
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
  });

  it('renders nothing when fallback is null and child throws', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const { container } = render(
      <ErrorBoundary fallback={null}>
        <ThrowingChild shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(container.innerHTML).toBe('');
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
  });

  it('logs error details via componentDidCatch', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <ThrowingChild shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(errorSpy).toHaveBeenCalled();
    const callArgs = errorSpy.mock.calls.flat();
    const hasErrorBoundaryCatch = callArgs.some(
      (arg) => typeof arg === 'string' && arg.includes('ErrorBoundary caught')
    );
    expect(hasErrorBoundaryCatch).toBe(true);
  });
});
