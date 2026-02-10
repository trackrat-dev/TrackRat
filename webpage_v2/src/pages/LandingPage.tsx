import { Link } from 'react-router-dom';

// Matches the base path in vite.config.ts and BrowserRouter basename
const BASE = '/TrackRat/';

const APP_STORE_URL = 'https://apps.apple.com/us/app/trackrat/id6746423610';
const YOUTUBE_URL = 'https://www.youtube.com/@TrackRat-App/shorts';
const INSTAGRAM_URL = 'https://www.instagram.com/trackratapp/';
const GITHUB_URL = 'https://github.com/bokonon1/TrackRat';
const FEEDBACK_URL = 'https://trackrat.nolt.io/';
const API_DOCS_URL = 'https://apiv2.trackrat.net/docs';
const SUPPORT_EMAIL = 'mailto:trackrat@andymartin.cc';

const features = [
  {
    title: 'See delays at a glance',
    description:
      'Visualize real-time departure and arrival delays on your route as well as across the network.',
    image: `${BASE}images/1.webp`,
  },
  {
    title: 'NJ Transit and Amtrak, together',
    description:
      'One view for all trains traveling your route, regardless of carrier.',
    image: `${BASE}images/2.webp`,
  },
  {
    title: 'Know your track early',
    description:
      'Platform predictions at Penn Station and other major hubs.',
    image: `${BASE}images/3.webp`,
  },
  {
    title: 'On your Lock Screen',
    description:
      'Live Activities show train status right on your Lock Screen and Dynamic Island.',
    image: `${BASE}images/4.webp`,
  },
  {
    title: 'PATH, PATCO, and more',
    description:
      'Not just NJ Transit and Amtrak! Track PATH, PATCO, LIRR, Metro-North, and more.',
    image: `${BASE}images/5.webp`,
  },
];

const transitSystems = [
  'NJ Transit',
  'Amtrak',
  'PATH',
  'PATCO',
  'LIRR',
  'Metro-North',
];

const faqs = [
  {
    q: 'Is TrackRat free?',
    a: 'Yes. The core features of TrackRat are completely free to use. Some of the more advanced features require a TrackRat Pro subscription to be purchased through the App Store. In both cases, there are no ads, no accounts, and no data collected.',
  },
  {
    q: 'How does track prediction work?',
    a: 'TrackRat uses historical data and live track activity to predict which platform your train will depart from. Predictions are available at Penn Station New York and other major hubs.',
  },
  {
    q: 'Which trains are supported?',
    a: 'NJ Transit, Amtrak, PATH, PATCO, LIRR, and Metro-North are currently supported.',
  },
  {
    q: 'How real-time is the data?',
    a: 'Train positions and status update every 15–30 seconds from transit agency feeds. The web app polls every 30 seconds.',
  },
  {
    q: 'Is TrackRat open source?',
    a: 'Yes. The backend, iOS app, and web app are all open source under the Apache 2.0 license on GitHub.',
  },
  {
    q: 'Can I build my own app with TrackRat data?',
    a: 'Yes! The API is open and documented. However, we are still actively developing and occasionally making breaking changes to the API. If you are planning to use it in a production application, please get in touch so we can coordinate and avoid surprises.',
  },
  {
    q: 'Does TrackRat work on Android?',
    a: "Not yet. An Android app is something we'd love to build, but we haven't had the bandwidth. If you're an Android developer interested in leading this effort, we'd love to hear from you — please get in touch!",
  },
  {
    q: 'Why are some trains showing as SCHEDULED instead of real-time?',
    a: 'TrackRat combines scheduled timetable data with real-time feeds from transit agencies. Trains show as SCHEDULED until the agency\'s real-time feed confirms they are active. Once a train appears in the real-time feed, it switches to OBSERVED with live position and delay information.',
  },
  {
    q: 'Do I need to create an account?',
    a: 'No. TrackRat works without any account or sign-up. There is no login, no personal data collection, and no tracking. Just open the app or website and start looking up trains.',
  },
];

