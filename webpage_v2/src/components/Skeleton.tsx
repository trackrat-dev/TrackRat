/**
 * Layout-matched loading skeletons.
 *
 * `Skeleton` is the base building block — a pulsing placeholder block. Size and
 * position it with Tailwind utilities via `className` (e.g. `h-4 w-24`).
 * The composed skeletons below mirror real components so the first paint doesn't
 * jump when data arrives.
 */

export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div className={`animate-pulse rounded bg-text-muted/10 ${className}`.trim()} aria-hidden="true" />
  );
}

/** Mirrors `TrainCard`: title + line name, status badge, and departure/arrival/route rows. */
export function TrainCardSkeleton() {
  return (
    <div className="w-full border border-text-muted/20 rounded-2xl p-4 bg-surface/70 backdrop-blur-xl">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 space-y-2">
          <Skeleton className="h-6 w-28" />
          <Skeleton className="h-4 w-40" />
        </div>
        <Skeleton className="h-6 w-20 rounded-full" />
      </div>
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-24" />
        </div>
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-24" />
        </div>
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-4 w-12" />
        </div>
      </div>
    </div>
  );
}

/** Mirrors `TrainDetailsPage`: title card, forecast card block, and three stop cards. */
export function TrainDetailsSkeleton() {
  return (
    <div className="max-w-4xl mx-auto" role="status" aria-label="Loading train details" aria-busy="true">
      {/* Title card */}
      <div className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-6 mb-6 space-y-4">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-4 w-56" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-5 w-32" />
        </div>
      </div>

      {/* Forecast card block */}
      <div className="bg-surface/70 backdrop-blur-xl border border-text-muted/20 rounded-2xl p-4 mb-6">
        <Skeleton className="h-16 w-full" />
      </div>

      {/* Stop cards */}
      <div className="space-y-3">
        {[0, 1, 2].map(i => (
          <div key={i} className="bg-surface/50 backdrop-blur-xl border border-text-muted/20 rounded-xl p-4 space-y-2">
            <Skeleton className="h-5 w-44" />
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-full" />
          </div>
        ))}
      </div>

      <span className="sr-only">Loading train details</span>
    </div>
  );
}
