import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

// Matches the base path in vite.config.ts and BrowserRouter basename
const BASE = '/';

const APP_STORE_URL = 'https://apps.apple.com/us/app/trackrat/id6746423610';
const GITHUB_URL = 'https://github.com/trackrat-dev/TrackRat';
const YOUTUBE_URL = 'https://www.youtube.com/@TrackRat-App/shorts';
const INSTAGRAM_URL = 'https://www.instagram.com/trackratapp/';
const API_DOCS_URL = 'https://apiv2.trackrat.net/docs';
const SUPPORT_EMAIL = 'mailto:trackrat@andymartin.cc';

const features = [
  {
    title: 'See delays at a glance',
    description:
      'Color-coded status for every train. Know instantly if trains are on time, delayed, or cancelled.',
    image: `${BASE}images/1.webp`,
  },
  {
    title: 'Know your track early',
    description:
      'Track predictions so you can head to the right platform before the board updates.',
    image: `${BASE}images/3.webp`,
  },
  {
    title: 'Never miss a disruption',
    description:
      'Set up alerts for your regular routes. Get notified about delays, cancellations, and planned service changes.',
    image: `${BASE}images/alerts.webp`,
  },
  {
    title: 'All your options on one screen',
    description:
      'NJ Transit, Amtrak, etc — browse combined schedules for any route.',
    image: `${BASE}images/2.webp`,
  },
  {
    title: 'Updates on your Lock Screen',
    description:
      'Start a Live Activity and get real-time updates without opening the app.',
    image: `${BASE}images/4.webp`,
  },
];

const unifiedFeature = {
  title: 'NYC Subway, LIRR, Metro-North, PATH, and 7 more systems',
  images: [
    `${BASE}images/mtn.webp`,
    `${BASE}images/5.webp`,
    `${BASE}images/subway.webp`,
    `${BASE}images/lirr.webp`,
  ],
};

const transitSystems = [
  { name: 'NJ Transit', region: 'Northeast' },
  { name: 'Amtrak', region: 'Northeast' },
  { name: 'PATH', region: 'Northeast' },
  { name: 'PATCO', region: 'Northeast' },
  { name: 'LIRR', region: 'New York' },
  { name: 'Metro-North', region: 'New York' },
  { name: 'NYC Subway', region: 'New York' },
  { name: 'DC Metro (beta)', region: 'DC' },
  { name: 'MBTA Commuter Rail (beta)', region: 'Boston' },
  { name: 'Metra (beta)', region: 'Chicago' },
  { name: 'BART (beta)', region: 'Bay Area' },
];

