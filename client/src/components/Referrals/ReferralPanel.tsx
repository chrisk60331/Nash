import { Fragment, useMemo, useState } from 'react';
import { Copy, Gift, Sparkles, Ticket, Users } from 'lucide-react';
import { Popover, Transition } from '@headlessui/react';
import { registerPage } from 'librechat-data-provider';
import { useToastContext } from '@librechat/client';
import { useChatContext } from '~/Providers';
import { useAuthContext, useLocalize } from '~/hooks';
import {
  useGetReferralSummary,
  useGetStartupConfig,
  useRedeemReferralOrPromoCode,
} from '~/data-provider';
import { cn } from '~/utils';

type ReferralPanelProps = {
  variant?: 'settings' | 'hero' | 'login' | 'header';
  showRedeem?: boolean;
  className?: string;
};

function formatCredits(value: number) {
  return new Intl.NumberFormat().format(value);
}

export default function ReferralPanel({
  variant = 'settings',
  showRedeem = false,
  className,
}: ReferralPanelProps) {
  const localize = useLocalize();
  const { showToast } = useToastContext();
  const { isAuthenticated } = useAuthContext();
  const { conversation, isSubmitting } = useChatContext();
  const { data: startupConfig } = useGetStartupConfig();
  const { data, isLoading } = useGetReferralSummary({
    enabled: isAuthenticated && startupConfig?.referrals?.enabled === true,
  });
  const redeemMutation = useRedeemReferralOrPromoCode();
  const [code, setCode] = useState('');
  const [badgeOpen, setBadgeOpen] = useState(false);

  const rewardUsd = data?.rewardUsd ?? startupConfig?.referrals?.rewardUsd ?? 5;
  const registerHref = useMemo(() => {
    if (typeof window === 'undefined' || !window.location.search) {
      return registerPage();
    }
    return `${registerPage()}${window.location.search}`;
  }, []);

  const handleCopy = async () => {
    if (!data?.referralLink) {
      return;
    }
    try {
      await navigator.clipboard.writeText(data.referralLink);
      showToast({ message: 'Referral link copied', status: 'success' });
    } catch (error) {
      showToast({ message: 'Could not copy referral link', status: 'error' });
    }
  };

  const handleRedeem = () => {
    const trimmed = code.trim();
    if (!trimmed) {
      return;
    }
    redeemMutation.mutate(trimmed, {
      onSuccess: (result) => {
        const message =
          result.kind === 'promo'
            ? `Promo applied: ${formatCredits(result.tokenCreditsAwarded ?? 0)} credits added`
            : 'Referral code linked to your account';
        showToast({ message, status: 'success' });
        setCode('');
      },
      onError: (error) => {
        showToast({ message: error.message || 'Could not redeem code', status: 'error' });
      },
    });
  };

  const shellClassName =
    variant === 'hero'
      ? 'overflow-hidden rounded-3xl border border-violet-500/30 bg-gradient-to-br from-violet-500/10 via-background to-amber-500/10 p-5 shadow-[0_20px_80px_-40px_rgba(139,92,246,0.7)]'
      : variant === 'login'
        ? 'rounded-3xl border border-amber-500/30 bg-gradient-to-br from-amber-500/10 via-background to-violet-500/10 p-5'
        : 'rounded-2xl border border-border-light bg-surface-secondary/60 p-4';

  const shouldHideHeaderBadge =
    variant === 'header' &&
    ((Array.isArray(conversation?.messages) && conversation.messages.length >= 1) || isSubmitting);

  if (!startupConfig?.referrals?.enabled) {
    return null;
  }

  if (shouldHideHeaderBadge) {
    return null;
  }

  if (!isAuthenticated) {
    if (variant === 'header') {
      return null;
    }
    if (variant === 'login') {
      return (
        <div className={cn('flex flex-col items-end', className)}>
          <button
            type="button"
            onClick={() => setBadgeOpen((prev) => !prev)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-all duration-200',
              badgeOpen
                ? 'border-violet-500/40 bg-violet-500/15 text-violet-700 dark:text-violet-400'
                : 'border-amber-500/30 bg-amber-500/10 text-amber-700 hover:bg-amber-500/20 dark:text-amber-400',
            )}
          >
            <Gift className="h-3.5 w-3.5" />
            Earn ${rewardUsd.toFixed(0)} per referral
          </button>
          <Transition
            as={Fragment}
            show={badgeOpen}
            enter="transition ease-out duration-200"
            enterFrom="opacity-0 -translate-y-1 scale-95"
            enterTo="opacity-100 translate-y-0 scale-100"
            leave="transition ease-in duration-150"
            leaveFrom="opacity-100 translate-y-0 scale-100"
            leaveTo="opacity-0 -translate-y-1 scale-95"
          >
            <div className="mt-2 w-72 origin-top-right rounded-2xl border border-violet-500/20 bg-gradient-to-br from-amber-500/8 via-background to-violet-500/8 p-4 shadow-lg backdrop-blur-sm">
              <div className="flex items-start gap-3">
                <div className="rounded-xl bg-violet-500/15 p-2 text-violet-500">
                  <Gift className="h-4 w-4" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-text-primary">Referral rewards</p>
                    <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-medium text-amber-600 dark:text-amber-400">
                      ${rewardUsd.toFixed(2)} / referral
                    </span>
                  </div>
                  <p className="mt-1 text-xs leading-5 text-text-secondary">
                    Invite friends once you&apos;re in. Earn token credits when a referral upgrades to a paid account.
                  </p>
                </div>
              </div>
              <div className="mt-3">
                <a
                  href={registerHref}
                  className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-3 py-2 text-xs font-medium text-white transition-transform duration-200 hover:-translate-y-0.5 hover:bg-violet-700"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  Start sharing invites
                </a>
              </div>
            </div>
          </Transition>
        </div>
      );
    }
    return (
      <div className={cn(shellClassName, className)}>
        <div className="flex items-start gap-3">
          <div className="rounded-2xl bg-violet-500/15 p-2 text-violet-500">
            <Gift className="h-5 w-5" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-semibold text-text-primary">Referral rewards</p>
            <p className="mt-1 text-sm text-text-secondary">
              Invite friends once you&apos;re in. Earn ${rewardUsd.toFixed(2)} in token credits when a referral
              upgrades to a paid account.
            </p>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <a
            href={registerHref}
            className="inline-flex items-center gap-2 rounded-2xl bg-violet-600 px-4 py-2 text-sm font-medium text-white transition-transform duration-200 hover:-translate-y-0.5 hover:bg-violet-700"
          >
            <Sparkles className="h-4 w-4" />
            Start sharing invites
          </a>
        </div>
      </div>
    );
  }

  if (variant === 'header') {
    return (
      <Popover className={cn('relative', className)}>
        {({ open }) => (
          <>
            <Popover.Button
              className={cn(
                'inline-flex h-10 items-center gap-2 rounded-xl border px-3 text-sm font-medium text-text-primary transition-all duration-200 ease-in-out active:scale-[0.97]',
                open
                  ? 'border-violet-500/40 bg-violet-500/12 shadow-[0_0_24px_rgba(139,92,246,0.15)]'
                  : 'border-border-light bg-presentation hover:border-violet-500/30 hover:bg-surface-active-alt',
              )}
            >
              <Gift className="h-4 w-4 text-violet-500" />
              <span className="hidden sm:inline">Invite</span>
              <span className="rounded-full bg-violet-500/15 px-1.5 py-0.5 text-[11px] text-violet-500">
                ${rewardUsd.toFixed(0)}
              </span>
            </Popover.Button>
            <Transition
              as={Fragment}
              enter="transition ease-out duration-200"
              enterFrom="opacity-0 translate-y-1 scale-95"
              enterTo="opacity-100 translate-y-0 scale-100"
              leave="transition ease-in duration-150"
              leaveFrom="opacity-100 translate-y-0 scale-100"
              leaveTo="opacity-0 translate-y-1 scale-95"
            >
              <Popover.Panel className="fixed right-3 top-16 z-[80] w-[320px] rounded-2xl border border-violet-500/20 bg-background/95 p-4 shadow-2xl backdrop-blur-xl sm:right-4">
                <div className="flex items-start gap-3">
                  <div className="rounded-xl bg-violet-500/15 p-2 text-violet-500">
                    <Gift className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-text-primary">Referral rewards</p>
                      <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-medium text-amber-600 dark:text-amber-400">
                        ${rewardUsd.toFixed(2)}
                      </span>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-text-secondary">
                      Earn token credits when an invited beta upgrades.
                    </p>
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-3 gap-2">
                  <div className="rounded-xl border border-border-light bg-background/70 p-2">
                    <div className="text-[10px] uppercase tracking-wide text-text-secondary">Code</div>
                    <div className="mt-1 truncate text-sm font-semibold tracking-[0.12em] text-text-primary">
                      {data?.referralCode ?? '...'}
                    </div>
                  </div>
                  <div className="rounded-xl border border-border-light bg-background/70 p-2">
                    <div className="text-[10px] uppercase tracking-wide text-text-secondary">Signups</div>
                    <div className="mt-1 text-sm font-semibold text-text-primary">{data?.stats.signups ?? 0}</div>
                  </div>
                  <div className="rounded-xl border border-border-light bg-background/70 p-2">
                    <div className="text-[10px] uppercase tracking-wide text-text-secondary">Paid</div>
                    <div className="mt-1 text-sm font-semibold text-text-primary">
                      {data?.stats.paidConversions ?? 0}
                    </div>
                  </div>
                </div>

                <div className="mt-3 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleCopy}
                    className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-3 py-2 text-xs font-medium text-white transition-transform duration-200 hover:-translate-y-0.5 hover:bg-violet-700 active:scale-[0.97]"
                  >
                    <Copy className="h-3.5 w-3.5" />
                    Copy link
                  </button>
                  <span className="min-w-0 truncate rounded-xl border border-border-light px-3 py-2 text-[11px] text-text-secondary">
                    {data?.referralLink}
                  </span>
                </div>
              </Popover.Panel>
            </Transition>
          </>
        )}
      </Popover>
    );
  }

  return (
    <div className={cn(shellClassName, className)}>
      <div className="flex items-start gap-3">
        <div className="rounded-2xl bg-violet-500/15 p-2 text-violet-500">
          <Gift className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-text-primary">Referral rewards</p>
            {data?.referredByCode && (
              <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-medium text-amber-600 dark:text-amber-400">
                Referred by {data.referredByCode}
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-text-secondary">
            Earn ${rewardUsd.toFixed(2)} in token credits whenever one of your invited betas upgrades.
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="mt-4 text-sm text-text-secondary">Loading referral rewards...</div>
      ) : (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-border-light bg-background/70 p-3">
              <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-text-secondary">
                <Ticket className="h-3.5 w-3.5" />
                Your code
              </div>
              <div className="mt-2 text-lg font-semibold tracking-[0.18em] text-text-primary">
                {data?.referralCode ?? '...'}
              </div>
            </div>
            <div className="rounded-2xl border border-border-light bg-background/70 p-3">
              <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-text-secondary">
                <Users className="h-3.5 w-3.5" />
                Signups
              </div>
              <div className="mt-2 text-lg font-semibold text-text-primary">{data?.stats.signups ?? 0}</div>
            </div>
            <div className="rounded-2xl border border-border-light bg-background/70 p-3">
              <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-text-secondary">
                <Sparkles className="h-3.5 w-3.5" />
                Paid conversions
              </div>
              <div className="mt-2 text-lg font-semibold text-text-primary">
                {data?.stats.paidConversions ?? 0}
              </div>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center gap-2 rounded-2xl bg-violet-600 px-4 py-2 text-sm font-medium text-white transition-transform duration-200 hover:-translate-y-0.5 hover:bg-violet-700"
            >
              <Copy className="h-4 w-4" />
              Copy invite link
            </button>
            {data?.referralLink && (
              <span className="truncate rounded-2xl border border-border-light px-3 py-2 text-xs text-text-secondary">
                {data.referralLink}
              </span>
            )}
          </div>

          {showRedeem && (
            <div className="mt-4 rounded-2xl border border-border-light bg-background/70 p-3">
              <label className="block text-sm font-medium text-text-primary">Redeem promo code</label>
              <p className="mt-1 text-xs text-text-secondary">
                Claim a promo credit code or attach a referral code if you signed up without one.
              </p>
              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <input
                  value={code}
                  onChange={(event) => setCode(event.target.value.toUpperCase())}
                  placeholder="Enter code"
                  className="flex-1 rounded-2xl border border-border-light bg-surface-primary px-3 py-2 text-sm text-text-primary focus:border-violet-500 focus:outline-none"
                />
                <button
                  type="button"
                  onClick={handleRedeem}
                  disabled={redeemMutation.isLoading || code.trim().length === 0}
                  className="rounded-2xl border border-violet-500/30 px-4 py-2 text-sm font-medium text-violet-600 transition-colors hover:bg-violet-500/10 disabled:cursor-not-allowed disabled:opacity-50 dark:text-violet-400"
                >
                  {redeemMutation.isLoading ? localize('com_ui_saving') : localize('com_ui_submit')}
                </button>
              </div>
            </div>
          )}

          {variant === 'settings' && data?.recentReferrals?.length ? (
            <div className="mt-4 space-y-2">
              <p className="text-xs font-medium uppercase tracking-wide text-text-secondary">Recent referrals</p>
              {data.recentReferrals.map((referral) => (
                <div
                  key={referral.userId}
                  className="flex items-center justify-between rounded-2xl border border-border-light bg-background/70 px-3 py-2 text-sm"
                >
                  <span className="text-text-primary">{referral.name}</span>
                  <span className="text-text-secondary">
                    {referral.rewardGrantedAt ? 'Rewarded' : 'Signed up'}
                  </span>
                </div>
              ))}
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
