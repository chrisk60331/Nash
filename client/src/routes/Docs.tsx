import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

const Section = ({ id, title, children }: { id: string; title: string; children: React.ReactNode }) => (
  <section id={id} className="scroll-mt-6">
    <h2 className="mt-10 text-lg font-semibold text-text-primary border-b border-border-light pb-2">{title}</h2>
    <div className="mt-4 space-y-3">{children}</div>
  </section>
);

const Q = ({ q, children }: { q: string; children: React.ReactNode }) => (
  <div>
    <p className="font-medium text-text-primary">{q}</p>
    <div className="mt-1 text-sm text-text-secondary leading-relaxed">{children}</div>
  </div>
);

export default function Docs() {
  return (
    <div className="min-h-screen bg-surface-primary text-text-primary">
      <div className="mx-auto max-w-3xl px-6 py-12">

        {/* Header nav */}
        <div className="mb-10 flex items-center gap-4">
          <Link
            to="/c/new"
            className="flex items-center gap-1.5 text-sm text-text-secondary transition-colors hover:text-green-500"
          >
            <ArrowLeft size={16} />
            Back to Nash
          </Link>
          <span className="text-border-medium">|</span>
          <div className="flex gap-4 text-sm text-text-secondary">
            <Link to="/privacy" className="hover:text-green-500 transition-colors">Privacy</Link>
            <Link to="/terms" className="hover:text-green-500 transition-colors">Terms</Link>
            <Link to="/cookies" className="hover:text-green-500 transition-colors">Cookies</Link>
          </div>
        </div>

        <header className="mb-8 border-b border-border-light pb-6">
          <h1 className="text-3xl font-bold tracking-tight">Help & FAQ</h1>
          <p className="mt-2 text-sm text-text-secondary">
            Can't find your answer?{' '}
            <a href="mailto:support@backboard.io" className="text-green-500 hover:underline">
              Email support
            </a>
          </p>
        </header>

        {/* Jump links */}
        <nav className="mb-10 flex flex-wrap gap-x-4 gap-y-1 text-sm text-green-500">
          {[
            ['#getting-started', 'Getting Started'],
            ['#models', 'Models & Plans'],
            ['#billing', 'Billing'],
            ['#data', 'Your Data'],
            ['#account', 'Account'],
            ['#troubleshooting', 'Troubleshooting'],
          ].map(([href, label]) => (
            <a key={href} href={href} className="hover:underline">
              {label}
            </a>
          ))}
        </nav>

        <Section id="getting-started" title="Getting Started">
          <Q q="What is Nash?">
            Nash gives you access to 100+ AI models — including GPT-4o, Claude, Gemini, Llama, and
            more — through a single chat interface. You can switch models mid-conversation, compare
            responses, and save your history across devices.
          </Q>
          <Q q="How do I choose a model?">
            Click the model selector at the top of any conversation. Models are grouped by provider.
            Free-tier models are available without a subscription; faster and more powerful models
            require a Plus or Pro plan.
          </Q>
          <Q q="Is there a mobile app?">
            Not yet. Nash runs in any modern browser and is fully responsive on mobile. A native app
            is on the roadmap.
          </Q>
        </Section>

        <Section id="models" title="Models & Plans">
          <Q q="Which models are free?">
            Models from Cohere, Cerebras, and Featherless are available on the Free plan.
            GPT-4o, Claude 3.5, Gemini 1.5 Pro, and other premium models require Plus or Pro.
          </Q>
          <Q q="What counts as a token?">
            Tokens are the unit AI models use to measure text. Roughly 1 token ≈ 4 characters of
            English text. Both your input (prompt) and the model's output (response) count toward
            your monthly token allowance.
          </Q>
          <Q q="What are the plan token limits?">
            <ul className="mt-1 list-disc pl-5 space-y-1">
              <li><strong>Free</strong> — 250,000 tokens/month, free models only</li>
              <li><strong>Plus</strong> — 500,000 tokens/month, all models</li>
              <li><strong>Pro</strong> — 3,000,000 tokens/month, all models, priority access</li>
            </ul>
            Plus and Pro can optionally enable overage billing so you never hit a hard wall.
          </Q>
          <Q q="Do unused tokens roll over?">
            No. Token allowances reset at the start of each billing period.
          </Q>
        </Section>

        <Section id="billing" title="Billing">
          <Q q="How does billing work?">
            Paid plans are billed monthly in advance via Stripe. You can upgrade, downgrade, or
            cancel at any time from{' '}
            <Link to="/billing" className="text-green-500 hover:underline">
              Billing settings
            </Link>
            . Cancellations take effect at the end of the current period — you keep access until
            then.
          </Q>
          <Q q="Do you offer refunds?">
            We don't offer refunds for partial billing periods. If you believe you've been charged
            in error, contact{' '}
            <a href="mailto:support@backboard.io" className="text-green-500 hover:underline">
              support@backboard.io
            </a>{' '}
            within 7 days.
          </Q>
          <Q q="What payment methods do you accept?">
            All major credit and debit cards via Stripe. We don't accept PayPal, crypto, or
            invoicing at this time.
          </Q>
          <Q q="I was referred by a friend — where's my credit?">
            Referral credits are applied automatically when your friend's first paid subscription
            goes through. Check your balance in{' '}
            <Link to="/billing" className="text-green-500 hover:underline">
              Billing
            </Link>
            .
          </Q>
        </Section>

        <Section id="data" title="Your Data">
          <Q q="Do you use my conversations to train AI models?">
            No. Your conversation content is never used to train AI models — by Nash or any of our
            underlying model providers under our agreements.
          </Q>
          <Q q="Where is my data stored?">
            Your account data and conversation history are stored securely on Backboard.io
            infrastructure, hosted in AWS (US region). See our{' '}
            <Link to="/privacy" className="text-green-500 hover:underline">
              Privacy Policy
            </Link>{' '}
            for details.
          </Q>
          <Q q="How do I delete my conversation history?">
            Go to{' '}
            <Link to="/settings/data-controls" className="text-green-500 hover:underline">
              Settings → Data Controls
            </Link>{' '}
            and click <strong>Delete all conversations</strong>. This is immediate and permanent.
          </Q>
          <Q q="How do I delete my account?">
            Account deletion removes all your data from our systems within 30 days, including
            conversation history, profile, and billing records (except what we're legally required
            to retain). To request account deletion, email{' '}
            <a href="mailto:support@backboard.io" className="text-green-500 hover:underline">
              support@backboard.io
            </a>
            .
          </Q>
          <Q q="Can I export my data?">
            Data export is coming soon. In the meantime, contact{' '}
            <a href="mailto:support@backboard.io" className="text-green-500 hover:underline">
              support@backboard.io
            </a>{' '}
            and we'll provide an export manually.
          </Q>
        </Section>

        <Section id="account" title="Account">
          <Q q="How do I change my password?">
            Password reset is coming soon. For now, contact{' '}
            <a href="mailto:support@backboard.io" className="text-green-500 hover:underline">
              support@backboard.io
            </a>{' '}
            and we'll reset it manually.
          </Q>
          <Q q="Can I change my email address?">
            Not yet via self-service. Email{' '}
            <a href="mailto:support@backboard.io" className="text-green-500 hover:underline">
              support@backboard.io
            </a>{' '}
            with your current and new email address.
          </Q>
          <Q q="I signed up with Google. Can I also set a password?">
            Not currently — Google and email/password accounts are separate. If you'd like to
            migrate, contact support.
          </Q>
        </Section>

        <Section id="troubleshooting" title="Troubleshooting">
          <Q q="A model isn't responding / I'm getting errors.">
            Check the{' '}
            <a
              href="https://crimson-rabbit-6111.statusgator.app"
              target="_blank"
              rel="noreferrer"
              className="text-green-500 hover:underline"
            >
              status page
            </a>{' '}
            for any known outages. If the status page shows all systems operational, try refreshing
            the page. If the problem persists, email{' '}
            <a href="mailto:support@backboard.io" className="text-green-500 hover:underline">
              support@backboard.io
            </a>{' '}
            with the model name and a description of the error.
          </Q>
          <Q q="My token balance looks wrong.">
            Token counts update in near-real-time. If you think there's a discrepancy, email
            support with the conversation ID (visible in the URL) and the date/time of the request.
          </Q>
          <Q q="I'm being logged out unexpectedly.">
            Sessions expire after 15 minutes of inactivity. If you're being logged out much sooner,
            check that cookies are enabled in your browser and that no browser extension is blocking
            them.
          </Q>
          <Q q="Something else isn't working.">
            Email{' '}
            <a href="mailto:support@backboard.io" className="text-green-500 hover:underline">
              support@backboard.io
            </a>{' '}
            — include your browser, OS, and a description of the issue.
          </Q>
        </Section>

        <footer className="mt-16 border-t border-border-light pt-6 text-center text-xs text-text-secondary">
          <p>© {new Date().getFullYear()} Backboard.io, Inc. — Nash</p>
          <div className="mt-2 flex justify-center gap-4">
            <Link to="/privacy" className="hover:text-green-500 transition-colors">Privacy</Link>
            <Link to="/terms" className="hover:text-green-500 transition-colors">Terms</Link>
            <Link to="/cookies" className="hover:text-green-500 transition-colors">Cookies</Link>
            <a href="mailto:support@backboard.io" className="hover:text-green-500 transition-colors">Contact</a>
          </div>
        </footer>

      </div>
    </div>
  );
}