function IOSBanner() {
  const [dismissed, setDismissed] = useState(false);
  const [isIOS, setIsIOS] = useState(false);

  useEffect(() => {
    setIsIOS(/iPhone|iPad|iPod/.test(navigator.userAgent));
    setDismissed(sessionStorage.getItem('trackrat:ios-banner-dismissed') === 'true');
  }, []);

  if (!isIOS || dismissed) return null;

  const handleDismiss = () => {
    setDismissed(true);
    sessionStorage.setItem('trackrat:ios-banner-dismissed', 'true');
  };

  return (
    <div className="bg-surface/90 backdrop-blur-xl border-b border-text-muted/20 px-4 py-3">
      <div className="max-w-3xl mx-auto flex items-center gap-3">
        <img
          src={`${BASE}icon.png`}
          alt="TrackRat"
          className="w-10 h-10 rounded-lg"
        />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-text-primary">TrackRat</div>
          <div className="text-xs text-text-muted">Get the full experience on iOS</div>
        </div>
        <a
          href={APP_STORE_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="px-3 py-1.5 bg-accent text-white text-xs font-semibold rounded-lg shrink-0"
        >
          Open
        </a>
        <button
          onClick={handleDismiss}
          className="text-text-muted hover:text-text-primary text-lg leading-none shrink-0"
        >
          ×
        </button>
      </div>
    </div>
  );
}

export function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-text-muted">
      <IOSBanner />

      {/* Hero */}
      <section className="px-6 pt-14 pb-12 text-center max-w-3xl mx-auto">
        <img
          src={`${BASE}icon.png`}
          alt="TrackRat"
          className="w-24 h-24 rounded-[22px] mx-auto mb-6 shadow-lg"
        />
        <h1 className="text-4xl md:text-5xl font-bold mb-4 text-text-primary">
          TrackRat
        </h1>
        <p className="text-lg md:text-xl text-text-secondary mb-8 max-w-xl mx-auto leading-relaxed">
          Open source, real-time train tracking for NJ Transit, Amtrak, the Subway, PATH, LIRR, Metro-North, and more!
        </p>
        <a
          href={APP_STORE_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-6 py-3 mb-4 rounded-xl bg-accent text-white font-semibold text-lg hover:bg-accent/90 transition-colors shadow-lg"
        >
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z" />
          </svg>
          Download for iOS
        </a>
        <div className="flex items-center justify-center gap-5 mt-4">
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="text-text-muted hover:text-text-primary transition-colors"
            aria-label="View on GitHub"
          >
            <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
            </svg>
          </a>
          <a
            href={YOUTUBE_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="text-text-muted hover:text-accent transition-colors"
            aria-label="YouTube"
          >
            <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
              <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
            </svg>
          </a>
          <a
            href={INSTAGRAM_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="text-text-muted hover:text-accent transition-colors"
            aria-label="Instagram"
          >
            <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 1 0 0 12.324 6.162 6.162 0 0 0 0-12.324zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.406-11.845a1.44 1.44 0 1 0 0 2.881 1.44 1.44 0 0 0 0-2.881z" />
            </svg>
          </a>
        </div>
      </section>

      {/* Feature Showcase */}
      <section className="px-6 py-12 max-w-4xl mx-auto">
        {features.map((feature, i) => (
          <div
            key={feature.title}
            className={`flex flex-col ${i % 2 === 0 ? 'md:flex-row' : 'md:flex-row-reverse'} items-center gap-8 md:gap-12 mb-20`}
          >
            <img
              src={feature.image}
              alt={feature.title}
              className="w-64 md:w-72 rounded-2xl shadow-lg"
              loading="lazy"
            />
            <div className="text-center md:text-left flex-1">
              <h2 className="text-2xl md:text-3xl font-bold mb-3 text-text-primary">
                {feature.title}
              </h2>
              <p className="text-text-secondary text-lg leading-relaxed">
                {feature.description}
              </p>
            </div>
          </div>
        ))}
      </section>

      {/* Multi-system Showcase */}
      <section className="px-6 py-14 max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <h2 className="text-2xl md:text-3xl font-bold text-text-primary">
            {unifiedFeature.title}
          </h2>
        </div>
        <div className="flex justify-center gap-2 md:gap-4">
          {unifiedFeature.images.map((src) => (
            <img
              key={src}
              src={src}
              alt={unifiedFeature.title}
              className="w-36 md:w-48 rounded-2xl shadow-lg"
              loading="lazy"
            />
          ))}
        </div>
      </section>

      {/* Supported Transit Systems */}
      <section className="px-6 py-12 bg-surface/50">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold text-center mb-8 text-text-primary">
            Supported Transit Systems
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
            {transitSystems.map((system) => (
              <div
                key={system.name}
                className="bg-surface/80 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-5 text-center"
              >
                <span className="font-semibold text-lg">{system.name}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* More Resources */}
      <section className="px-6 py-12 max-w-4xl mx-auto">
        <h2 className="text-2xl md:text-3xl font-bold text-center mb-8 text-text-primary">
          More Resources
        </h2>
        <div className="grid md:grid-cols-3 gap-6 max-w-3xl mx-auto">
          <Link
            to="/departures"
            className="bg-surface/80 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-6 text-center hover:border-accent/40 transition-colors"
          >
            <h3 className="font-semibold text-lg mb-2 text-text-primary">Web App</h3>
            <p className="text-text-muted text-sm leading-relaxed">
              Track departures from any browser. No download required.
            </p>
            <span className="inline-block mt-3 text-xs font-medium text-accent bg-accent/15 px-2 py-0.5 rounded-full">
              BETA
            </span>
          </Link>
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="bg-surface/80 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-6 text-center hover:border-accent/40 transition-colors"
          >
            <h3 className="font-semibold text-lg mb-2 text-text-primary">Open Source</h3>
            <p className="text-text-muted text-sm leading-relaxed">
              TrackRat is open source under GPLv3. View the code, report
              issues, or contribute.
            </p>
          </a>
          <a
            href={API_DOCS_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="bg-surface/80 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-6 text-center hover:border-accent/40 transition-colors"
          >
            <h3 className="font-semibold text-lg mb-2 text-text-primary">Public REST API</h3>
            <p className="text-text-muted text-sm leading-relaxed">
              Build your own transit tools or integrate
              TrackRat data. Free for everyone, but please reach out before using in production!
            </p>
          </a>
        </div>
      </section>

      {/* Footer */}
      <footer className="px-6 py-12 text-center">
        <div className="max-w-4xl mx-auto">
          <div className="flex flex-wrap items-center justify-center gap-6 mb-6 text-sm">
            <a
              href={`${BASE}privacy.txt`}
              className="text-text-muted hover:text-accent transition-colors"
            >
              Privacy Policy
            </a>
            <a
              href={`${BASE}terms.txt`}
              className="text-text-muted hover:text-accent transition-colors"
            >
              Terms of Use
            </a>
            <a
              href={SUPPORT_EMAIL}
              className="text-text-muted hover:text-accent transition-colors"
            >
              Contact Support
            </a>
          </div>
          <p className="text-text-muted text-xs mt-2">
            Amtrak data powered by{' '}
            <a
              href="https://amtraker.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:underline"
            >
              Amtraker
            </a>
            .
          </p>
          <p className="text-text-muted text-sm mt-4">
            &copy; {new Date().getFullYear()} TrackRat
          </p>
        </div>
      </footer>
    </div>
  );
}
