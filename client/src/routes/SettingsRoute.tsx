import { Link, useParams } from 'react-router-dom';
import { Command, DollarSign, MessageSquare, ChevronRight } from 'lucide-react';
import Presentation from '~/components/Chat/Presentation';
import {
  DataIcon,
  GearIcon,
  PersonalizationIcon,
  SpeechIcon,
  UserIcon,
} from '@librechat/client';
import { SettingsTabValues } from 'librechat-data-provider';
import type { TranslationKeys } from '~/hooks';
import { useGetStartupConfig } from '~/data-provider';
import {
  Account,
  Balance,
  Chat,
  Commands,
  Data,
  General,
  Personalization,
  Speech,
} from '~/components/Nav/SettingsTabs';
import PlanGate from '~/components/Nav/PlanGate';
import usePersonalizationAccess from '~/hooks/usePersonalizationAccess';
import { useLocalize } from '~/hooks';
import { cn } from '~/utils';

type SettingsSection = {
  value: SettingsTabValues;
  label: TranslationKeys;
  description: string;
  icon: React.ReactNode;
  featureName?: string;
  requiredPlan?: 'plus' | 'unlimited';
};

function SettingsOverviewCard({
  href,
  icon,
  title,
  description,
}: {
  href: string;
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <Link
      to={href}
      className="group rounded-2xl border border-border-light bg-surface-secondary/40 p-4 transition-all hover:border-border-medium hover:bg-surface-secondary"
    >
      <div className="flex items-start gap-3">
        <div className="rounded-xl border border-border-light bg-background/70 p-2 text-text-primary">
          {icon}
        </div>
        <div className="min-w-0">
          <div className="font-medium text-text-primary transition-colors group-hover:text-text-primary">
            {title}
          </div>
          <p className="mt-1 text-sm leading-5 text-text-secondary">{description}</p>
        </div>
      </div>
    </Link>
  );
}

function SettingsSectionContent({
  section,
  hasMemoryOptOut,
}: {
  section: SettingsSection;
  hasMemoryOptOut: boolean;
}) {
  let content: React.ReactNode = null;

  switch (section.value) {
    case SettingsTabValues.GENERAL:
      content = <General />;
      break;
    case SettingsTabValues.CHAT:
      content = <Chat />;
      break;
    case SettingsTabValues.COMMANDS:
      content = <Commands />;
      break;
    case SettingsTabValues.SPEECH:
      content = <Speech />;
      break;
    case SettingsTabValues.PERSONALIZATION:
      content = (
        <Personalization
          hasMemoryOptOut={hasMemoryOptOut}
          hasAnyPersonalizationFeature={true}
        />
      );
      break;
    case SettingsTabValues.DATA:
      content = <Data />;
      break;
    case SettingsTabValues.BALANCE:
      content = <Balance />;
      break;
    case SettingsTabValues.ACCOUNT:
      content = <Account />;
      break;
    default:
      content = <General />;
  }

  if (!section.requiredPlan || !section.featureName) {
    return <>{content}</>;
  }

  return (
    <PlanGate requiredPlan={section.requiredPlan} featureName={section.featureName}>
      {content}
    </PlanGate>
  );
}

