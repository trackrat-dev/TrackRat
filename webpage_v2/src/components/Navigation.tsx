import { Link, useLocation } from 'react-router-dom';

function DeparturesIcon({ className }: { className?: string }) {
  return (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="3" width="16" height="16" rx="2" />
      <path d="M4 11h16" />
      <path d="M12 3v8" />
      <circle cx="8" cy="21" r="1" />
      <circle cx="16" cy="21" r="1" />
      <path d="M8 19V11" />
      <path d="M16 19V11" />
    </svg>
  );
}

function StatusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3v18h18" />
      <path d="M7 16l4-8 4 4 4-6" />
    </svg>
  );
}

function FavoritesIcon({ className }: { className?: string }) {
  return (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="1">
      <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
    </svg>
  );
}

function HistoryIcon({ className }: { className?: string }) {
  return (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12a9 9 0 1 0 3-6.7" />
      <path d="M3 4v5h5" />
      <path d="M12 7v5l3 3" />
    </svg>
  );
}

export function Navigation() {
  const location = useLocation();

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  return (
    <nav className="fixed bottom-0 left-0 right-0 md:relative md:bottom-auto bg-surface/80 backdrop-blur-xl border-t border-text-muted/20 md:border-none">
      <div className="flex items-center justify-around md:justify-start md:gap-4 px-4 py-3">
        <Link
          to="/departures"
          className={`flex flex-col md:flex-row items-center gap-1 md:gap-2 px-3 py-2 rounded-lg transition-colors ${
            isActive('/departures') ? 'text-accent font-semibold' : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          <DeparturesIcon />
          <span className="text-xs md:text-sm font-medium">Departures</span>
        </Link>
        <Link
          to="/status"
          className={`flex flex-col md:flex-row items-center gap-1 md:gap-2 px-3 py-2 rounded-lg transition-colors ${
            isActive('/status') ? 'text-accent font-semibold' : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          <StatusIcon />
          <span className="text-xs md:text-sm font-medium">Status</span>
        </Link>
        <Link
          to="/favorites"
          className={`flex flex-col md:flex-row items-center gap-1 md:gap-2 px-3 py-2 rounded-lg transition-colors ${
            isActive('/favorites') ? 'text-accent font-semibold' : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          <FavoritesIcon />
          <span className="text-xs md:text-sm font-medium">Favorites</span>
        </Link>
        <Link
          to="/history"
          className={`flex flex-col md:flex-row items-center gap-1 md:gap-2 px-3 py-2 rounded-lg transition-colors ${
            isActive('/history') ? 'text-accent font-semibold' : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          <HistoryIcon />
          <span className="text-xs md:text-sm font-medium">History</span>
        </Link>
      </div>
    </nav>
  );
}
