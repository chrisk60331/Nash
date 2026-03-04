import { useState, useCallback } from 'react';
import { Search, ChevronDown, ChevronUp, Shield } from 'lucide-react';
import { Dialog, DialogPanel, DialogTitle, Transition, TransitionChild } from '@headlessui/react';
import { QueryKeys, dataService } from 'librechat-data-provider';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { AdminUser, AdminSubscription } from 'librechat-data-provider';
import type { TDialogProps } from '~/common';
import { cn } from '~/utils';

type PlanTier = 'free' | 'plus' | 'unlimited';

const PLAN_STYLES: Record<PlanTier, string> = {
  free: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400',
  plus: 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-400',
  unlimited: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400',
};

function PlanBadge({ plan }: { plan: PlanTier }) {
  return (
    <span
      className={cn(
        'rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase leading-none',
        PLAN_STYLES[plan] ?? PLAN_STYLES.free,
      )}
    >
      {plan}
    </span>
  );
}

function UserRow({
  user,
  isExpanded,
  onToggle,
}: {
  user: AdminUser;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="border-b border-border-light last:border-b-0">
      <button
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-hover"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium text-text-primary">
              {user.name || user.username}
            </span>
            {user.role === 'ADMIN' && (
              <Shield className="h-3.5 w-3.5 flex-shrink-0 text-blue-500" />
            )}
          </div>
          <span className="text-xs text-text-secondary">{user.email}</span>
        </div>
        {isExpanded ? (
          <ChevronUp className="h-4 w-4 text-text-secondary" />
        ) : (
          <ChevronDown className="h-4 w-4 text-text-secondary" />
        )}
      </button>
      {isExpanded && <SubscriptionEditor userId={user.id} userName={user.name || user.email} currentRole={user.role} />}
    </div>
  );
}