export default function SettingsRoute() {
  const localize = useLocalize();
  const { tab } = useParams();
  const { data: startupConfig } = useGetStartupConfig();
  const { hasAnyPersonalizationFeature, hasMemoryOptOut } = usePersonalizationAccess();

  const sections: SettingsSection[] = [
    {
      value: SettingsTabValues.GENERAL,
      icon: <GearIcon />,
      label: 'com_nav_setting_general',
      description: 'Theme, language, and app behavior preferences.',
    },
    {
      value: SettingsTabValues.CHAT,
      icon: <MessageSquare className="h-4 w-4" aria-hidden="true" />,
      label: 'com_nav_setting_chat',
      description: 'Defaults that shape your chat experience.',
    },
    {
      value: SettingsTabValues.COMMANDS,
      icon: <Command className="h-4 w-4" aria-hidden="true" />,
      label: 'com_nav_commands',
      description: 'Create and manage reusable chat commands.',
      requiredPlan: 'plus',
      featureName: 'Commands',
    },
    {
      value: SettingsTabValues.SPEECH,
      icon: <SpeechIcon className="h-4 w-4" />,
      label: 'com_nav_setting_speech',
      description: 'Speech input and voice output settings.',
      requiredPlan: 'plus',
      featureName: 'Speech',
    },
    ...(hasAnyPersonalizationFeature
      ? [
          {
            value: SettingsTabValues.PERSONALIZATION,
            icon: <PersonalizationIcon />,
            label: 'com_nav_setting_personalization' as TranslationKeys,
            description: 'Memory and personalization controls.',
            requiredPlan: 'plus' as const,
            featureName: 'Memory & Personalization',
          },
        ]
      : []),
    {
      value: SettingsTabValues.DATA,
      icon: <DataIcon />,
      label: 'com_nav_setting_data',
      description: 'Retention, exports, and shared data controls.',
      requiredPlan: 'plus',
      featureName: 'Data Controls',
    },
    ...(startupConfig?.balance?.enabled
      ? [
          {
            value: SettingsTabValues.BALANCE,
            icon: <DollarSign className="h-4 w-4" aria-hidden="true" />,
            label: 'com_nav_setting_balance' as TranslationKeys,
            description: 'Review token credit balance and usage.',
          },
        ]
      : []),
    {
      value: SettingsTabValues.ACCOUNT,
      icon: <UserIcon />,
      label: 'com_nav_setting_account',
      description: 'Profile, referrals, security, and account controls.',
    },
  ];

  const activeSection = tab ? sections.find((section) => section.value === tab) : undefined;

  if (tab && !activeSection) {
    return (
      <Presentation>
        <div className="h-full overflow-y-auto bg-presentation">
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 px-4 py-6 sm:px-6 lg:px-8">
            <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-sm text-text-secondary">
              <Link className="transition-colors hover:text-text-primary" to="/c/new">
                {localize('com_ui_chat')}
              </Link>
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
              <Link className="transition-colors hover:text-text-primary" to="/settings">
                {localize('com_nav_settings')}
              </Link>
            </nav>
            <div className="rounded-2xl border border-border-light bg-background/70 p-6">
              <h1 className="text-xl font-semibold text-text-primary">{localize('com_nav_settings')}</h1>
              <p className="mt-2 text-sm text-text-secondary">
                That settings section does not exist. Pick one of the available sections below.
              </p>
              <div className="mt-4">
                <Link
                  to="/settings"
                  className="inline-flex rounded-xl bg-violet-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-700"
                >
                  Back to settings
                </Link>
              </div>
            </div>
          </div>
        </div>
      </Presentation>
    );
  }

  return (
    <Presentation>
      <div className="h-full overflow-y-auto bg-presentation">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
          <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-sm text-text-secondary">
            <Link className="transition-colors hover:text-text-primary" to="/c/new">
              {localize('com_ui_chat')}
            </Link>
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
            <Link className="transition-colors hover:text-text-primary" to="/settings">
              {localize('com_nav_settings')}
            </Link>
            {activeSection && (
              <>
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
                <span className="text-text-primary">{localize(activeSection.label)}</span>
              </>
            )}
          </nav>

          {!activeSection ? (
            <>
              <div className="max-w-3xl">
                <h1 className="text-2xl font-semibold text-text-primary sm:text-3xl">
                  {localize('com_nav_settings')}
                </h1>
                <p className="mt-2 text-sm leading-6 text-text-secondary sm:text-base">
                  Pick a section instead of scrolling through one long modal. Each section now has its
                  own page and breadcrumb.
                </p>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {sections.map((section) => (
                  <SettingsOverviewCard
                    key={section.value}
                    href={`/settings/${section.value}`}
                    icon={section.icon}
                    title={localize(section.label)}
                    description={section.description}
                  />
                ))}
              </div>
            </>
          ) : (
            <>
              <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                <div className="max-w-3xl">
                  <h1 className="text-2xl font-semibold text-text-primary sm:text-3xl">
                    {localize(activeSection.label)}
                  </h1>
                  <p className="mt-2 text-sm leading-6 text-text-secondary sm:text-base">
                    {activeSection.description}
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  {sections.map((section) => (
                    <Link
                      key={section.value}
                      to={`/settings/${section.value}`}
                      className={cn(
                        'rounded-xl border px-3 py-2 text-sm transition-colors',
                        section.value === activeSection.value
                          ? 'border-violet-500/40 bg-violet-500/10 text-text-primary'
                          : 'border-border-light bg-background/60 text-text-secondary hover:text-text-primary',
                      )}
                    >
                      {localize(section.label)}
                    </Link>
                  ))}
                </div>
              </div>

              <div className="rounded-2xl border border-border-light bg-background/70 p-3 sm:p-5">
                <SettingsSectionContent section={activeSection} hasMemoryOptOut={hasMemoryOptOut} />
              </div>
            </>
          )}
        </div>
      </div>
    </Presentation>
  );
}
