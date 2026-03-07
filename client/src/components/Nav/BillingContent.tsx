import { useState } from 'react';
import { Check, Lock, Sparkles, Zap } from 'lucide-react';
import { useCreateCheckout, useCreatePortalSession, useGetStartupConfig, useGetSubscription } from '~/data-provider';
import { useLocalize } from '~/hooks';
import { cn } from '~/utils';

type PlanTier = 'free' | 'plus' | 'unlimited';

interface TierCardProps {
  tier: PlanTier;
  name: string;
  description: string;
  price?: string;
  priceNote?: string;
  features: string[];
  highlight?: React.ReactNode;
  currentPlan: PlanTier;
  priceId?: string;
  icon: React.ReactNode;
  accent: string;
  onUpgrade: (priceId: string) => void;
  onManage: () => void;
  isLoading: boolean;
  className?: string;
}

function TierCard({
  tier,
  name,
  description,
  price,
  priceNote,
  features,
  highlight,
  currentPlan,
  priceId,
  icon,
  accent,
  onUpgrade,
  onManage,
  isLoading,
  className,
}: TierCardProps) {
  const localize = useLocalize();
  const isCurrent = currentPlan === tier;
  const isDowngrade =
    (tier === 'free' && currentPlan !== 'free') ||
    (tier === 'plus' && currentPlan === 'unlimited');

  return (
    <div
      className={cn(
        'flex h-full flex-col rounded-2xl border p-4 transition-all',
        isCurrent
          ? 'border-2 border-green-500 bg-green-500/5'
          : 'border-border-medium hover:border-border-heavy',
        className,
      )}
    >
      <div className="mb-2 flex items-center gap-2">
        <div className={cn('flex h-8 w-8 items-center justify-center rounded-lg', accent)}>{icon}</div>
        <h3 className="text-base font-semibold text-text-primary">{name}</h3>
      </div>
      {price && (
        <div className="mb-2">
          <div className="text-2xl font-semibold tracking-tight text-text-primary">{price}</div>
          {priceNote && (
            <div className="mt-0.5 text-[11px] uppercase tracking-wide text-text-secondary">
              {priceNote}
            </div>
          )}
        </div>
      )}
      <p className="mb-3 text-sm leading-5 text-text-secondary">{description}</p>
      {highlight && (
        <div className="mb-3 rounded-xl border border-border-light bg-surface-secondary/70 p-2.5">
          {highlight}
        </div>
      )}
      <ul className="mb-4 flex-1 space-y-1.5">
        {features.map((feature, i) => (
          <li key={i} className="flex items-start gap-2 text-sm leading-5 text-text-secondary">
            <Check className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-green-500" />
            <span>{feature}</span>
          </li>
        ))}
      </ul>
      <div className="mt-auto">
        {isCurrent ? (
          <div className="flex items-center justify-center gap-1.5 rounded-lg bg-green-500/10 px-4 py-2.5 text-sm font-medium text-green-600 dark:text-green-400">
            <Check className="h-4 w-4" />
            {localize('com_billing_current_plan')}
          </div>
        ) : isDowngrade ? null : (
          <button
            onClick={() => {
              if (currentPlan !== 'free' && priceId) {
                onManage();
              } else if (priceId) {
                onUpgrade(priceId);
              }
            }}
            disabled={isLoading || !priceId}
            className={cn(
              'w-full rounded-lg px-4 py-2 text-sm font-medium transition-colors',
              tier === 'unlimited'
                ? 'bg-amber-500 text-white hover:bg-amber-600 disabled:opacity-50'
                : 'bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50',
            )}
          >
            {isLoading ? '...' : localize('com_billing_upgrade')}
          </button>
        )}
      </div>
    </div>
  );
}

