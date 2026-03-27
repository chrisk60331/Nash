import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Sparkles, ArrowRight, Play, Zap, Shield, Brain, Users } from 'lucide-react';
import { useGetStartupConfig } from '~/data-provider';

const YOUTUBE_ID = 'CerDLYA27NA';

function VideoModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl aspect-video rounded-2xl overflow-hidden shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <iframe
          src={`https://www.youtube.com/embed/${YOUTUBE_ID}?autoplay=1&rel=0`}
          title="Nash demo"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          className="absolute inset-0 w-full h-full"
        />
        <button
          onClick={onClose}
          className="absolute top-3 right-3 z-10 flex h-8 w-8 items-center justify-center rounded-full bg-black/60 text-white text-lg leading-none hover:bg-black/80 transition-colors"
          aria-label="Close video"
        >
          ×
        </button>
      </div>
    </div>
  );
}

const features = [
  {
    icon: Brain,
    title: 'Every top AI model',
    desc: 'GPT-4o, Claude, Gemini, Grok — one interface to rule them all.',
  },
  {
    icon: Zap,
    title: 'Instant agents',
    desc: 'Deploy purpose-built AI agents for any workflow in minutes.',
  },
  {
    icon: Shield,
    title: 'Enterprise-grade',
    desc: 'Guardrails, audit logs, and SSO ready out of the box.',
  },
  {
    icon: Users,
    title: 'Built for teams',
    desc: 'Shared memory, agent marketplace, and team rollout tools.',
  },
];

