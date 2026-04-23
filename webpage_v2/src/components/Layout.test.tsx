import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Layout } from './Layout';

function renderLayout() {
  return render(
    <MemoryRouter>
      <Layout />
    </MemoryRouter>
  );
}

describe('Layout', () => {
  it('renders TrackRat name in header', () => {
    renderLayout();
    expect(screen.getByText('TrackRat')).toBeInTheDocument();
  });

  it('shows Beta badge in header', () => {
    renderLayout();
    expect(screen.getByText('Beta')).toBeInTheDocument();
  });

  it('renders feedback button', () => {
    renderLayout();
    expect(screen.getByLabelText('Send feedback')).toBeInTheDocument();
  });

  it('renders GitHub link', () => {
    renderLayout();
    expect(screen.getByLabelText('GitHub')).toBeInTheDocument();
  });
});
