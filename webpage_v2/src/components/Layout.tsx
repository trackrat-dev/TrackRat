import { useState } from 'react';
import { Link, Outlet } from 'react-router-dom';
import { Navigation } from './Navigation';
import { FeedbackModal } from './FeedbackModal';

export function Layout() {
  const [showFeedback, setShowFeedback] = useState(false);

  return (
    <div className="min-h-screen bg-background text-text-primary flex flex-col">
      <header className="bg-surface/80 backdrop-blur-xl border-b border-text-muted/20 px-4 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <h1 className="text-2xl font-bold">
            <Link
              to="/"
              className="flex items-center gap-2 hover:opacity-80 transition-opacity"
            >
              <img
                src="/icon.png"
                alt="TrackRat"
                className="w-8 h-8 rounded-lg"
              />
              <span className="bg-gradient-to-r from-primary-start to-primary-end bg-clip-text text-transparent">
                TrackRat
              </span>
            </Link>
          </h1>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowFeedback(true)}
              className="text-text-muted hover:text-text-primary transition-colors"
              aria-label="Send feedback"
              title="Send feedback"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </button>
            <a
              href="https://github.com/bokonon1/TrackRat"
              target="_blank"
              rel="noopener noreferrer"
              className="text-text-muted hover:text-text-primary transition-colors"
              aria-label="GitHub"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
              </svg>
            </a>
          </div>
        </div>
      </header>

      {showFeedback && <FeedbackModal onClose={() => setShowFeedback(false)} />}

      <main className="flex-1 pb-20 md:pb-4">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <Outlet />
        </div>
      </main>

      <Navigation />
    </div>
  );
}
