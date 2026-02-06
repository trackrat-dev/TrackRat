import { Link, useLocation } from 'react-router-dom';

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
          <span className="text-xl">🚂</span>
          <span className="text-xs md:text-sm font-medium">Departures</span>
        </Link>
        <Link
          to="/favorites"
          className={`flex flex-col md:flex-row items-center gap-1 md:gap-2 px-3 py-2 rounded-lg transition-colors ${
            isActive('/favorites') ? 'text-accent font-semibold' : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          <span className="text-xl">⭐</span>
          <span className="text-xs md:text-sm font-medium">Favorites</span>
        </Link>
      </div>
    </nav>
  );
}
