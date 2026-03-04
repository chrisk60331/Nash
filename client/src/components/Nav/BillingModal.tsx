import { useState } from 'react';
import { Check, Lock, Sparkles, Zap } from 'lucide-react';
import { Dialog, DialogPanel, DialogTitle, Transition, TransitionChild } from '@headlessui/react';
import type { TDialogProps } from '~/common';
import { useGetSubscription, useCreateCheckout, useCreatePortalSession } from '~/data-provider';
import { useGetStartupConfig } from '~/data-provider';
import { useLocalize } from '~/hooks';
import { cn } from '~/utils';

type PlanTier = 'free' | 'plus' | 'unlimited';

interface TierCardProps {
  tier: PlanTier;
  name: string;
  description: string;
  features: string[];
  currentPlan: PlanTier;
  priceId?: string;
  icon: React.ReactNode;
  accent: string;
  onUpgrade: (priceId: string) => void;
  onManage: () => void;
  isLoading: boolean;
}

function TierCard({
  tier,
  name,
  description,
  features,
  currentPlan,
  priceId,
  icon,
  accent,
  onUpgrade,
  onManage,
  isLoading,
}: TierCardProps) {
  const localize = useLocalize();
  const isCurrent = currentPlan === tier;
  const isDowngrade =
    (tier === 'free' && currentPlan !== 'free') ||
    (tier === 'plus' && currentPlan === 'unlimited');

  return (
    <div
      className={cn(
        'flex flex-col rounded-xl border p-5 transition-all',
        isCurrent
          ? 'border-2 border-green-500 bg-green-500/5'
          : 'border-border-medium hover:border-border-heavy',
      )}
    >
      <div className="mb-3 flex items-center gap-2">
        <div className={cn('flex h-8 w-8 items-center justify-center rounded-lg', accent)}>
          {icon}
        </div>
        <h3 className="text-lg font-semibold text-text-primary">{name}</h3>
      </div>
      <p className="mb-4 text-sm text-text-secondary">{description}</p>
      <ul className="mb-6 flex-1 space-y-2">
        {features.map((feature, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-text-secondary">
            <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-green-500" />
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
              'w-full rounded-lg px-4 py-2.5 text-sm font-medium transition-colors',
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

export default function BillingModal({ open, onOpenChange }: TDialogProps) {
  const localize = useLocalize();
  const { data: startupConfig } = useGetStartupConfig();
  const { data: subscription } = useGetSubscription({ enabled: open });
  const checkoutMutation = useCreateCheckout();
  const portalMutation = useCreatePortalSession();
  const [isLoading, setIsLoading] = useState(false);

  const currentPlan: PlanTier = subscription?.plan ?? 'free';
  const billing = startupConfig?.billing;

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
  const usagePct = includedTokens > 0 ? Math.min(100, Math.round((usageTokens / includedTokens) * 100)) : 0;

  return (
    <Transition appear show={open}>
      <Dialog as="div" className="relative z-50" onClose={onOpenChange}>
        <TransitionChild
          enter="ease-out duration-200"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black opacity-50 dark:opacity-80" aria-hidden="true" />
        </TransitionChild>

        <TransitionChild
          enter="ease-out duration-200"
          enterFrom="opacity-0 scale-95"
          enterTo="opacity-100 scale-100"
          leave="ease-in duration-100"
          leaveFrom="opacity-100 scale-100"
          leaveTo="opacity-0 scale-95"
        >
          <div className="fixed inset-0 flex w-screen items-center justify-center p-4">
            <DialogPanel className="max-h-[90vh] w-full max-w-3xl overflow-hidden rounded-xl bg-background shadow-2xl backdrop-blur-2xl animate-in sm:rounded-2xl">
              <DialogTitle
                className="flex items-center justify-between border-b border-border-light p-6 pb-4"
                as="div"
              >
                <h2 className="text-lg font-semibold text-text-primary">
                  {localize('com_billing_title')}
                </h2>
                <button
                  type="button"
                  className="rounded-sm opacity-70 transition-opacity hover:opacity-100 focus:outline-none"
                  onClick={() => onOpenChange(false)}
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="h-5 w-5 text-text-primary"
                  >
                    <line x1="18" x2="6" y1="6" y2="18" />
                    <line x1="6" x2="18" y1="6" y2="18" />
                  </svg>
                </button>
              </DialogTitle>

              <div className="overflow-auto p-6">
                {currentPlan !== 'free' && includedTokens > 0 && (
                  <div className="mb-6 rounded-lg border border-border-light p-4">
                    <div className="mb-2 flex items-center justify-between text-sm">
                      <span className="font-medium text-text-primary">
                        {localize('com_billing_usage')}
                      </span>
                      <span className="text-text-secondary">
                        {new Intl.NumberFormat().format(usageTokens)} / {new Intl.NumberFormat().format(includedTokens)} tokens
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

                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
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
                    description={localize('com_billing_plus_desc')}
                    features={[
                      localize('com_billing_plus_feature_1'),
                      localize('com_billing_plus_feature_2'),
                      localize('com_billing_plus_feature_3'),
                      localize('com_billing_plus_feature_4'),
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
                    description={localize('com_billing_unlimited_desc')}
                    features={[
                      localize('com_billing_unlimited_feature_1'),
                      localize('com_billing_unlimited_feature_2'),
                      localize('com_billing_unlimited_feature_3'),
                    ]}
                    currentPlan={currentPlan}
                    priceId={billing?.priceIdUnlimited ?? ''}
                    icon={<Zap className="h-4 w-4 text-amber-600 dark:text-amber-400" />}
                    accent="bg-amber-100 dark:bg-amber-900/30"
                    onUpgrade={handleUpgrade}
                    onManage={handleManage}
                    isLoading={isLoading}
                  />
                </div>

                {currentPlan !== 'free' && (
                  <div className="mt-4 text-center">
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
            </DialogPanel>
          </div>
        </TransitionChild>
      </Dialog>
    </Transition>
  );
}
