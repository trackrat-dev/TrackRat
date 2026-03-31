interface ErrorMessageProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorMessage({ message, onRetry }: ErrorMessageProps) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center">
      <div className="text-error text-lg mb-4">⚠️ {message}</div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 bg-accent text-white rounded-lg font-semibold hover:bg-accent/80 transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  );
}