export function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-text-primary">
      {/* Hero */}
      <section className="px-6 pt-12 pb-16 text-center max-w-3xl mx-auto">
        <img
          src={`${BASE}icon.png`}
          alt="TrackRat"
          className="w-24 h-24 rounded-[22px] mx-auto mb-6 shadow-lg"
        />
        <h1 className="text-4xl md:text-5xl font-bold mb-4 bg-gradient-to-r from-primary-start to-primary-end bg-clip-text text-transparent">
          TrackRat
        </h1>
        <p className="text-lg md:text-xl text-text-secondary mb-8 max-w-xl mx-auto">
          Open source, real-time train tracking for NJ Transit, Amtrak, PATH, PATCO, LIRR, Metro-North, and more!
        </p>
        <div className="flex items-center justify-center gap-4">
          <a
            href={APP_STORE_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="text-text-muted hover:text-accent transition-colors"
            aria-label="Download on the App Store"
          >
            <svg className="w-7 h-7" fill="currentColor" viewBox="0 0 24 24">
              <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z" />
            </svg>
          </a>
          <a
            href={YOUTUBE_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="text-text-muted hover:text-accent transition-colors"
            aria-label="YouTube"
          >
            <svg className="w-7 h-7" fill="currentColor" viewBox="0 0 24 24">
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
            <svg className="w-7 h-7" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 1 0 0 12.324 6.162 6.162 0 0 0 0-12.324zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.406-11.845a1.44 1.44 0 1 0 0 2.881 1.44 1.44 0 0 0 0-2.881z" />
            </svg>
          </a>
        </div>
      </section>

      {/* Feature Showcase */}
      <section className="px-6 py-12 max-w-3xl mx-auto">
        {features.map((feature, i) => (
          <div
            key={feature.title}
            className={`flex flex-col ${i % 2 === 0 ? 'md:flex-row' : 'md:flex-row-reverse'} items-center gap-8 mb-16 last:mb-0`}
          >
            <img
              src={feature.image}
              alt={feature.title}
              className="w-48 rounded-2xl shadow-lg"
              loading="lazy"
            />
            <div className="text-center md:text-left flex-1">
              <h2 className="text-2xl md:text-3xl font-bold mb-3">
                {feature.title}
              </h2>
              <p className="text-text-secondary text-lg leading-relaxed">
                {feature.description}
              </p>
            </div>
          </div>
        ))}
      </section>

      {/* Supported Transit Systems */}
      <section className="px-6 py-12 bg-surface/50">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold text-center mb-8">
            Supported Transit Systems
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
            {transitSystems.map((name) => (
              <div
                key={name}
                className="bg-surface/80 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-5 text-center"
              >
                <span className="font-semibold text-lg">{name}</span>
              </div>
            ))}
          </div>
          <p className="text-text-secondary text-center">
            Have an idea for another transit system?{' '}
            <a
              href={FEEDBACK_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:underline"
            >
              Send us your suggestions
            </a>
          </p>
        </div>
      </section>

      {/* Open Source */}
      <section className="px-6 py-12 max-w-4xl mx-auto">
        <h2 className="text-2xl md:text-3xl font-bold text-center mb-8">
          Open Source & Publicly Available
        </h2>
        <div className="space-y-8 max-w-2xl mx-auto">
          <div>
            <h3 className="font-semibold text-lg mb-2">Apache 2.0 Licensed</h3>
            <p className="text-text-secondary leading-relaxed">
              TrackRat is fully open source under the Apache 2.0 license. You
              can read, fork, and contribute to every part of the project on
              GitHub.
            </p>
        <div className="text-center mt-8">
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-6 py-3 bg-text-primary text-background font-semibold rounded-xl hover:opacity-90 transition-opacity"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z" />
            </svg>
            View on GitHub
          </a>
        </div>
          </div>

          <div>
            <h3 className="font-semibold text-lg mb-2">Public REST API</h3>
            <p className="text-text-secondary leading-relaxed">
              The{' '}
              <a
                href={API_DOCS_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent hover:underline"
              >
                REST API
              </a>{' '}
              is open for anyone to use. Build your own transit tools, run
              analyses, or integrate TrackRat data into your projects.
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-lg mb-2">Web App (experimental)</h3>
            <p className="text-text-secondary leading-relaxed">
              The experimental web app provides cross-platform support for departure lookups and
              real-time train status. This is under development!
            </p>
            <Link
              to="/departures"
              className="inline-flex text-center items-center gap-2 mt-3 px-4 py-2 bg-accent/20 text-accent font-medium rounded-lg hover:bg-accent/30 transition-colors"
            >
              Try the Web App
            </Link>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="px-6 py-12 bg-surface/50">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold text-center mb-8">
            FAQ
          </h2>
          <div className="space-y-6">
            {faqs.map((faq) => (
              <div key={faq.q}>
                <h3 className="font-semibold text-lg mb-1">{faq.q}</h3>
                <p className="text-text-secondary">{faq.a}</p>
              </div>
            ))}
          </div>
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
            <a
              href={FEEDBACK_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="text-text-muted hover:text-accent transition-colors"
            >
              Submit Feedback
            </a>
          </div>
          <p className="text-text-muted text-sm">
            &copy; {new Date().getFullYear()} TrackRat
          </p>
        </div>
      </footer>
    </div>
  );
}
