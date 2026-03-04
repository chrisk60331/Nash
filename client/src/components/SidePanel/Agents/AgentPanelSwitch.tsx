import { useEffect } from 'react';
import { AgentPanelProvider, useAgentPanelContext } from '~/Providers/AgentPanelContext';
import { Panel, isEphemeralAgent } from '~/common';
import PlanGate from '~/components/Nav/PlanGate';
import VersionPanel from './Version/VersionPanel';
import { useChatContext } from '~/Providers';
import ActionsPanel from './ActionsPanel';
import { useLocalize } from '~/hooks';
import AgentPanel from './AgentPanel';

export default function AgentPanelSwitch() {
  const localize = useLocalize();
  return (
    <PlanGate requiredPlan="plus" featureName={localize('com_sidepanel_agent_builder')}>
      <AgentPanelProvider>
        <AgentPanelSwitchWithContext />
      </AgentPanelProvider>
    </PlanGate>
  );
}

function AgentPanelSwitchWithContext() {
  const { conversation } = useChatContext();
  const { activePanel, setCurrentAgentId } = useAgentPanelContext();

  useEffect(() => {
    const agent_id = conversation?.agent_id ?? '';
    if (!isEphemeralAgent(agent_id)) {
      setCurrentAgentId(agent_id);
    }
  }, [setCurrentAgentId, conversation?.agent_id]);

  if (activePanel === Panel.actions) {
    return <ActionsPanel />;
  }
  if (activePanel === Panel.version) {
    return <VersionPanel />;
  }
  return <AgentPanel />;
}
