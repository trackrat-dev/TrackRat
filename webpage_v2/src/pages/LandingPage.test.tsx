import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LandingPage } from './LandingPage';

const APP_STORE_URL = 'https://apps.apple.com/us/app/trackrat/id6746423610';

function renderLandingPage() {
  return render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>
  );
}

describe('LandingPage hero CTAs', () => {
  it('offers a one-click path into /departures via the "Open the web app (beta)" CTA', () => {
    renderLandingPage();
    const webAppCta = screen.getByRole('link', { name: 'Open the web app (beta)' });
    expect(webAppCta).toHaveAttribute('href', '/departures');
    // Must be a real anchor link (keyboard reachable), not a div/button with onClick.
    expect(webAppCta.tagName).toBe('A');
  });

  it('keeps "Download for iOS" as a link pointing at the App Store', () => {
    renderLandingPage();
    const iosCta = screen.getByRole('link', { name: 'Download for iOS' });
    expect(iosCta).toHaveAttribute('href', APP_STORE_URL);
    expect(iosCta.tagName).toBe('A');
  });

  it('gives the two hero CTAs distinct accessible names and separate destinations', () => {
    renderLandingPage();
    const webAppCta = screen.getByRole('link', { name: 'Open the web app (beta)' });
    const iosCta = screen.getByRole('link', { name: 'Download for iOS' });
    expect(webAppCta).not.toBe(iosCta);
    expect(webAppCta.getAttribute('href')).not.toBe(iosCta.getAttribute('href'));
  });

  it('updates the Web App resources card CTA copy to "Open the web app"', () => {
    renderLandingPage();
    const cardCta = screen.getByRole('link', {
      name: /^Open the web app Track departures from any browser/,
    });
    expect(cardCta).toHaveAttribute('href', '/departures');
  });
});