export default function Landing() {
  const [videoOpen, setVideoOpen] = useState(false);
  const { data: startupConfig } = useGetStartupConfig();
  const appTitle = startupConfig?.appTitle ?? 'Nash';

  return (
    <div className="relative min-h-screen overflow-hidden bg-surface-primary text-text-primary">
      {/* Background blobs */}
      <div className="pointer-events-none absolute -top-40 -right-40 h-[500px] w-[500px] rounded-full bg-bb-blue/10 blur-[100px] dark:bg-bb-blue/15" />
      <div className="pointer-events-none absolute top-1/3 -left-32 h-[400px] w-[400px] rounded-full bg-green-500/8 blur-[80px] dark:bg-green-500/12" />
      <div className="pointer-events-none absolute bottom-0 right-1/4 h-[350px] w-[350px] rounded-full bg-bb-steel/20 blur-[90px] dark:bg-bb-steelDark/30" />

      {/* Nav */}
      <header className="relative z-10 mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2.5">
          <img
            src="assets/nash.png"
            className="h-8 w-auto object-contain dark:hidden"
            alt={appTitle}
          />
          <img
            src="assets/nash_dark.png"
            className="hidden h-8 w-auto object-contain dark:block"
            alt={appTitle}
          />
        </div>
        <div className="flex items-center gap-3">
          <Link
            to="/login"
            className="text-sm font-medium text-text-secondary transition-colors hover:text-text-primary"
          >
            Sign in
          </Link>
          <Link
            to="/preview"
            className="inline-flex items-center gap-1.5 rounded-xl bg-green-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-all hover:bg-green-700 active:scale-[0.97]"
          >
            Try free
            <ArrowRight size={14} />
          </Link>
        </div>
      </header>

      {/* Hero */}
      <main className="relative z-10 mx-auto max-w-6xl px-6 pt-16 pb-24 text-center">
        {/* Pill badge */}
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-bb-blue/30 bg-bb-blue/10 px-3.5 py-1.5 text-xs font-semibold text-bb-blue dark:bg-bb-blue/20 dark:text-white">
          <Sparkles size={12} />
          The AI workspace for teams that ship
        </div>

        <h1 className="mx-auto max-w-3xl text-5xl font-extrabold leading-[1.1] tracking-tight text-text-primary sm:text-6xl md:text-7xl">
          One AI workspace.{' '}
          <span className="bg-gradient-to-r from-green-500 to-bb-blue bg-clip-text text-transparent">
            Every model.
          </span>
        </h1>

        <p className="mx-auto mt-6 max-w-xl text-lg leading-7 text-text-secondary">
          Nash gives your team a single, powerful home for AI — built on the best models, with
          agents, memory, and guardrails baked in.
        </p>

        {/* CTAs */}
        <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
          <Link
            to="/preview"
            className="group inline-flex items-center gap-2 rounded-2xl bg-green-600 px-7 py-3.5 text-base font-semibold text-white shadow-lg shadow-green-600/20 transition-all hover:bg-green-700 hover:shadow-green-600/30 active:scale-[0.97]"
          >
            Try it free
            <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" />
          </Link>

          <button
            onClick={() => setVideoOpen(true)}
            className="group inline-flex items-center gap-2.5 rounded-2xl border border-border-medium bg-surface-secondary/60 px-7 py-3.5 text-base font-semibold text-text-primary backdrop-blur-sm transition-all hover:border-green-500/50 hover:bg-surface-secondary active:scale-[0.97]"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-green-600/15 text-green-600 transition-colors group-hover:bg-green-600/25">
              <Play size={13} className="translate-x-0.5" fill="currentColor" />
            </span>
            Watch it live
          </button>
        </div>

        {/* Video thumbnail / preview card */}
        <div className="mx-auto mt-16 max-w-3xl">
          <button
            onClick={() => setVideoOpen(true)}
            className="group relative w-full overflow-hidden rounded-2xl border border-border-light shadow-2xl shadow-black/20 transition-transform hover:-translate-y-1 hover:shadow-black/30 focus:outline-none"
            aria-label="Watch Nash demo video"
          >
            {/* YouTube thumbnail */}
            <img
              src={`https://img.youtube.com/vi/${YOUTUBE_ID}/maxresdefault.jpg`}
              alt="Nash demo preview"
              className="w-full object-cover"
              onError={(e) => {
                // Fall back to hqdefault if maxresdefault isn't available
                (e.target as HTMLImageElement).src = `https://img.youtube.com/vi/${YOUTUBE_ID}/hqdefault.jpg`;
              }}
            />
            {/* Overlay */}
            <div className="absolute inset-0 flex items-center justify-center bg-black/30 transition-colors group-hover:bg-black/20">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-white/90 shadow-lg transition-transform group-hover:scale-110">
                <Play size={24} className="translate-x-1 text-green-600" fill="currentColor" />
              </div>
            </div>
            {/* Duration/label badge */}
            <div className="absolute bottom-3 right-3 rounded-lg bg-black/70 px-2.5 py-1 text-xs font-medium text-white backdrop-blur-sm">
              Watch demo
            </div>
          </button>
        </div>

        {/* Feature grid */}
        <div className="mx-auto mt-24 grid max-w-4xl gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {features.map(({ icon: Icon, title, desc }) => (
            <div
              key={title}
              className="group rounded-2xl border border-border-light bg-surface-secondary/50 p-5 text-left backdrop-blur-sm transition-all hover:-translate-y-0.5 hover:border-green-500/30 hover:bg-surface-secondary hover:shadow-md"
            >
              <div className="mb-3 inline-flex h-9 w-9 items-center justify-center rounded-xl bg-green-600/10 text-green-600 transition-colors group-hover:bg-green-600/15">
                <Icon size={18} />
              </div>
              <h3 className="mb-1 text-sm font-semibold text-text-primary">{title}</h3>
              <p className="text-xs leading-5 text-text-secondary">{desc}</p>
            </div>
          ))}
        </div>

        {/* Bottom CTA strip */}
        <div className="mx-auto mt-20 max-w-2xl rounded-2xl border border-border-light bg-gradient-to-br from-bb-blue/10 via-surface-secondary/60 to-green-500/10 p-8">
          <h2 className="text-2xl font-bold text-text-primary">Ready to get started?</h2>
          <p className="mt-2 text-sm text-text-secondary">
            No credit card required. Start chatting with the world's best AI models in seconds.
          </p>
          <div className="mt-6 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
            <Link
              to="/preview"
              className="inline-flex items-center gap-2 rounded-2xl bg-green-600 px-7 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-green-700 active:scale-[0.97]"
            >
              Try it free — no signup needed
              <ArrowRight size={14} />
            </Link>
            <Link
              to="/register"
              className="inline-flex items-center gap-2 rounded-2xl border border-border-medium bg-surface-primary px-7 py-3 text-sm font-medium text-text-secondary transition-all hover:border-green-500/40 hover:text-text-primary active:scale-[0.97]"
            >
              Create account
            </Link>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-border-light px-6 py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-4 sm:flex-row sm:justify-between">
          <img
            src="assets/nash.png"
            className="h-6 w-auto object-contain dark:hidden"
            alt={appTitle}
          />
          <img
            src="assets/nash_dark.png"
            className="hidden h-6 w-auto object-contain dark:block"
            alt={appTitle}
          />
          <div className="flex items-center gap-6 text-xs text-text-tertiary">
            <Link to="/privacy" className="transition-colors hover:text-text-secondary">Privacy</Link>
            <Link to="/terms" className="transition-colors hover:text-text-secondary">Terms</Link>
            <Link to="/docs" className="transition-colors hover:text-text-secondary">Docs</Link>
            <Link to="/enterprise" className="transition-colors hover:text-text-secondary">Enterprise</Link>
          </div>
        </div>
      </footer>

      {videoOpen && <VideoModal onClose={() => setVideoOpen(false)} />}
    </div>
  );
}
