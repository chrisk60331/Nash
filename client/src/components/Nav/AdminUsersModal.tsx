import React, { useState, useCallback } from 'react';
import {
  Search,
  Gift,
  Shield,
  User,
  RotateCcw,
  X,
  Users,
  Tag,
  CheckCircle2,
} from 'lucide-react';
import { Dialog, DialogPanel, Transition, TransitionChild } from '@headlessui/react';
import { QueryKeys, dataService } from 'librechat-data-provider';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { AdminUser, AdminSubscription, AdminSecuritySettingsResponse } from 'librechat-data-provider';
import type { TDialogProps } from '~/common';
import { useCreateAdminPromoCode, useGetAdminPromoCodes } from '~/data-provider';
import { cn } from '~/utils';

type PlanTier = 'free' | 'plus' | 'unlimited';
type ActiveTab = 'users' | 'promos';

const PLAN_CONFIG: Record<PlanTier, { badge: string; active: string; dot: string }> = {
  free: {
    badge: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
    active: 'bg-gray-700 text-white dark:bg-gray-600',
    dot: 'bg-gray-400',
  },
  plus: {
    badge: 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-400',
    active: 'bg-violet-600 text-white',
    dot: 'bg-violet-500',
  },
  unlimited: {
    badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400',
    active: 'bg-amber-500 text-white',
    dot: 'bg-amber-500',
  },
};

const AVATAR_GRADIENTS = [
  'from-blue-500 to-violet-600',
  'from-emerald-500 to-teal-600',
  'from-amber-500 to-orange-600',
  'from-rose-500 to-pink-600',
  'from-cyan-500 to-blue-600',
  'from-indigo-500 to-purple-600',
];

function avatarGradient(str: string): string {
  let hash = 0;
  for (const ch of str) {
    hash = (hash * 31 + ch.charCodeAt(0)) & 0xffffffff;
  }
  return AVATAR_GRADIENTS[Math.abs(hash) % AVATAR_GRADIENTS.length];
}

function UserAvatar({ name, email, size = 'md' }: { name?: string | null; email: string; size?: 'sm' | 'md' | 'lg' }) {
  const label = name || email;
  const initial = label[0]?.toUpperCase() ?? '?';
  const gradient = avatarGradient(email);
  return (
    <div
      className={cn(
        'flex flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br font-bold text-white shadow-sm',
        gradient,
        size === 'sm' && 'h-7 w-7 text-xs',
        size === 'md' && 'h-9 w-9 text-sm',
        size === 'lg' && 'h-11 w-11 text-base',
      )}
    >
      {initial}
    </div>
  );
}

function PlanBadge({ plan }: { plan: PlanTier }) {
  const cfg = PLAN_CONFIG[plan] ?? PLAN_CONFIG.free;
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase leading-none',
        cfg.badge,
      )}
    >
      <span className={cn('h-1.5 w-1.5 rounded-full', cfg.dot)} />
      {plan}
    </span>
  );
}

function DetailRow({
  label,
  value,
  mono,
  muted,
}: {
  label: string;
  value: string;
  mono?: boolean;
  muted?: boolean;
}) {
  return (
    <div className="flex items-center justify-between border-b border-border-light px-4 py-2.5 last:border-b-0">
      <span className="text-xs text-text-secondary">{label}</span>
      <span
        className={cn(
          'max-w-[200px] truncate text-xs',
          mono && 'font-mono',
          muted ? 'text-text-secondary' : 'text-text-primary',
        )}
      >
        {value}
      </span>
    </div>
  );
}

/* ─── Left panel: user list item ─── */
function UserListItem({
  user,
  isSelected,
  onSelect,
}: {
  user: AdminUser;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        'group flex w-full items-center gap-3 px-3 py-2.5 text-left transition-all duration-150',
        isSelected ? 'bg-blue-50 dark:bg-blue-950/30' : 'hover:bg-surface-hover',
      )}
    >
      <UserAvatar name={user.name} email={user.email} size="sm" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              'truncate text-[13px] font-medium',
              isSelected ? 'text-blue-600 dark:text-blue-400' : 'text-text-primary',
            )}
          >
            {user.name || user.username || user.email}
          </span>
          {user.role === 'ADMIN' && (
            <Shield className="h-3 w-3 flex-shrink-0 text-blue-500" />
          )}
        </div>
        <p className="truncate text-[11px] text-text-secondary">{user.email}</p>
      </div>
    </button>
  );
}

