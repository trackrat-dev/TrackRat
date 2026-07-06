import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { TimeDisplay } from './TimeDisplay';

// Times use an explicit UTC offset; assertions check structure/classes rather
// than rendered clock strings so they hold regardless of the test timezone.
describe('TimeDisplay', () => {
  it('renders a single scheduled time (no strikethrough) when on schedule', () => {
    const { container } = render(
      <TimeDisplay scheduledTime="2025-01-15T14:00:00-05:00" delayMinutes={0} />
    );

    expect(container.querySelectorAll('span')).toHaveLength(1);
    expect(container.querySelector('.line-through')).not.toBeInTheDocument();
    expect(container.querySelector('.text-text-primary')).toBeInTheDocument();
  });

  it('renders a single scheduled time when no live time is available', () => {
    const { container } = render(
      <TimeDisplay scheduledTime="2025-01-15T14:00:00-05:00" delayMinutes={5} />
    );

    // delayMinutes is non-zero but there is no live time to flip to.
    expect(container.querySelector('.line-through')).not.toBeInTheDocument();
    expect(container.querySelectorAll('span')).toHaveLength(1);
  });

  it('leads with the live time and strikes through scheduled when late', () => {
    const { container } = render(
      <TimeDisplay
        scheduledTime="2025-01-15T14:00:00-05:00"
        liveTime="2025-01-15T14:21:00-05:00"
        delayMinutes={21}
      />
    );

    expect(container.querySelector('.text-warning')).toBeInTheDocument();
    expect(container.querySelector('.line-through')).toBeInTheDocument();
  });

  it('colors the live time green when the train is early', () => {
    const { container } = render(
      <TimeDisplay
        scheduledTime="2025-01-15T14:00:00-05:00"
        liveTime="2025-01-15T13:57:00-05:00"
        delayMinutes={-3}
      />
    );

    expect(container.querySelector('.text-success')).toBeInTheDocument();
    expect(container.querySelector('.line-through')).toBeInTheDocument();
  });
});
