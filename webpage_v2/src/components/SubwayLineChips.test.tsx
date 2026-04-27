import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SubwayLineChips } from './SubwayLineChips';

describe('SubwayLineChips', () => {
  it('renders nothing for a non-subway station code', () => {
    const { container } = render(<SubwayLineChips stationCode="NY" />);
    expect(container.innerHTML).toBe('');
  });

  it('renders chips for a subway station', () => {
    render(<SubwayLineChips stationCode="SL29" />);
    expect(screen.getByText('L')).toBeInTheDocument();
  });

  it('renders multiple chips for a multi-line station', () => {
    render(<SubwayLineChips stationCode="S127" />);
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();
    expect(screen.getByText('N')).toBeInTheDocument();
  });

  it('excludes the current line when excludeLine is set', () => {
    render(<SubwayLineChips stationCode="S127" excludeLine="1" />);
    expect(screen.queryByText('1')).not.toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();
  });

  it('renders chips with correct background colors', () => {
    render(<SubwayLineChips stationCode="SL29" />);
    const chip = screen.getByText('L');
    expect(chip).toHaveStyle({ backgroundColor: '#A7A9AC' });
  });

  it('applies custom size', () => {
    render(<SubwayLineChips stationCode="SL29" size={20} />);
    const chip = screen.getByText('L');
    expect(chip).toHaveStyle({ width: '20px', height: '20px' });
  });

  it('renders nothing when excludeLine removes the only line', () => {
    const { container } = render(<SubwayLineChips stationCode="SL29" excludeLine="L" />);
    expect(container.innerHTML).toBe('');
  });
});