/* ─── Right panel: subscription detail ─── */
function SubscriptionDetail({
  user,
  onRoleUpdated,
}: {
  user: AdminUser;
  onRoleUpdated: () => void;
}) {
  const queryClient = useQueryClient();
  const [savedField, setSavedField] = useState<string | null>(null);

  const { data: sub, isLoading } = useQuery<AdminSubscription>(
    [QueryKeys.adminUserSubscription, user.id],
    () => dataService.getAdminUserSubscription(user.id),
    { staleTime: 10_000 },
  );

  const flash = useCallback((field: string) => {
    setSavedField(field);
    setTimeout(() => setSavedField(null), 2000);
  }, []);

  const mutation = useMutation(
    (data: { plan?: string; usageTokens?: number }) =>
      dataService.updateAdminUserSubscription(user.id, data),
    {
      onSuccess: (_, vars) => {
        queryClient.invalidateQueries([QueryKeys.adminUserSubscription, user.id]);
        queryClient.invalidateQueries([QueryKeys.adminUsers]);
        flash(vars.plan != null ? 'plan' : 'usage');
      },
    },
  );

  const roleMutation = useMutation(
    (role: string) => dataService.setAdminUserRole(user.id, role),
    {
      onSuccess: () => {
        queryClient.invalidateQueries([QueryKeys.adminUsers]);
        flash('role');
        onRoleUpdated();
      },
    },
  );

  const [pendingPlan, setPendingPlan] = useState<PlanTier | null>(null);

  const handlePlanChange = useCallback(
    (newPlan: PlanTier) => {
      setPendingPlan(newPlan);
      mutation.mutate({ plan: newPlan }, { onSettled: () => setPendingPlan(null) });
    },
    [mutation],
  );

  const handleResetUsage = useCallback(() => {
    mutation.mutate({ usageTokens: 0 });
  }, [mutation]);

  const isAdmin = user.role === 'ADMIN';
  const currentPlan = (pendingPlan ?? sub?.plan ?? 'free') as PlanTier;

  if (isLoading || !sub) {
    return (
      <div className="flex flex-1 flex-col gap-5 p-6">
        <div className="flex items-center gap-4">
          <div className="h-11 w-11 animate-pulse rounded-full bg-surface-tertiary" />
          <div className="space-y-2">
            <div className="h-4 w-36 animate-pulse rounded bg-surface-tertiary" />
            <div className="h-3 w-52 animate-pulse rounded bg-surface-tertiary" />
          </div>
        </div>
        <div className="space-y-3 pt-2">
          {[...Array(4)].map((_, i) => (
            <div
              key={i}
              className="h-10 animate-pulse rounded-xl bg-surface-tertiary"
              style={{ animationDelay: `${i * 80}ms` }}
            />
          ))}
        </div>
      </div>
    );
  }

  const usagePct =
    sub.includedTokens > 0
      ? Math.min(100, (sub.usageTokens / sub.includedTokens) * 100)
      : 0;

  const hasExtraDetails =
    (sub.overageTokens != null && sub.overageTokens > 0) ||
    sub.balance ||
    sub.referralCode ||
    sub.referredByCode ||
    sub.stripeCustomerId ||
    sub.stripeMeteredItemId ||
    sub.periodEnd;

  return (
    <div className="flex flex-1 flex-col overflow-y-auto">
      {/* User header */}
      <div className="border-b border-border-light px-6 py-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <UserAvatar name={user.name} email={user.email} size="lg" />
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-semibold text-text-primary">
                  {user.name || user.username || user.email}
                </h3>
                {savedField === 'role' && (
                  <CheckCircle2 className="h-4 w-4 text-emerald-500 animate-in fade-in zoom-in-75 duration-200" />
                )}
              </div>
              <p className="text-sm text-text-secondary">{user.email}</p>
              <div className="mt-1.5 flex items-center gap-2">
                <PlanBadge plan={currentPlan} />
                {isAdmin && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                    <Shield className="h-2.5 w-2.5" />
                    Admin
                  </span>
                )}
              </div>
            </div>
          </div>
          <button
            onClick={() => roleMutation.mutate(isAdmin ? 'USER' : 'ADMIN')}
            disabled={roleMutation.isLoading}
            className={cn(
              'flex-shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium transition-all active:scale-[0.97]',
              isAdmin
                ? 'bg-red-50 text-red-600 hover:bg-red-100 dark:bg-red-950/30 dark:text-red-400 dark:hover:bg-red-950/50'
                : 'bg-blue-50 text-blue-600 hover:bg-blue-100 dark:bg-blue-950/30 dark:text-blue-400 dark:hover:bg-blue-950/50',
            )}
          >
            {roleMutation.isLoading ? '...' : isAdmin ? 'Demote to User' : 'Promote to Admin'}
          </button>
        </div>
      </div>

      <div className="flex-1 space-y-5 px-6 py-5">
        {/* Plan selector */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <label className="text-xs font-semibold uppercase tracking-wide text-text-secondary">
              Plan
            </label>
            {savedField === 'plan' && (
              <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-600 animate-in fade-in duration-200">
                <CheckCircle2 className="h-3 w-3" />
                Saved
              </span>
            )}
          </div>
          <div className="flex gap-2">
            {(['free', 'plus', 'unlimited'] as PlanTier[]).map((p) => (
              <button
                key={p}
                onClick={() => handlePlanChange(p)}
                disabled={mutation.isLoading}
                className={cn(
                  'flex-1 rounded-xl border py-2.5 text-sm font-medium transition-all duration-150 active:scale-[0.97]',
                  currentPlan === p
                    ? cn('border-transparent shadow-sm', PLAN_CONFIG[p].active)
                    : 'border-border-light text-text-secondary hover:border-border-medium hover:bg-surface-hover',
                )}
              >
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Token usage */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <label className="text-xs font-semibold uppercase tracking-wide text-text-secondary">
              Token Usage
            </label>
            <div className="flex items-center gap-2">
              {savedField === 'usage' && (
                <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-600 animate-in fade-in duration-200">
                  <CheckCircle2 className="h-3 w-3" />
                  Reset
                </span>
              )}
              {sub.usageTokens > 0 && (
                <button
                  onClick={handleResetUsage}
                  disabled={mutation.isLoading}
                  className="flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium text-red-500 transition-all hover:bg-red-50 active:scale-[0.97] dark:hover:bg-red-950/30"
                >
                  <RotateCcw className="h-2.5 w-2.5" />
                  Reset
                </button>
              )}
            </div>
          </div>
          <div className="rounded-xl bg-surface-secondary px-4 py-3">
            <div className="flex items-baseline justify-between">
              <span className="text-xl font-semibold tabular-nums text-text-primary">
                {new Intl.NumberFormat().format(sub.usageTokens)}
              </span>
              {sub.includedTokens > 0 && (
                <span className="text-xs text-text-secondary">
                  of {new Intl.NumberFormat().format(sub.includedTokens)}
                </span>
              )}
            </div>
            {sub.includedTokens > 0 && (
              <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-surface-tertiary">
                <div
                  className={cn(
                    'h-full rounded-full transition-all duration-500',
                    usagePct > 90
                      ? 'bg-red-500'
                      : usagePct > 70
                        ? 'bg-amber-500'
                        : 'bg-blue-500',
                  )}
                  style={{ width: `${usagePct}%` }}
                />
              </div>
            )}
          </div>
        </div>

        {/* Details */}
        {hasExtraDetails && (
          <div className="overflow-hidden rounded-xl border border-border-light">
            {sub.overageTokens != null && sub.overageTokens > 0 && (
              <DetailRow
                label="Overage"
                value={`${new Intl.NumberFormat().format(sub.overageTokens)} tokens`}
              />
            )}
            {sub.balance && (
              <DetailRow
                label="Credit balance"
                value={
                  sub.balance.tokenCreditsUsd != null
                    ? `$${sub.balance.tokenCreditsUsd.toFixed(2)}`
                    : new Intl.NumberFormat().format(sub.balance.tokenCredits)
                }
              />
            )}
            {sub.referralCode && (
              <DetailRow label="Referral code" value={sub.referralCode} mono />
            )}
            {sub.referredByCode && (
              <DetailRow label="Referred by" value={sub.referredByCode} mono />
            )}
            {sub.stripeCustomerId && (
              <DetailRow label="Stripe customer" value={sub.stripeCustomerId} mono muted />
            )}
            {sub.stripeMeteredItemId && (
              <DetailRow label="Metered item" value={sub.stripeMeteredItemId} mono muted />
            )}
            {sub.periodEnd && (
              <DetailRow
                label="Period ends"
                value={new Date(sub.periodEnd).toLocaleDateString()}
              />
            )}
          </div>
        )}

        {(mutation.isError || roleMutation.isError) && (
          <p className="rounded-xl bg-red-50 px-4 py-2.5 text-xs text-red-600 dark:bg-red-950/30 dark:text-red-400">
            Failed to update. Please try again.
          </p>
        )}
      </div>
    </div>
  );
}

/* ─── Promo codes panel ─── */
function PromoPanel({ open }: { open: boolean }) {
  const [promoCode, setPromoCode] = useState('');
  const [promoUsdValue, setPromoUsdValue] = useState('5');
  const [promoMaxUses, setPromoMaxUses] = useState('');

  const { data: promoData } = useGetAdminPromoCodes({ enabled: open });
  const promoMutation = useCreateAdminPromoCode();

  return (
    <div className="flex-1 overflow-y-auto px-6 py-5">
      <div className="mb-6">
        <label className="mb-3 block text-xs font-semibold uppercase tracking-wide text-text-secondary">
          New Code
        </label>
        <div className="space-y-3">
          <input
            type="text"
            placeholder="Code (e.g. LAUNCH50)"
            value={promoCode}
            onChange={(e) => setPromoCode(e.target.value.toUpperCase())}
            className="w-full rounded-xl border border-border-medium bg-transparent px-4 py-2.5 font-mono text-sm text-text-primary placeholder-text-secondary focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          />
          <div className="flex gap-3">
            <input
              type="number"
              min="1"
              step="0.5"
              placeholder="USD reward"
              value={promoUsdValue}
              onChange={(e) => setPromoUsdValue(e.target.value)}
              className="flex-1 rounded-xl border border-border-medium bg-transparent px-4 py-2.5 text-sm text-text-primary placeholder-text-secondary focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            <input
              type="number"
              min="1"
              placeholder="Max uses (optional)"
              value={promoMaxUses}
              onChange={(e) => setPromoMaxUses(e.target.value)}
              className="flex-1 rounded-xl border border-border-medium bg-transparent px-4 py-2.5 text-sm text-text-primary placeholder-text-secondary focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
          </div>
          <button
            type="button"
            disabled={promoMutation.isLoading || promoCode.trim().length === 0}
            onClick={() =>
              promoMutation.mutate(
                {
                  code: promoCode.trim(),
                  usdValue: Number(promoUsdValue || '0'),
                  maxUses: promoMaxUses ? Number(promoMaxUses) : undefined,
                },
                {
                  onSuccess: () => {
                    setPromoCode('');
                    setPromoUsdValue('5');
                    setPromoMaxUses('');
                  },
                },
              )
            }
            className="w-full rounded-xl bg-violet-600 py-2.5 text-sm font-semibold text-white transition-all hover:bg-violet-700 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {promoMutation.isLoading ? 'Creating...' : 'Create Promo Code'}
          </button>
        </div>
      </div>

      {promoData?.promoCodes?.length ? (
        <div>
          <label className="mb-3 block text-xs font-semibold uppercase tracking-wide text-text-secondary">
            Active Codes ({promoData.promoCodes.length})
          </label>
          <div className="space-y-2">
            {promoData.promoCodes.map((promo) => (
              <div
                key={promo.code}
                className="flex items-center justify-between rounded-xl border border-border-light bg-surface-secondary/50 px-4 py-3 transition-colors hover:bg-surface-hover"
              >
                <span className="font-mono text-sm font-semibold text-text-primary">
                  {promo.code}
                </span>
                <div className="flex items-center gap-3 text-xs text-text-secondary">
                  <span className="font-medium text-emerald-600 dark:text-emerald-400">
                    ${promo.usdValue?.toFixed(2) ?? '0.00'}
                  </span>
                  {promo.maxUses != null && (
                    <span className="rounded-full bg-surface-tertiary px-2 py-0.5">
                      max {promo.maxUses}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-14 text-center">
          <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-100 dark:bg-violet-900/20">
            <Tag className="h-7 w-7 text-violet-500" />
          </div>
          <p className="text-sm font-medium text-text-primary">No promo codes yet</p>
          <p className="mt-1 text-xs text-text-secondary">Create one above to get started</p>
        </div>
      )}
    </div>
  );
}

/* ─── Main modal ─── */
export default function AdminUsersModal({ open, onOpenChange }: TDialogProps) {
  const [search, setSearch] = useState('');
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>('users');
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery(
    [QueryKeys.adminUsers, search],
    () => dataService.getAdminUsers(search || undefined),
    {
      staleTime: 15_000,
      keepPreviousData: true,
      enabled: open,
    },
  );

  const { data: securitySettings } = useQuery<AdminSecuritySettingsResponse>(
    ['admin-security-settings'],
    () => dataService.getAdminSecuritySettings(),
    {
      staleTime: 15_000,
      enabled: open,
    },
  );

  const securityMutation = useMutation(
    (requireMfaForAllUsers: boolean) =>
      dataService.updateAdminSecuritySettings({ requireMfaForAllUsers }),
    {
      onSuccess: (updated) => {
        queryClient.setQueryData(['admin-security-settings'], updated);
        queryClient.setQueryData([QueryKeys.startupConfig], (current: Record<string, unknown> | undefined) =>
          current != null ? { ...current, requireMfaForAllUsers: updated.requireMfaForAllUsers } : current,
        );
      },
    },
  );

  const users = data?.users ?? [];
  const selectedUser = users.find((u) => u.id === selectedUserId) ?? null;

  return (
    <Transition appear show={open}>
      <Dialog as="div" className="relative z-50" onClose={onOpenChange}>
        <TransitionChild
          enter="ease-out duration-200"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-150"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/50 dark:bg-black/70" aria-hidden="true" />
        </TransitionChild>

        <TransitionChild
          enter="ease-out duration-200"
          enterFrom="opacity-0 translate-y-2 scale-[0.98]"
          enterTo="opacity-100 translate-y-0 scale-100"
          leave="ease-in duration-150"
          leaveFrom="opacity-100 translate-y-0 scale-100"
          leaveTo="opacity-0 translate-y-2 scale-[0.98]"
        >
          <div className="fixed inset-0 flex items-center justify-center p-4 sm:p-6">
            <DialogPanel className="flex h-[85vh] w-full max-w-4xl overflow-hidden rounded-2xl bg-background shadow-2xl">

              {/* ── Left panel: nav + list ── */}
              <div className="flex w-72 flex-shrink-0 flex-col border-r border-border-light">

                {/* Header */}
                <div className="border-b border-border-light px-4 pb-3 pt-4">
                  <div className="mb-3 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Shield className="h-4 w-4 text-blue-500" />
                      <h2 className="text-sm font-semibold text-text-primary">User Management</h2>
                    </div>
                    <button
                      type="button"
                      onClick={() => onOpenChange(false)}
                      className="rounded-lg p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
                      aria-label="Close"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>

                  {/* Tabs */}
                  <div className="flex rounded-lg bg-surface-secondary p-0.5">
                    {(
                    [
                      { id: 'users' as ActiveTab, label: 'Users', Icon: Users, count: data?.total },
                      { id: 'promos' as ActiveTab, label: 'Promos', Icon: Gift, count: undefined },
                    ] as { id: ActiveTab; label: string; Icon: React.ElementType; count?: number }[]
                  ).map(({ id, label, Icon, count }) => (
                      <button
                        key={id}
                        onClick={() => setActiveTab(id)}
                        className={cn(
                          'flex flex-1 items-center justify-center gap-1.5 rounded-md py-1.5 text-xs font-medium transition-all',
                          activeTab === id
                            ? 'bg-background text-text-primary shadow-sm'
                            : 'text-text-secondary hover:text-text-primary',
                        )}
                      >
                        <Icon className="h-3 w-3" aria-hidden="true" />
                        {label}
                        {count != null && (
                          <span
                            className={cn(
                              'rounded-full px-1.5 py-0.5 text-[10px] leading-none',
                              activeTab === id
                                ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                                : 'text-text-secondary',
                            )}
                          >
                            {count}
                          </span>
                        )}
                      </button>
                    ))}
                  </div>

                  <div className="mt-3 rounded-xl border border-border-light bg-surface-secondary/40 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold text-text-primary">Require MFA for all users</p>
                        <p className="mt-1 text-[11px] leading-relaxed text-text-secondary">
                          Admins are always required. Turn this on to require TOTP enrollment for every account.
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() =>
                          securityMutation.mutate(!(securitySettings?.requireMfaForAllUsers ?? false))
                        }
                        disabled={securityMutation.isLoading}
                        className={cn(
                          'relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-60',
                          securitySettings?.requireMfaForAllUsers
                            ? 'bg-green-600'
                            : 'bg-surface-tertiary',
                        )}
                        aria-pressed={securitySettings?.requireMfaForAllUsers ?? false}
                        aria-label="Require MFA for all users"
                      >
                        <span
                          className={cn(
                            'inline-block h-5 w-5 transform rounded-full bg-white transition-transform',
                            securitySettings?.requireMfaForAllUsers ? 'translate-x-5' : 'translate-x-1',
                          )}
                        />
                      </button>
                    </div>
                  </div>
                </div>

                {/* Search (users tab only) */}
                {activeTab === 'users' && (
                  <div className="border-b border-border-light px-3 py-2">
                    <div className="relative">
                      <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-secondary" />
                      <input
                        type="text"
                        placeholder="Search users..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="w-full rounded-lg border border-border-light bg-surface-secondary/50 py-1.5 pl-8 pr-3 text-xs text-text-primary placeholder-text-secondary transition-all focus:border-blue-500 focus:bg-background focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                      />
                    </div>
                  </div>
                )}

                {/* List body */}
                <div className="flex-1 overflow-y-auto">
                  {activeTab === 'users' ? (
                    isLoading && users.length === 0 ? (
                      <div className="space-y-px p-2">
                        {[...Array(6)].map((_, i) => (
                          <div
                            key={i}
                            className="flex items-center gap-3 rounded-lg px-2 py-2"
                            style={{ animationDelay: `${i * 50}ms` }}
                          >
                            <div className="h-7 w-7 animate-pulse rounded-full bg-surface-tertiary" />
                            <div className="flex-1 space-y-1.5">
                              <div className="h-3 w-24 animate-pulse rounded bg-surface-tertiary" />
                              <div className="h-2.5 w-36 animate-pulse rounded bg-surface-tertiary" />
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : users.length === 0 ? (
                      <div className="flex flex-col items-center justify-center py-16 text-center">
                        <User className="mb-2 h-8 w-8 text-text-secondary/30" />
                        <p className="text-sm text-text-secondary">
                          {search ? 'No users found' : 'No users yet'}
                        </p>
                      </div>
                    ) : (
                      <div className="py-1">
                        {users.map((user) => (
                          <UserListItem
                            key={user.id}
                            user={user}
                            isSelected={selectedUserId === user.id}
                            onSelect={() => setSelectedUserId(user.id)}
                          />
                        ))}
                      </div>
                    )
                  ) : null}
                </div>
              </div>

              {/* ── Right panel ── */}
              <div className="flex flex-1 flex-col overflow-hidden">
                {activeTab === 'promos' ? (
                  <>
                    <div className="border-b border-border-light px-6 py-4">
                      <h3 className="text-base font-semibold text-text-primary">Promo Codes</h3>
                      <p className="mt-0.5 text-xs text-text-secondary">
                        Create and manage promotional codes
                      </p>
                    </div>
                    <PromoPanel open={open} />
                  </>
                ) : selectedUser ? (
                  <SubscriptionDetail
                    key={selectedUser.id}
                    user={selectedUser}
                    onRoleUpdated={() => {
                      /* role label refreshes via query invalidation */
                    }}
                  />
                ) : (
                  <div className="flex flex-1 flex-col items-center justify-center text-center">
                    <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-surface-secondary">
                      <Users className="h-8 w-8 text-text-secondary/40" />
                    </div>
                    <p className="text-sm font-medium text-text-primary">Select a user</p>
                    <p className="mt-1 max-w-[220px] text-xs text-text-secondary">
                      Choose someone from the list to view and manage their subscription
                    </p>
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
