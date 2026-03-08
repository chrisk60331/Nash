import LegalLayout from './LegalLayout';

export default function Cookies() {
  return (
    <LegalLayout title="Cookie Policy" lastUpdated="March 8, 2026">
      <p>
        This Cookie Policy explains how Nash (operated by Backboard.io, Inc.) uses cookies and
        similar technologies when you use our Service at nash.backboard.io.
      </p>

      <h2>1. What Are Cookies?</h2>
      <p>
        Cookies are small text files placed on your device by websites you visit. They are widely
        used to make websites work efficiently and to provide information to site owners. Similar
        technologies include local storage and session storage, which we also use.
      </p>

      <h2>2. Cookies We Use</h2>

      <h3>Strictly Necessary Cookies</h3>
      <p>
        These cookies are essential for the Service to function and cannot be disabled. Without
        them, features like logging in and maintaining your session are not possible.
      </p>
      <ul>
        <li>
          <strong>refreshToken</strong> — An HttpOnly, Secure cookie that stores your
          authentication refresh token. Expires after 14 days. This cookie is never accessible
          to JavaScript.
        </li>
        <li>
          <strong>nash_cookie_consent</strong> — Stores your cookie consent preference so we
          don't ask you again. Persists for 1 year.
        </li>
      </ul>

      <h3>Functional Cookies / Local Storage</h3>
      <p>
        These are used to remember your preferences and improve your experience. They are stored
        in your browser's local storage (not sent to our server on every request).
      </p>
      <ul>
        <li>
          <strong>Theme preference</strong> — Stores your light/dark mode preference
        </li>
        <li>
          <strong>navVisible</strong> — Remembers whether the sidebar is open or closed
        </li>
        <li>
          <strong>Font size settings</strong> — Stores your preferred text size
        </li>
        <li>
          <strong>Last viewed conversation</strong> — Used to restore your session
        </li>
      </ul>

      <h3>Analytics Cookies</h3>
      <p>
        We may use Google Tag Manager (GTM) to collect anonymous usage analytics to understand
        how users interact with the Service. When active, GTM may set cookies on Google's behalf.
        This data is aggregated and not tied to your identity.
      </p>
      <p>
        Analytics cookies are only activated if you accept non-essential cookies. You can
        withdraw consent at any time via the cookie settings link in the footer.
      </p>

      <h2>3. Third-Party Cookies</h2>
      <p>
        Nash does not serve third-party advertising cookies. When you use our Service, AI model
        providers (OpenAI, Anthropic, Google, etc.) receive your message content to generate
        responses — but this happens via server-to-server API calls, not via cookies in your
        browser.
      </p>
      <p>
        Payment pages powered by Stripe may set their own cookies in accordance with{' '}
        <a href="https://stripe.com/privacy" target="_blank" rel="noreferrer">
          Stripe's Privacy Policy
        </a>
        .
      </p>

      <h2>4. Managing Cookies</h2>
      <p>
        You can control cookies through your browser settings. Most browsers allow you to:
      </p>
      <ul>
        <li>View what cookies are set and delete them</li>
        <li>Block all or specific cookies</li>
        <li>Set preferences for specific websites</li>
      </ul>
      <p>
        Note: disabling strictly necessary cookies (such as the authentication cookie) will
        prevent you from staying logged in to Nash.
      </p>
      <p>Browser-specific guidance:</p>
      <ul>
        <li>
          <a href="https://support.google.com/chrome/answer/95647" target="_blank" rel="noreferrer">
            Google Chrome
          </a>
        </li>
        <li>
          <a href="https://support.mozilla.org/en-US/kb/enhanced-tracking-protection-firefox-desktop" target="_blank" rel="noreferrer">
            Mozilla Firefox
          </a>
        </li>
        <li>
          <a href="https://support.apple.com/guide/safari/manage-cookies-sfri11471/mac" target="_blank" rel="noreferrer">
            Apple Safari
          </a>
        </li>
        <li>
          <a href="https://support.microsoft.com/en-us/microsoft-edge/delete-cookies-in-microsoft-edge-63947406-40ac-c3b8-57b9-2a946a29ae09" target="_blank" rel="noreferrer">
            Microsoft Edge
          </a>
        </li>
      </ul>

      <h2>5. Changes to This Policy</h2>
      <p>
        We may update this Cookie Policy when we add or change cookie usage. Updates will be
        reflected in the "Last updated" date above.
      </p>

      <h2>6. Contact</h2>
      <p>
        Questions about our cookie practices? Contact{' '}
        <a href="mailto:privacy@nash.ai">privacy@nash.ai</a>.
      </p>
    </LegalLayout>
  );
}
