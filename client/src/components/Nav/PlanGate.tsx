import { useState } from 'react';
import { Lock } from 'lucide-react';
import { useGetSubscription, useGetStartupConfig } from '~/data-provider';
import BillingModal from './BillingModal';
import { useLocalize } from '~/hooks';

type PlanTier = 'free' | 'plus' | 'unlimited';

const PLAN_ORDER: Record<PlanTier, number> = { free: 0, plus: 1, unlimited: 2 };

interface PlanGateProps {
  requiredPlan: PlanTier;
  featureName: string;
  children: React.ReactNode;
}

export default function PlanGate({ requiredPlan, featureName, children }: PlanGateProps) {
  const localize = useLocalize();
  const { data: startupConfig } = useGetStartupConfig();
  const billingEnabled = !!startupConfig?.billing?.enabled;
  const { data: subscription } = useGetSubscription({ enabled: billingEnabled });
  const [showBilling, setShowBilling] = useState(false);

  const currentPlan: PlanTier = subscription?.plan ?? 'free';
  const hasAccess = PLAN_ORDER[currentPlan] >= PLAN_ORDER[requiredPlan];

  if (!billingEnabled || hasAccess) {
    return <>{children}</>;
  }

  return (
    <div className="relative">
      <div className="pointer-events-none select-none opacity-30" aria-hidden="true">
        {children}
      </div>
      <div
        className="absolute inset-0 flex cursor-pointer flex-col items-center justify-center rounded-lg bg-surface-primary/80 backdrop-blur-[2px]"
        onClick={() => setShowBilling(true)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            setShowBilling(true);
          }
        }}
      >
        <Lock className="mb-2 h-6 w-6 text-text-secondary" />
        <p className="text-sm font-medium text-text-primary">
          {localize('com_billing_upgrade_to_unlock', { plan: requiredPlan.charAt(0).toUpperCase() + requiredPlan.slice(1) })}
        </p>
        <p className="mt-1 text-xs text-text-secondary">{featureName}</p>
      </div>
      {showBilling && <BillingModal open={showBilling} onOpenChange={setShowBilling} />}
    </div>
  );
}
