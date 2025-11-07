import { ReactNode } from 'react';
import { Navigation } from './Navigation';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-background text-white flex flex-col">
      <header className="bg-surface/80 backdrop-blur-xl border-b border-white/10 px-4 py-4">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-primary-start to-primary-end bg-clip-text text-transparent">
            TrackRat
          </h1>
        </div>
      </header>

      <main className="flex-1 pb-20 md:pb-4">
        <div className="max-w-7xl mx-auto px-4 py-6">{children}</div>
      </main>

      <Navigation />
    </div>
  );
}
