import { useState, useRef, useEffect } from 'react';
import { apiService } from '../services/api';

interface FeedbackModalProps {
  onClose: () => void;
}

export function FeedbackModal({ onClose }: FeedbackModalProps) {
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim()) return;

    setSubmitting(true);
    setError(null);

    try {
      await apiService.submitFeedback({
        message: message.trim(),
        screen: 'web_feedback',
        app_version: 'web-1.0.0',
        device_model: navigator.userAgent.slice(0, 100),
      });
      setSubmitted(true);
      timeoutRef.current = setTimeout(onClose, 2000);
    } catch {
      setError('Failed to send feedback. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-background border border-text-muted/20 rounded-2xl shadow-xl w-full max-w-md animate-fade-in"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-text-muted/10">
          <h3 className="text-lg font-semibold text-text-primary">Send Feedback</h3>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary text-xl leading-none">&times;</button>
        </div>

        {submitted ? (
          <div className="p-6 text-center">
            <div className="text-success text-2xl mb-2">Thanks!</div>
            <p className="text-text-secondary text-sm">Your feedback has been submitted.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="p-4">
            <textarea
              value={message}
              onChange={e => setMessage(e.target.value)}
              placeholder="What's on your mind? Bug reports, feature requests, or anything else..."
              className="w-full h-32 p-3 rounded-xl bg-surface border border-text-muted/20 text-text-primary placeholder-text-muted text-sm resize-none focus:outline-none focus:border-accent/50"
              autoFocus
              maxLength={2000}
            />
            <div className="flex items-center justify-between mt-1 mb-3">
              <span className="text-xs text-text-muted">{message.length}/2000</span>
              {error && <span className="text-xs text-error">{error}</span>}
            </div>
            <button
              type="submit"
              disabled={!message.trim() || submitting}
              className="w-full py-2.5 rounded-xl bg-accent text-white font-semibold text-sm hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {submitting ? 'Sending...' : 'Send Feedback'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
