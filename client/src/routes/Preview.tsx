import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  BookOpen,
  Check,
  ChevronDown,

  ChevronsUpDown,
  Clock3,
  Lock,
  Menu,
  MessageSquareText,
  PanelLeft,
  Paperclip,
  Pencil,
  Play,
  Plus,
  Search,
  Sparkles,
  Star,
  Trash2,
  Upload,
  Wand2,
} from 'lucide-react';
import {
  Button,
  OGDialog,
  OGDialogContent,
  OGDialogDescription,
  OGDialogTitle,
} from '@librechat/client';
import { useGetStartupConfig } from '~/data-provider';
import { useGetModelsQuery } from 'librechat-data-provider/react-query';
import { useAuthContext } from '~/hooks/AuthContext';
import LoginForm from '~/components/Auth/LoginForm';
import SocialLoginRender from '~/components/Auth/SocialLoginRender';
import RegistrationForm from '~/components/Auth/RegistrationForm';
import { readPendingChatDraft, savePendingChatDraft } from '~/utils/auth/pendingChat';
import EnterpriseUpsellCard from '~/components/SidePanel/EnterpriseUpsellCard';

type AuthTab = 'login' | 'register';

type PreviewOption = {
  key: string;
  label: string;
  subtitle: string;
  endpoint?: string;
  spec?: string;
  modelLabel?: string;
};

type PreviewModelEntry = {
  key: string;
  endpoint: string;
  model: string;
  label: string;
  subtitle: string;
};

const YOUTUBE_ID = 'CerDLYA27NA';

const previewChats = [
  'Resolving Top-Level Package Error',
  "Casual Check-In: How's Everything Going?",
  'Email Draft for Sales Lead Outreach',
  'Friendly Greeting Exchange',
  'Omni Dog ASCII Art Guide',
];

const fakeMemories = [
  {
    key: 'interest_deep_history',
    tokens: 16,
    date: 'Mar 5, 2026',
    value:
      'interest_deep_history: Interested in ancient/medieval history topics (crusades-era dynamics, castles, weapons realism, pants invention, early language evidence)',
  },
  {
    key: 'prefers_surgical_edits',
    tokens: 10,
    date: 'Mar 5, 2026',
    value:
      'prefers_surgical_edits: Wants the simplest fix first, with small focused changes and logic kept in the API.',
  },
  {
    key: 'ui_stack_preference',
    tokens: 12,
    date: 'Mar 4, 2026',
    value:
      'ui_stack_preference: Prefers node + shadcn-ui/ui + tailwind css for frontend and many small components over large pages.',
  },
];

function buildPreviewOptions(
  modelsData: Record<string, Array<{ name: string; tiers?: string[] }>> | undefined,
): PreviewOption[] {
  if (!modelsData) {
    return [];
  }

  return Object.entries(modelsData)
    .filter(
      ([endpoint, models]) =>
        endpoint.toLowerCase() !== 'agents' && Array.isArray(models) && models.length > 0,
    )
    .map(([endpoint, models]) => {
      const modelCount = models.length;
      const sampleModels = models
        .slice(0, 2)
        .map((model) => model.name)
        .join(' • ');

      return {
        key: `endpoint:${endpoint}`,
        label: endpoint,
        subtitle:
          sampleModels.length > 0
            ? `${modelCount.toLocaleString()} models • ${sampleModels}`
            : `${modelCount.toLocaleString()} models`,
        endpoint,
        modelLabel: endpoint,
      };
    });
}

function buildPreviewModelEntries(
  modelsData: Record<string, Array<{ name: string; tiers?: string[] }>> | undefined,
): PreviewModelEntry[] {
  if (!modelsData) {
    return [];
  }

  return Object.entries(modelsData).flatMap(([endpoint, models]) =>
    endpoint.toLowerCase() === 'agents'
      ? []
      : (Array.isArray(models) ? models : []).slice(0, 24).map((model) => {
      const tiers =
        Array.isArray(model?.tiers) && model.tiers.length > 0
          ? ` • ${model.tiers.join(', ')}`
          : '';

      return {
        key: `model:${endpoint}:${model.name}`,
        endpoint,
        model: model.name,
        label: model.name,
        subtitle: `${endpoint}${tiers}`,
      };
    }),
  );
}

function VideoModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-[90] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative aspect-video w-full max-w-5xl overflow-hidden rounded-2xl border border-border-light bg-black shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <iframe
          src={`https://www.youtube.com/embed/${YOUTUBE_ID}?autoplay=1&rel=0`}
          title="Nash live demo"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          className="absolute inset-0 h-full w-full"
        />
        <button
          type="button"
          onClick={onClose}
          className="absolute right-3 top-3 z-10 flex h-9 w-9 items-center justify-center rounded-full bg-black/60 text-lg leading-none text-white transition-colors hover:bg-black/80"
          aria-label="Close video"
        >
          ×
        </button>
      </div>
    </div>
  );
}

function PreviewAuthModal({
  open,
  onOpenChange,
  tab,
  onTabChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tab: AuthTab;
  onTabChange: (tab: AuthTab) => void;
}) {
  const { error, setError, login } = useAuthContext();
  const { data: startupConfig } = useGetStartupConfig();

  if (!startupConfig) {
    return null;
  }

  return (
    <OGDialog open={open} onOpenChange={onOpenChange}>
      <OGDialogContent className="w-full max-w-md border-border-light bg-surface-primary px-6 py-6 text-text-primary">
        <OGDialogTitle className="sr-only">
          {tab === 'login' ? 'Sign in to continue' : 'Create your account'}
        </OGDialogTitle>
        <OGDialogDescription className="sr-only">
          Continue into the full Nash workspace and send your preview message.
        </OGDialogDescription>

        <div className="mb-5 flex flex-col items-center gap-1">
          <img
            src="assets/nash.png"
            className="h-8 w-auto object-contain dark:hidden"
            alt="Nash"
          />
          <img
            src="assets/nash_dark.png"
            className="hidden h-8 w-auto object-contain dark:block"
            alt="Nash"
          />
          <p className="mt-1.5 text-xs text-text-secondary">
            {tab === 'login'
              ? 'Sign in and we’ll continue your message in full chat'
              : 'Create your account and we’ll send your message instantly'}
          </p>
        </div>

        {startupConfig.registrationEnabled && (
          <div className="mb-5 flex rounded-xl border border-border-light bg-surface-secondary/50 p-1">
            <button
              type="button"
              onClick={() => onTabChange('login')}
              className={`flex-1 rounded-lg py-1.5 text-sm font-medium transition-colors ${
                tab === 'login'
                  ? 'bg-surface-primary text-text-primary shadow-sm'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              Sign in
            </button>
            <button
              type="button"
              onClick={() => onTabChange('register')}
              className={`flex-1 rounded-lg py-1.5 text-sm font-medium transition-colors ${
                tab === 'register'
                  ? 'bg-surface-primary text-text-primary shadow-sm'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              Sign up
            </button>
          </div>
        )}

        {tab === 'login' ? (
          <LoginForm
            onSubmit={login}
            startupConfig={startupConfig}
            error={error}
            setError={setError}
          />
        ) : (
          <RegistrationForm startupConfig={startupConfig} />
        )}

        <SocialLoginRender startupConfig={startupConfig} />
      </OGDialogContent>
    </OGDialog>
  );
}

function LeftRail({ onOpenSignup }: { onOpenSignup: () => void }) {
  return (
    <aside className="hidden h-full w-[248px] shrink-0 border-r border-border-light bg-[#171717] text-white lg:flex">
      <div className="relative flex h-full w-full flex-col">
        <div className="flex items-center justify-between px-4 py-4">
          <div className="flex items-center gap-3">
            <PanelLeft size={18} className="text-white/80" />
            <img
              src="assets/nash_dark.png"
              className="h-7 w-auto object-contain"
              alt="Nash"
            />
          </div>
          <div className="flex items-center gap-2 text-white/75">
            <Star size={16} />
            <Wand2 size={16} />
          </div>
        </div>

        <div className="px-3">
          <button
            type="button"
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm text-white/85 transition-colors hover:bg-white/5"
          >
            <Search size={16} />
            Search messages
          </button>
          <button
            type="button"
            className="mt-1 flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm text-white/85 transition-colors hover:bg-white/5"
          >
            <Sparkles size={16} />
            Persona Marketplace
          </button>
        </div>

        <div className="mt-5 px-4">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-white/35">
            Chats
          </div>
          <div className="space-y-1">
            {previewChats.map((chat, index) => (
              <button
                key={chat}
                type="button"
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm transition-colors ${
                  index === 0
                    ? 'bg-white/10 text-white'
                    : 'text-white/75 hover:bg-white/5 hover:text-white'
                }`}
              >
                <MessageSquareText size={16} className="shrink-0" />
                <span className="truncate">{chat}</span>
              </button>
            ))}
          </div>
        </div>

        <button
          type="button"
          onClick={onOpenSignup}
          className="absolute inset-0"
          aria-label="Open signup from left drawer"
        />
      </div>
    </aside>
  );
}

function TopBar({
  options,
  modelEntries,
  selectedOption,
  selectedModelEntry,
  onSelectOption,
  onSelectModelEntry,
  onWatchLive,
}: {
  options: PreviewOption[];
  modelEntries: PreviewModelEntry[];
  selectedOption: PreviewOption | null;
  selectedModelEntry: PreviewModelEntry | null;
  onSelectOption: (key: string) => void;
  onSelectModelEntry: (entry: PreviewModelEntry) => void;
  onWatchLive: () => void;
}) {
  return (
    <div className="sticky top-0 z-20 border-b border-border-light bg-[#212121]/95 px-3 py-3 backdrop-blur-sm sm:px-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-white">
          <button
            type="button"
            className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/5 transition-colors hover:bg-white/10 lg:hidden"
          >
            <Menu size={18} />
          </button>
          <PreviewModelSelector
            options={options}
            modelEntries={modelEntries}
            selectedOption={selectedOption}
            selectedModelEntry={selectedModelEntry}
            onSelectOption={onSelectOption}
            onSelectModelEntry={onSelectModelEntry}
          />
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onWatchLive}
            className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-white/10"
          >
            <Play size={14} />
            Watch it live
          </button>
          <Link
            to="/"
            className="inline-flex items-center rounded-xl px-3 py-2 text-sm font-medium text-white/75 transition-colors hover:bg-white/5 hover:text-white"
          >
            Back home
          </Link>
        </div>
      </div>
    </div>
  );
}

function RightPanel({ onOpenSignup }: { onOpenSignup: () => void }) {
  const [memoryExpanded, setMemoryExpanded] = useState(true);
  const [useMemory, setUseMemory] = useState(true);

  return (
    <aside className="hidden h-full w-[360px] shrink-0 border-l border-border-light bg-[#212121] text-white xl:flex">
      <div className="relative flex h-full w-full flex-col gap-4 px-3 py-3">
        <div className="rounded-2xl border border-white/10 bg-[#171717] p-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <BookOpen size={16} className="text-white/75" />
            Memories
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-[#171717] p-3">
          <div className="flex items-center gap-2">
            <div className="min-w-0 flex-1 rounded-xl border border-white/10 bg-[#111111] px-3 py-2.5 text-sm text-white/45">
              Filter memories...
            </div>
            <button
              type="button"
              className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-transparent text-white/75 transition-colors hover:bg-white/5 hover:text-white"
              aria-label="Import memories"
              tabIndex={-1}
            >
              <Upload size={16} />
            </button>
            <button
              type="button"
              className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-transparent text-white/75 transition-colors hover:bg-white/5 hover:text-white"
              aria-label="Add memory"
              tabIndex={-1}
            >
              <Plus size={16} />
            </button>
          </div>

          <div className="mt-4 flex items-center gap-3">
            <span className="text-sm text-white/80">Use memory</span>
            <button
              type="button"
              onClick={() => setUseMemory((current) => !current)}
              className={`inline-flex h-7 w-12 items-center rounded-full transition-colors ${
                useMemory ? 'bg-white' : 'bg-white/20'
              }`}
              aria-pressed={useMemory}
              aria-label="Toggle memory"
              tabIndex={-1}
            >
              <span
                className={`inline-block h-5 w-5 transform rounded-full bg-[#171717] transition-transform ${
                  useMemory ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

        </div>

        <div className="relative min-h-0 flex-1 overflow-hidden rounded-2xl border border-white/10 bg-[#171717]">
          <button
            type="button"
            onClick={onOpenSignup}
            className="relative z-10 flex w-full items-center justify-between border-b border-white/10 px-4 py-3 text-left transition-colors hover:bg-white/5"
          >
            <div className="text-sm font-medium text-white">Saved memories</div>
            <ChevronsUpDown size={16} className="text-white/55" />
          </button>

          {memoryExpanded && (
            <div className="flex max-h-full flex-col gap-3 overflow-y-auto p-3">
              {fakeMemories.map((memory) => (
                <div
                  key={memory.key}
                  className="rounded-2xl border border-white/10 bg-transparent p-4"
                >
                  <div className="flex items-start gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="text-xs text-white/55">
                        {memory.tokens} tokens&nbsp;&nbsp;{memory.date}
                      </div>
                    </div>
                    <div className="flex items-center gap-1 text-white/60">
                      <button
                        type="button"
                        className="inline-flex h-8 w-8 items-center justify-center rounded-lg transition-colors hover:bg-white/5 hover:text-white"
                        aria-label={`Edit ${memory.key}`}
                        tabIndex={-1}
                      >
                        <Pencil size={14} />
                      </button>
                      <button
                        type="button"
                        className="inline-flex h-8 w-8 items-center justify-center rounded-lg transition-colors hover:bg-white/5 hover:text-white"
                        aria-label={`Delete ${memory.key}`}
                        tabIndex={-1}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                  <div className="mt-3 text-left text-[15px] leading-7 text-white">
                    {memory.value}
                  </div>
                </div>
              ))}
            </div>
          )}

          <button
            type="button"
            onClick={onOpenSignup}
            className="absolute inset-0 rounded-2xl"
            aria-label="Open signup to use right drawer"
          />
        </div>

        <EnterpriseUpsellCard className="relative z-10 shrink-0 bg-gradient-to-br from-bb-blue/15 via-[#171717] to-bb-steel/20" />
      </div>
    </aside>
  );
}

function PreviewModelSelector({
  options,
  modelEntries,
  selectedOption,
  selectedModelEntry,
  onSelectOption,
  onSelectModelEntry,
}: {
  options: PreviewOption[];
  modelEntries: PreviewModelEntry[];
  selectedOption: PreviewOption | null;
  selectedModelEntry: PreviewModelEntry | null;
  onSelectOption: (key: string) => void;
  onSelectModelEntry: (entry: PreviewModelEntry) => void;
}) {
  const [open, setOpen] = useState(false);

  const entriesForSelectedProvider = useMemo(() => {
    if (!selectedOption?.endpoint) {
      return [];
    }

    return modelEntries.filter((entry) => entry.endpoint === selectedOption.endpoint);
  }, [modelEntries, selectedOption?.endpoint]);

  return (
    <div className="relative hidden lg:flex">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white transition-colors hover:bg-white/10"
      >
        <Lock size={14} className="text-white/65" />
        <span className="max-w-[320px] truncate">
          {selectedModelEntry?.label ?? selectedOption?.label ?? 'Choose a model'}
        </span>
        <ChevronDown
          size={14}
          className={`text-white/55 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <div className="absolute left-0 top-[calc(100%+10px)] z-30 w-[720px] overflow-hidden rounded-2xl border border-white/10 bg-[#1d1d1d] p-2 shadow-2xl shadow-black/30">
          <div className="border-b border-white/10 px-3 py-3">
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-white/40">
              Choose provider and model
            </div>
            <div className="mt-1 text-sm text-white/60">
              Fast open menu with provider-first selection.
            </div>
          </div>

          <div className="grid grid-cols-[220px_minmax(0,1fr)] gap-2 p-2">
            <div className="max-h-[480px] overflow-y-auto rounded-xl border border-white/10 bg-[#181818] p-2">
              <div className="mb-2 px-2 text-xs font-semibold uppercase tracking-[0.18em] text-white/35">
                Providers
              </div>
              <div className="space-y-1">
                {options.map((option) => {
                  const isSelected = option.key === selectedOption?.key;
                  const count = modelEntries.filter((entry) => entry.endpoint === option.endpoint).length;

                  return (
                    <button
                      key={option.key}
                      type="button"
                      onClick={() => onSelectOption(option.key)}
                      className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition-colors ${
                        isSelected
                          ? 'bg-white/10 text-white'
                          : 'text-white/75 hover:bg-white/5 hover:text-white'
                      }`}
                    >
                      <span className="truncate">{option.label}</span>
                      <span className="ml-2 shrink-0 text-xs text-white/40">{count}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="max-h-[480px] overflow-y-auto rounded-xl border border-white/10 bg-[#181818] p-2">
              {entriesForSelectedProvider.length === 0 ? (
                <div className="px-3 py-8 text-sm text-white/50">No models available for this provider.</div>
              ) : (
                <div className="space-y-1">
                  {entriesForSelectedProvider.map((entry) => {
                    const isSelected = entry.key === selectedModelEntry?.key;

                    return (
                      <button
                        key={entry.key}
                        type="button"
                        onClick={() => {
                          onSelectModelEntry(entry);
                          setOpen(false);
                        }}
                        className={`w-full rounded-xl border px-3 py-3 text-left transition-all ${
                          isSelected
                            ? 'border-green-500 bg-green-500/10'
                            : 'border-white/10 bg-[#212121] hover:border-green-500/35'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="truncate text-sm font-semibold text-white">{entry.label}</div>
                            <div className="mt-1 text-xs leading-5 text-white/55">{entry.subtitle}</div>
                          </div>
                          <div
                            className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${
                              isSelected
                                ? 'border-green-500 bg-green-500 text-white'
                                : 'border-white/20 text-transparent'
                            }`}
                          >
                            <Check size={12} />
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CenterPanel({
  options,
  modelEntries,
  selectedOption,
  selectedModelEntry,
  draft,
  onSelect,
  onSelectModelEntry,
  onDraftChange,
  onSubmit,
  onWatchLive,
  onOpenSignup,
}: {
  options: PreviewOption[];
  modelEntries: PreviewModelEntry[];
  selectedOption: PreviewOption | null;
  selectedModelEntry: PreviewModelEntry | null;
  draft: string;
  onSelect: (key: string) => void;
  onSelectModelEntry: (entry: PreviewModelEntry) => void;
  onDraftChange: (value: string) => void;
  onSubmit: () => void;
  onWatchLive: () => void;
  onOpenSignup: () => void;
}) {
  const canSubmit = draft.trim().length > 0 && selectedOption != null;
  const messagePlaceholder = `Message ${selectedModelEntry?.label ?? selectedOption?.label ?? 'GPT-5.4'}`;

  return (
    <main className="flex min-w-0 flex-1 flex-col bg-[#212121] text-white">
      <TopBar
        options={options}
        modelEntries={modelEntries}
        selectedOption={selectedOption}
        selectedModelEntry={selectedModelEntry}
        onSelectOption={onSelect}
        onSelectModelEntry={onSelectModelEntry}
        onWatchLive={onWatchLive}
      />

      <div className="flex min-h-0 flex-1">
        <div className="flex min-h-0 flex-1 flex-col xl:flex-row">
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="flex min-h-0 flex-1 flex-col">
              <div className="flex flex-1 items-center justify-center px-6 pb-10 pt-16 sm:px-10">
                <div className="w-full max-w-5xl">
                  <div className="mx-auto flex max-w-3xl flex-col items-center text-center">


                    <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-6xl">
                      Good evening
                    </h1>

                    <div className="mt-10 w-full rounded-[30px] border border-white/10 bg-[#2f2f2f] shadow-2xl shadow-black/20">
                      <div className="p-5">
                        <textarea
                          value={draft}
                          onChange={(event) => onDraftChange(event.target.value)}
                          placeholder={messagePlaceholder}
                          className="min-h-[110px] w-full resize-none bg-transparent text-base text-white placeholder:text-white/45 focus:outline-none"
                        />

                        <div className="mt-4 flex flex-wrap items-center gap-2">
                          <div className="relative inline-flex items-center">
                            <div className="inline-flex items-center gap-2 rounded-full border border-blue-500/40 bg-blue-500/15 px-3 py-1.5 text-sm text-blue-100">
                              <Search size={14} />
                              Search
                            </div>
                            <button
                              type="button"
                              onClick={onOpenSignup}
                              className="absolute inset-0 rounded-full"
                              aria-label="Open signup to use search"
                            />
                          </div>
                          <div className="relative inline-flex items-center">
                            <div className="inline-flex items-center gap-2 rounded-full border border-violet-500/40 bg-violet-500/15 px-3 py-1.5 text-sm text-violet-100">
                              <Sparkles size={14} />
                              Memory Auto
                            </div>
                            <button
                              type="button"
                              onClick={onOpenSignup}
                              className="absolute inset-0 rounded-full"
                              aria-label="Open signup to use memory auto"
                            />
                          </div>
                          <div className="relative inline-flex items-center">
                            <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-sm text-white/85">
                              <Wand2 size={14} />
                              MCP Servers
                              <ChevronDown size={14} className="text-white/50" />
                            </div>
                            <button
                              type="button"
                              onClick={onOpenSignup}
                              className="absolute inset-0 rounded-full"
                              aria-label="Open signup to use MCP servers"
                            />
                          </div>
                          <div className="relative inline-flex items-center">
                            <div className="inline-flex items-center gap-2 rounded-full border border-amber-500/40 bg-amber-500/15 px-3 py-1.5 text-sm text-amber-100">
                              <Sparkles size={14} />
                              Fallback
                            </div>
                            <button
                              type="button"
                              onClick={onOpenSignup}
                              className="absolute inset-0 rounded-full"
                              aria-label="Open signup to use fallback"
                            />
                          </div>

                          <div className="ml-auto">
                            <button
                              type="button"
                              onClick={onSubmit}
                              disabled={!canSubmit}
                              className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-green-600 p-0 text-white transition-colors hover:bg-green-500 disabled:pointer-events-none disabled:opacity-50"
                              aria-label="Continue to full chat"
                            >
                              <ArrowRight className="h-4 w-4" />
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <RightPanel onOpenSignup={onOpenSignup} />
        </div>
      </div>
    </main>
  );
}

export default function Preview() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthContext();
  const { data: startupConfig } = useGetStartupConfig();
  const { data: modelsData } = useGetModelsQuery({ enabled: true, refetchOnMount: 'always' });

  const [videoOpen, setVideoOpen] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const [authTab, setAuthTab] = useState<AuthTab>('login');
  const [draft, setDraft] = useState('');

  const modelOptions = useMemo(
    () =>
      buildPreviewOptions(
        modelsData as Record<string, Array<{ name: string; tiers?: string[] }>> | undefined,
      ),
    [modelsData],
  );
  const modelEntries = useMemo(
    () =>
      buildPreviewModelEntries(
        modelsData as Record<string, Array<{ name: string; tiers?: string[] }>> | undefined,
      ),
    [modelsData],
  );
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [selectedModelKey, setSelectedModelKey] = useState<string | null>(null);

  useEffect(() => {
    if (selectedKey != null || modelOptions.length === 0) {
      return;
    }

    const pending = readPendingChatDraft();
    const pendingSpec =
      typeof pending?.conversation?.spec === 'string' ? pending.conversation.spec : null;
    const pendingEndpoint =
      typeof pending?.conversation?.endpoint === 'string' ? pending.conversation.endpoint : null;

    const matchedOption =
      modelOptions.find(
        (option) =>
          (pendingSpec && option.spec === pendingSpec) ||
          (pendingEndpoint && option.endpoint === pendingEndpoint),
      ) ?? modelOptions[0];

    setSelectedKey(matchedOption.key);
  }, [modelOptions, selectedKey]);

  useEffect(() => {
    const pending = readPendingChatDraft();
    if (pending?.text) {
      setDraft((current) => (current.length > 0 ? current : pending.text));
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }

    navigate('/c/new', { replace: true });
  }, [isAuthenticated, navigate]);

  const selectedOption =
    modelOptions.find((option) => option.key === selectedKey) ?? modelOptions[0] ?? null;
  const selectedModelEntry =
    modelEntries.find((entry) => entry.key === selectedModelKey) ?? null;

  useEffect(() => {
    if (selectedModelKey != null) {
      return;
    }

    if (selectedOption?.endpoint == null) {
      return;
    }

    const firstEntryForEndpoint = modelEntries.find((entry) => entry.endpoint === selectedOption.endpoint);
    if (firstEntryForEndpoint) {
      setSelectedModelKey(firstEntryForEndpoint.key);
    }
  }, [modelEntries, selectedModelKey, selectedOption?.endpoint]);

  const handleSubmitPreview = () => {
    if (!selectedOption || draft.trim().length === 0) {
      return;
    }

    savePendingChatDraft({
      text: draft.trim(),
      autoSend: true,
      conversation: {
        conversationId: 'new',
        spec: selectedOption.spec ?? undefined,
        endpoint: selectedModelEntry?.endpoint ?? selectedOption.endpoint ?? undefined,
        model: selectedModelEntry?.model,
        modelLabel: selectedModelEntry?.label ?? selectedOption.label,
        title: 'Preview chat',
      },
      addedConversation: null,
      savedAt: Date.now(),
    });

    setAuthTab('login');
    setAuthOpen(true);
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#171717]">
      <LeftRail
        onOpenSignup={() => {
          setAuthTab('register');
          setAuthOpen(true);
        }}
      />

      <CenterPanel
        options={modelOptions}
        modelEntries={modelEntries}
        selectedOption={selectedOption}
        selectedModelEntry={selectedModelEntry}
        draft={draft}
        onSelect={setSelectedKey}
        onSelectModelEntry={(entry) => {
          setSelectedKey(`endpoint:${entry.endpoint}`);
          setSelectedModelKey(entry.key);
        }}
        onDraftChange={setDraft}
        onSubmit={handleSubmitPreview}
        onWatchLive={() => setVideoOpen(true)}
        onOpenSignup={() => {
          setAuthTab('register');
          setAuthOpen(true);
        }}
      />

      <PreviewAuthModal
        open={authOpen}
        onOpenChange={setAuthOpen}
        tab={authTab}
        onTabChange={setAuthTab}
      />

      {videoOpen && <VideoModal onClose={() => setVideoOpen(false)} />}
    </div>
  );
}
