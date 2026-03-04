import PlanGate from '~/components/Nav/PlanGate';
import { useLocalize } from '~/hooks';
import MemoryPanel from './MemoryPanel';

export default function MemoryPanelGated() {
  const localize = useLocalize();
  return (
    <PlanGate requiredPlan="plus" featureName={localize('com_ui_memory')}>
      <MemoryPanel />
    </PlanGate>
  );
}
