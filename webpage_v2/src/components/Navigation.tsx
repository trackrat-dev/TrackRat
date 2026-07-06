import type { ComponentType } from 'react';
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

interface NavItem {
  to: string;
  label: string;
  Icon: ComponentType<{ className?: string }>;
  /** Detail-route prefixes that should also light this tab (e.g. /trains/NP/NY). */
  prefixes: string[];
}

const NAV_ITEMS: NavItem[] = [
  { to: '/departures', label: 'Departures', Icon: DeparturesIcon, prefixes: ['/trains/', '/train/', '/trip'] },
  { to: '/status', label: 'Status', Icon: StatusIcon, prefixes: ['/route/'] },
  { to: '/favorites', label: 'Favorites', Icon: FavoritesIcon, prefixes: [] },
  { to: '/history', label: 'History', Icon: HistoryIcon, prefixes: [] },
];

interface NavigationProps {
  /** 'header' renders inline for desktop; 'bottom' renders the fixed mobile tab bar. */
  variant: 'header' | 'bottom';
}

export function Navigation({ variant }: NavigationProps) {
  const { pathname } = useLocation();

  const isActive = (item: NavItem) =>
    pathname === item.to || item.prefixes.some((prefix) => pathname.startsWith(prefix));

  const isHeader = variant === 'header';
  const navClass = isHeader
    ? 'hidden md:block'
    : 'fixed bottom-0 left-0 right-0 md:hidden bg-surface/80 backdrop-blur-xl border-t border-text-muted/20';
  const listClass = isHeader
    ? 'flex items-center gap-1'
    : 'flex items-center justify-around px-4 py-3';
  const linkClass = isHeader
    ? 'flex flex-row items-center gap-2 px-3 py-2 rounded-lg transition-colors'
    : 'flex flex-col items-center gap-1 px-3 py-2 rounded-lg transition-colors';
  const labelClass = isHeader ? 'text-sm font-medium' : 'text-xs font-medium';

  return (
    <nav className={navClass}>
      <div className={listClass}>
        {NAV_ITEMS.map((item) => {
          const active = isActive(item);
          const { to, label, Icon } = item;
          return (
            <Link
              key={to}
              to={to}
              aria-current={active ? 'page' : undefined}
              className={`${linkClass} ${
                active ? 'text-accent font-semibold' : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              <Icon />
              <span className={labelClass}>{label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
