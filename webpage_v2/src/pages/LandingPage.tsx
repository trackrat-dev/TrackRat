import { Link } from 'react-router-dom';

// Matches the base path in vite.config.ts and BrowserRouter basename
const BASE = '/TrackRat/';

const APP_STORE_URL = 'https://apps.apple.com/us/app/trackrat/id6746423610';
const YOUTUBE_URL = 'https://www.youtube.com/@TrackRat-App/shorts';
const INSTAGRAM_URL = 'https://www.instagram.com/trackratapp/';
const FEEDBACK_URL = 'https://trackrat.nolt.io/';
const SUPPORT_EMAIL = 'mailto:trackrat@andymartin.cc';

const features = [
  {
    title: 'See delays at a glance',
    description:
      'Color-coded routes showing real-time delay status across the entire network. Know before you leave whether your line is running smoothly.',
    image: `${BASE}images/1.webp`,
  },
  {
    title: 'NJ Transit and Amtrak, together',
    description:
      'One view for all trains on your route, regardless of carrier. Compare times, see which trains are running on time, and pick the best option.',
    image: `${BASE}images/2.webp`,
  },
  {
    title: 'Know your track early',
    description:
      'AI-powered platform predictions at Penn Station and other major hubs. Get to the right platform before the announcement.',
    image: `${BASE}images/3.webp`,
  },
  {
    title: 'Your commute, on your Lock Screen',
    description:
      'Live Activities show real-time train status right on your Lock Screen and Dynamic Island. No need to open the app.',
    image: `${BASE}images/4.webp`,
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
          Real-time train tracking for NJ Transit, Amtrak, PATH, PATCO, LIRR, and Metro-North
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-6">
          <Link
            to="/departures"
            className="inline-flex items-center px-8 py-3 bg-accent text-white font-semibold rounded-xl hover:opacity-90 transition-opacity text-lg"
          >
            Try the Web App
          </Link>
          <a href={APP_STORE_URL} target="_blank" rel="noopener noreferrer">
            <img
              src="https://developer.apple.com/assets/elements/badges/download-on-the-app-store.svg"
              alt="Download on the App Store"
              className="h-12"
            />
          </a>
        </div>
        <div className="flex items-center justify-center gap-4">
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
      <section className="px-6 py-12 max-w-5xl mx-auto">
        {features.map((feature, i) => (
          <div
            key={feature.title}
            className={`flex flex-col ${i % 2 === 0 ? 'md:flex-row' : 'md:flex-row-reverse'} items-center gap-8 mb-16 last:mb-0`}
          >
            <img
              src={feature.image}
              alt={feature.title}
              className="w-64 rounded-2xl shadow-lg"
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
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {transitSystems.map((name) => (
              <div
                key={name}
                className="bg-surface/80 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-5 text-center"
              >
                <span className="font-semibold text-lg">{name}</span>
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
          <a href={APP_STORE_URL} target="_blank" rel="noopener noreferrer">
            <img
              src="https://developer.apple.com/assets/elements/badges/download-on-the-app-store.svg"
              alt="Download on the App Store"
              className="h-10 mx-auto mb-4"
            />
          </a>
          <p className="text-text-muted text-sm">
            &copy; {new Date().getFullYear()} TrackRat
          </p>
        </div>
      </footer>
    </div>
  );
}
