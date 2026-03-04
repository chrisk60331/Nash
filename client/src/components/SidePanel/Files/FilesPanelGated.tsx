import PlanGate from '~/components/Nav/PlanGate';
import { useLocalize } from '~/hooks';
import FilesPanel from './Panel';

export default function FilesPanelGated() {
  const localize = useLocalize();
  return (
    <PlanGate requiredPlan="plus" featureName={localize('com_sidepanel_attach_files')}>
      <FilesPanel />
    </PlanGate>
  );
}
