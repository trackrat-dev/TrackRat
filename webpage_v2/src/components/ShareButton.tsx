import { useState } from 'react';
import { share, ShareData, isShareSupported } from '../utils/share';

interface ShareButtonProps {
  shareData: ShareData;
  className?: string;
}

export function ShareButton({ shareData, className = '' }: ShareButtonProps) {
  const [showFeedback, setShowFeedback] = useState(false);

  const handleShare = async () => {
    const success = await share(shareData);

    if (success) {
      setShowFeedback(true);
      setTimeout(() => setShowFeedback(false), 2000);
    }
  };

  const supported = isShareSupported();
  const feedbackText = supported ? 'Shared!' : 'Link copied!';

  return (
    <div className="relative">
      <button
        onClick={handleShare}
        className={`p-2 rounded-lg bg-surface/70 backdrop-blur-xl border border-text-muted/20 hover:border-accent/50 transition-all ${className}`}
        aria-label="Share train"
        title={supported ? 'Share' : 'Copy link'}
      >
        <svg
          className="w-5 h-5 text-accent"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"
          />
        </svg>
      </button>

      {/* Feedback toast */}
      {showFeedback && (
        <div className="absolute top-full mt-2 left-1/2 transform -translate-x-1/2 whitespace-nowrap bg-success text-white text-sm px-3 py-1 rounded-lg shadow-lg animate-fade-in">
          {feedbackText}
        </div>
      )}
    </div>
  );
}
