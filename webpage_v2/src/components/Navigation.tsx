import type { ComponentType } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { DeparturesIcon, StatusIcon, StarIcon, HistoryIcon } from './icons';

interface NavItem {
  to: string;
  label: string;
  Icon: ComponentType<{ className?: string }>;
  /** Detail-route prefixes that should also light this tab (e.g. /trains/NP/NY). */
  prefixes: string[];
}

const NAV_ITEMS: NavItem[] = [
  { to: '/departures', label: 'Departures', Icon: DeparturesIcon, prefixes: ['/trains/', '/train/', '/trip'] },
  { to: '/status', label: 'Status', Icon: StatusIcon, prefixes: ['/route/', '/line/', '/system/'] },
  { to: '/favorites', label: 'Favorites', Icon: StarIcon, prefixes: [] },
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