function SubscriptionEditor({ userId, userName, currentRole }: { userId: string; userName: string; currentRole: string }) {
  const queryClient = useQueryClient();
  const { data: sub, isLoading } = useQuery<AdminSubscription>(
    [QueryKeys.adminUserSubscription, userId],
    () => dataService.getAdminUserSubscription(userId),
    { staleTime: 10_000 },
  );

  const mutation = useMutation(
    (data: { plan?: string; usageTokens?: number }) =>
      dataService.updateAdminUserSubscription(userId, data),
    {
      onSuccess: () => {
        queryClient.invalidateQueries([QueryKeys.adminUserSubscription, userId]);
        queryClient.invalidateQueries([QueryKeys.adminUsers]);
      },
    },
  );

  const roleMutation = useMutation(
    (role: string) => dataService.setAdminUserRole(userId, role),
    {
      onSuccess: () => {
        queryClient.invalidateQueries([QueryKeys.adminUsers]);
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

  if (isLoading || !sub) {
    return (
      <div className="px-4 pb-4 pt-1 text-xs text-text-secondary">Loading subscription...</div>
    );
  }

  const currentPlan = (pendingPlan ?? sub.plan) as PlanTier;

  const isAdmin = currentRole === 'ADMIN';

  return (
    <div className="space-y-3 border-t border-border-light bg-surface-secondary/50 px-4 py-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-text-secondary">Role</span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-primary">{isAdmin ? 'Admin' : 'User'}</span>
          <button
            onClick={() => roleMutation.mutate(isAdmin ? 'USER' : 'ADMIN')}
            disabled={roleMutation.isLoading}
            className={cn(
              'rounded px-2 py-0.5 text-[10px] font-medium transition-colors',
              isAdmin
                ? 'text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/30'
                : 'text-blue-600 hover:bg-blue-50 dark:text-blue-400 dark:hover:bg-blue-950/30',
            )}
          >
            {roleMutation.isLoading ? '...' : isAdmin ? 'Demote' : 'Promote'}
          </button>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-text-secondary">Plan</span>
        <div className="flex gap-1">
          {(['free', 'plus', 'unlimited'] as PlanTier[]).map((p) => (
            <button
              key={p}
              onClick={() => handlePlanChange(p)}
              disabled={mutation.isLoading}
              className={cn(
                'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                currentPlan === p
                  ? 'bg-surface-tertiary text-text-primary ring-1 ring-border-heavy'
                  : 'text-text-secondary hover:bg-surface-hover',
              )}
            >
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-text-secondary">Token usage</span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-primary">
            {new Intl.NumberFormat().format(sub.usageTokens)}
            {sub.includedTokens > 0 && (
              <span className="text-text-secondary">
                {' '}/ {new Intl.NumberFormat().format(sub.includedTokens)}
              </span>
            )}
          </span>
          {sub.usageTokens > 0 && (
            <button
              onClick={handleResetUsage}
              disabled={mutation.isLoading}
              className="rounded px-1.5 py-0.5 text-[10px] font-medium text-red-600 transition-colors hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/30"
            >
              Reset
            </button>
          )}
        </div>
      </div>

      {sub.stripeCustomerId && (
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-text-secondary">Stripe</span>
          <span className="truncate text-xs text-text-secondary">{sub.stripeCustomerId}</span>
        </div>
      )}

      {sub.periodEnd && (
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-text-secondary">Period ends</span>
          <span className="text-xs text-text-secondary">
            {new Date(sub.periodEnd).toLocaleDateString()}
          </span>
        </div>
      )}

      {(mutation.isError || roleMutation.isError) && (
        <div className="text-xs text-red-500">Failed to update. Try again.</div>
      )}
    </div>
  );
}

export default function AdminUsersModal({ open, onOpenChange }: TDialogProps) {
  const [search, setSearch] = useState('');
  const [expandedUser, setExpandedUser] = useState<string | null>(null);

  const { data, isLoading } = useQuery(
    [QueryKeys.adminUsers, search],
    () => dataService.getAdminUsers(search || undefined),
    {
      staleTime: 15_000,
      keepPreviousData: true,
      enabled: open,
    },
  );

  const users = data?.users ?? [];

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
            <DialogPanel className="flex max-h-[80vh] w-full max-w-lg flex-col overflow-hidden rounded-xl bg-background shadow-2xl backdrop-blur-2xl animate-in sm:rounded-2xl">
              <DialogTitle
                className="flex items-center justify-between border-b border-border-light p-4"
                as="div"
              >
                <div className="flex items-center gap-2">
                  <Shield className="h-5 w-5 text-blue-500" />
                  <h2 className="text-base font-semibold text-text-primary">User Management</h2>
                  {data && (
                    <span className="text-xs text-text-secondary">({data.total} users)</span>
                  )}
                </div>
                <button
                  type="button"
                  className="rounded-sm opacity-70 transition-opacity hover:opacity-100 focus:outline-none"
                  onClick={() => onOpenChange(false)}
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="text-text-primary"
                  >
                    <line x1="18" x2="6" y1="6" y2="18" />
                    <line x1="6" x2="18" y1="6" y2="18" />
                  </svg>
                </button>
              </DialogTitle>

              <div className="border-b border-border-light px-4 py-2">
                <div className="relative">
                  <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
                  <input
                    type="text"
                    placeholder="Search by name or email..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="w-full rounded-lg border border-border-medium bg-transparent py-1.5 pl-9 pr-3 text-sm text-text-primary placeholder-text-secondary focus:border-border-heavy focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex-1 overflow-y-auto">
                {isLoading && users.length === 0 ? (
                  <div className="px-4 py-8 text-center text-sm text-text-secondary">
                    Loading users...
                  </div>
                ) : users.length === 0 ? (
                  <div className="px-4 py-8 text-center text-sm text-text-secondary">
                    {search ? 'No users found' : 'No users'}
                  </div>
                ) : (
                  users.map((user) => (
                    <UserRow
                      key={user.id}
                      user={user}
                      isExpanded={expandedUser === user.id}
                      onToggle={() =>
                        setExpandedUser((prev) => (prev === user.id ? null : user.id))
                      }
                    />
                  ))
                )}
              </div>
            </DialogPanel>
          </div>
        </TransitionChild>
      </Dialog>
    </Transition>
  );
}