export default function BillingContent({ variant = 'modal' }: { variant?: 'modal' | 'page' }) {
  const localize = useLocalize();
  const { data: startupConfig } = useGetStartupConfig();
  const { data: subscription } = useGetSubscription({ enabled: true });
  const checkoutMutation = useCreateCheckout();
  const portalMutation = useCreatePortalSession();
  const [isLoading, setIsLoading] = useState(false);

  const currentPlan: PlanTier = subscription?.plan ?? 'free';
  const billing = startupConfig?.billing;
  const formatTokenCount = (value: number | undefined) =>
    new Intl.NumberFormat().format(Number(value ?? 0));

  const getOverageCopy = (planKey: 'plus' | 'pro') => {
    const planConfig = billing?.plans?.[planKey];
    if (!planConfig?.overageEnabled) {
      return `${formatTokenCount(planConfig?.tokens)} included each month`;
    }
    return `${formatTokenCount(planConfig?.tokens)} included monthly, then $${Number(
      planConfig?.overageUnitPriceUsd ?? 0,
    ).toFixed(2)} / ${formatTokenCount(planConfig?.overageTokensPerUnit)} tokens`;
  };

  const handleUpgrade = async (priceId: string) => {
    setIsLoading(true);
    try {
      const result = await checkoutMutation.mutateAsync(priceId);
      if (result.url) {
        window.location.href = result.url;
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleManage = async () => {
    setIsLoading(true);
    try {
      const result = await portalMutation.mutateAsync();
      if (result.url) {
        window.location.href = result.url;
      }
    } finally {
      setIsLoading(false);
    }
  };

  const usageTokens = subscription?.usageTokens ?? 0;
  const includedTokens = subscription?.includedTokens ?? 0;
  const overageTokens = subscription?.overageTokens ?? 0;
  const usagePct =
    includedTokens > 0 ? Math.min(100, Math.round((usageTokens / includedTokens) * 100)) : 0;

  const contentClasses =
    variant === 'page'
      ? 'space-y-5'
      : 'max-h-[calc(90vh-88px)] overflow-auto p-5';

  const planGridClasses =
    variant === 'page'
      ? 'grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3'
      : 'grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3';

  const featuredCardClasses =
    variant === 'page' ? 'md:col-span-2 xl:col-span-1' : 'md:col-span-2 xl:col-span-1';

  return (
    <div className={contentClasses}>
      {billing?.plans?.plus?.overageEnabled && (
        <div className="rounded-2xl border border-violet-500/20 bg-violet-500/5 p-3 text-sm text-text-primary">
          <div className="font-medium">Pay as you go overage</div>
          <p className="mt-1 text-sm leading-5 text-text-secondary">
            Paid plans keep working after included monthly usage is exhausted. Extra usage is billed
            automatically in metered token blocks.
          </p>
          {overageTokens > 0 && (
            <p className="mt-1.5 font-medium text-violet-600 dark:text-violet-400">
              Current overage this cycle: {formatTokenCount(overageTokens)} tokens
            </p>
          )}
        </div>
      )}

      {currentPlan !== 'free' && includedTokens > 0 && (
        <div className="rounded-lg border border-border-light p-3">
          <div className="mb-2 flex items-center justify-between gap-3 text-sm">
            <span className="font-medium text-text-primary">{localize('com_billing_usage')}</span>
            <span className="text-right text-text-secondary">
              {new Intl.NumberFormat().format(usageTokens)} /{' '}
              {new Intl.NumberFormat().format(includedTokens)} tokens
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-surface-tertiary">
            <div
              className={cn(
                'h-full rounded-full transition-all',
                usagePct > 90 ? 'bg-red-500' : usagePct > 70 ? 'bg-amber-500' : 'bg-green-500',
              )}
              style={{ width: `${usagePct}%` }}
            />
          </div>
        </div>
      )}

      <div className={planGridClasses}>
        <TierCard
          tier="free"
          name={localize('com_billing_free')}
          description={localize('com_billing_free_desc')}
          features={[
            localize('com_billing_free_feature_1'),
            localize('com_billing_free_feature_2'),
            localize('com_billing_free_feature_3'),
          ]}
          currentPlan={currentPlan}
          icon={<Lock className="h-4 w-4 text-gray-600 dark:text-gray-400" />}
          accent="bg-gray-100 dark:bg-gray-800"
          onUpgrade={handleUpgrade}
          onManage={handleManage}
          isLoading={isLoading}
        />
        <TierCard
          tier="plus"
          name={localize('com_billing_plus')}
          description="Premium models, memory, and enough capacity for daily workflows."
          price="$19.99 CAD"
          priceNote="Per month"
          features={[
            localize('com_billing_plus_feature_1'),
            localize('com_billing_plus_feature_2'),
            localize('com_billing_plus_feature_3'),
            '500,000 tokens included each month',
            getOverageCopy('plus'),
          ]}
          currentPlan={currentPlan}
          priceId={billing?.priceIdPlus ?? ''}
          icon={<Sparkles className="h-4 w-4 text-violet-600 dark:text-violet-400" />}
          accent="bg-violet-100 dark:bg-violet-900/30"
          onUpgrade={handleUpgrade}
          onManage={handleManage}
          isLoading={isLoading}
        />
        <TierCard
          tier="unlimited"
          name={localize('com_billing_unlimited')}
          description="Built for teams and high-volume research with a huge monthly allowance."
          price="$199.99 CAD"
          priceNote="Per month"
          highlight={
            <div>
              <div className="text-sm font-semibold text-text-primary">
                3 million tokens included monthly
              </div>
              <div className="mt-1 text-sm leading-5 text-text-secondary">
                Roughly 2.25 million words of monthly capacity for deep research and document-heavy
                work.
              </div>
            </div>
          }
          features={[
            localize('com_billing_unlimited_feature_1'),
            '3 million included tokens each month',
            getOverageCopy('pro'),
            localize('com_billing_unlimited_feature_3'),
          ]}
          currentPlan={currentPlan}
          priceId={billing?.priceIdUnlimited ?? ''}
          icon={<Zap className="h-4 w-4 text-amber-600 dark:text-amber-400" />}
          accent="bg-amber-100 dark:bg-amber-900/30"
          onUpgrade={handleUpgrade}
          onManage={handleManage}
          isLoading={isLoading}
          className={featuredCardClasses}
        />
      </div>

      {currentPlan !== 'free' && (
        <div className={cn('text-center', variant === 'page' ? 'pt-1' : '')}>
          <button
            onClick={handleManage}
            disabled={isLoading}
            className="text-sm text-text-secondary underline transition-colors hover:text-text-primary"
          >
            {localize('com_billing_manage')}
          </button>
        </div>
      )}
    </div>
  );
}
