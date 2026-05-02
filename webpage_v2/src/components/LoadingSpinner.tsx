export function LoadingSpinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center p-8" role="status" aria-label={label}>
      <div className="w-8 h-8 border-4 border-accent border-t-transparent rounded-full animate-spin" aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </div>
  );
}
