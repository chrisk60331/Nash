import { Building2, ArrowUpRight } from 'lucide-react';
import { Button } from '@librechat/client';
import { cn } from '~/utils';

export default function EnterpriseUpsellCard({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'group rounded-2xl border border-bb-blue/30 bg-gradient-to-br from-bb-blue/10 via-background to-bb-steel/20 p-4 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md dark:border-bb-blue/40 dark:from-bb-blue/20 dark:to-bb-steelDark/40',
        className,
      )}
    >
      <div className="mb-3 inline-flex items-center gap-2 rounded-xl bg-bb-blue/15 px-2.5 py-1.5 text-bb-blue dark:bg-bb-blue/45 dark:text-white">
        <Building2 className="h-4 w-4" />
        <span className="text-xs font-semibold tracking-wide">Built on Backboard.io</span>
      </div>

      <p className="text-sm font-semibold text-text-primary">Enterprise workspace setup</p>
      <p className="mt-2 text-xs leading-5 text-text-secondary">
        Get custom guardrails, team controls, and a setup tailored to your company.
      </p>
      <p className="mt-1 text-xs leading-5 text-text-secondary">
        Our team can help you integrate Backboard.io into your AI stack.
      </p>

      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => {
          window.location.href = 'mailto:support@backboard.io?subject=Enterprise%20workspace%20setup';
        }}
        className="mt-3 w-full border-bb-blue/30 text-bb-blue transition-colors duration-200 hover:bg-bb-blue/10 hover:text-bb-blueDark active:scale-[0.97] dark:border-bb-blue/60 dark:text-white dark:hover:bg-bb-blue/35 dark:hover:text-white"
      >
        <span>Contact support</span>
        <ArrowUpRight className="ml-1 h-3.5 w-3.5" aria-hidden />
      </Button>
    </div>
  );
}
