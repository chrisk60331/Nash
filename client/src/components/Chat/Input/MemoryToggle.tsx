import React, { memo, useState, useCallback, useMemo } from 'react';
import { Brain, Lock } from 'lucide-react';
import { Permissions, PermissionTypes } from 'librechat-data-provider';
import { useRecoilValue } from 'recoil';
import { useLocalize, useHasAccess } from '~/hooks';
import { useGetSubscription, useGetStartupConfig } from '~/data-provider';
import { useBadgeRowContext } from '~/Providers';
import BillingModal from '~/components/Nav/BillingModal';
import store from '~/store';
import { cn } from '~/utils';

type MemoryMode = 'Auto' | 'On' | 'Off';
type PlanTier = 'free' | 'plus' | 'unlimited';

const MODE_CYCLE: MemoryMode[] = ['Auto', 'On', 'Off'];
const PLAN_ORDER: Record<PlanTier, number> = { free: 0, plus: 1, unlimited: 2 };

function getNextMode(current: MemoryMode): MemoryMode {
  const idx = MODE_CYCLE.indexOf(current);
  return MODE_CYCLE[(idx + 1) % MODE_CYCLE.length];
}

function normalizeMode(value: unknown): MemoryMode {
  if (value === 'On' || value === 'Off' || value === 'Auto') {
    return value as MemoryMode;
  }
  return 'Auto';
}

function MemoryToggle() {
  const localize = useLocalize();
  const { memory: memoryData } = useBadgeRowContext();
  const { toolValue, handleChange } = memoryData;
  const [showBilling, setShowBilling] = useState(false);
  const isTemporary = useRecoilValue(store.isTemporary);

  const { data: startupConfig } = useGetStartupConfig();
  const billingEnabled = !!startupConfig?.billing?.enabled;
  const { data: subscription } = useGetSubscription({ enabled: billingEnabled });
  const currentPlan: PlanTier = (subscription?.plan as PlanTier) ?? 'free';
  const isLocked = billingEnabled && PLAN_ORDER[currentPlan] < PLAN_ORDER['plus'];

  const canUseMemories = useHasAccess({
    permissionType: PermissionTypes.MEMORIES,
    permission: Permissions.USE,
  });

  const mode = useMemo(
    () => (isTemporary ? 'Off' : normalizeMode(toolValue)),
    [isTemporary, toolValue],
  );

  const handleClick = useCallback(() => {
    if (isLocked) {
      setShowBilling(true);
      return;
    }
    if (isTemporary) {
      return;
    }
    const next = getNextMode(mode);
    handleChange({ value: next });
  }, [mode, handleChange, isLocked, isTemporary]);

  if (!canUseMemories) {
    return null;
  }

  return (
    <>
      <button
        type="button"
        onClick={handleClick}
        className={cn(
          'flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors',
          isLocked && 'cursor-pointer border-border-light bg-transparent text-text-tertiary hover:bg-surface-hover',
          !isLocked && mode === 'On' && 'border-purple-600/40 bg-purple-500/10 text-purple-700 hover:bg-purple-700/10 dark:text-purple-300',
          !isLocked && mode === 'Auto' && 'border-border-medium bg-surface-secondary text-text-secondary hover:bg-surface-hover',
          !isLocked && mode === 'Off' && 'border-border-light bg-transparent text-text-tertiary hover:bg-surface-hover',
        )}
        aria-label={isLocked ? `${localize('com_ui_memory')} (Plus)` : `${localize('com_ui_memory')}: ${mode}`}
        title={isLocked ? `${localize('com_ui_memory')} — upgrade to Plus` : `${localize('com_ui_memory')}: ${mode}`}
      >
        {isLocked ? (
          <Lock className="h-3.5 w-3.5" aria-hidden="true" />
        ) : (
          <Brain className="h-4 w-4" aria-hidden="true" />
        )}
        <span>
          {localize('com_ui_memory')}{!isLocked && ` ${mode}`}
        </span>
      </button>
      {showBilling && <BillingModal open={showBilling} onOpenChange={setShowBilling} />}
    </>
  );
}

export default memo(MemoryToggle);
