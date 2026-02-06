import { Link, Outlet } from 'react-router-dom';
import { Navigation } from './Navigation';

export function Layout() {
  return (
    <div className="min-h-screen bg-background text-text-primary flex flex-col">
      <header className="bg-surface/80 backdrop-blur-xl border-b border-text-muted/20 px-4 py-4">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-2xl font-bold">
            <Link
              to="/departures"
              className="bg-gradient-to-r from-primary-start to-primary-end bg-clip-text text-transparent hover:opacity-80 transition-opacity"
            >
              TrackRat
            </Link>
          </h1>
        </div>
      </header>

      <main className="flex-1 pb-20 md:pb-4">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <Outlet />
        </div>
      </main>

      <Navigation />
    </div>
  );
}
