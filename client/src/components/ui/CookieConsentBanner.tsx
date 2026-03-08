import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { X } from 'lucide-react';

const STORAGE_KEY = 'nash_cookie_consent';

export default function CookieConsentBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      // Small delay so the banner doesn't flash during initial page load
      const timer = setTimeout(() => setVisible(true), 1200);
      return () => clearTimeout(timer);
    }
  }, []);

  const accept = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ accepted: true, at: new Date().toISOString() }));
    setVisible(false);
  };

  const dismiss = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ accepted: false, at: new Date().toISOString() }));
    setVisible(false);
  };

  if (!visible) {
    return null;
  }

  return (
    <div
      role="dialog"
      aria-label="Cookie consent"
      className="fixed bottom-4 left-4 right-4 z-50 mx-auto max-w-xl animate-in slide-in-from-bottom-4 duration-300 rounded-2xl border border-border-light bg-surface-secondary p-4 shadow-lg sm:left-6 sm:right-auto sm:max-w-sm"
    >
      <button
        onClick={dismiss}
        aria-label="Dismiss cookie notice"
        className="absolute right-3 top-3 rounded-lg p-1 text-text-secondary hover:bg-surface-active hover:text-text-primary transition-colors"
      >
        <X size={14} />
      </button>

      <p className="pr-6 text-sm text-text-secondary leading-relaxed">
        We use essential cookies to keep you logged in. We may also use analytics cookies to
        improve the experience.{' '}
        <Link to="/cookies" className="text-green-500 underline hover:text-green-400">
          Cookie Policy
        </Link>
      </p>

      <div className="mt-3 flex gap-2">
        <button
          onClick={accept}
          className="flex-1 rounded-xl bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-500 transition-colors"
        >
          Accept all
        </button>
        <button
          onClick={dismiss}
          className="flex-1 rounded-xl border border-border-medium px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-surface-active transition-colors"
        >
          Essential only
        </button>
      </div>
    </div>
  );
}
