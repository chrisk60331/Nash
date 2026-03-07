import React, { useMemo, useState } from 'react';
import { Trash2 } from 'lucide-react';
import { Label, OGDialog, OGDialogTrigger, OGDialogTemplate } from '@librechat/client';
import type t from 'librechat-data-provider';
import { useLocalize, TranslationKeys, useAgentCategories } from '~/hooks';
import { cn, renderAgentAvatar, getContactDisplayName } from '~/utils';
import { isEphemeralAgent } from '~/common';
import AgentDetailContent from './AgentDetailContent';

interface AgentCardProps {
  agent: t.Agent;
  onSelect?: (agent: t.Agent) => void;
  onStartChat?: () => void;
  onDelete?: (agentId: string) => void;
  className?: string;
}

/**
 * Card component to display agent information with integrated detail dialog
 */
const AgentCard: React.FC<AgentCardProps> = ({ agent, onSelect, onStartChat, onDelete, className = '' }) => {
  const localize = useLocalize();
  const { categories } = useAgentCategories();
  const [isOpen, setIsOpen] = useState(false);

  const categoryLabel = useMemo(() => {
    if (!agent.category) return '';

    const category = categories.find((cat) => cat.value === agent.category);
    if (category) {
      if (category.label && category.label.startsWith('com_')) {
        return localize(category.label as TranslationKeys);
      }
      return category.label;
    }

    return agent.category.charAt(0).toUpperCase() + agent.category.slice(1);
  }, [agent.category, categories, localize]);

  const displayName = getContactDisplayName(agent);

  const handleOpenChange = (open: boolean) => {
    setIsOpen(open);
    if (open && onSelect) {
      onSelect(agent);
    }
  };

  return (
    <OGDialog open={isOpen} onOpenChange={handleOpenChange}>
      <OGDialogTrigger asChild>
        <div
          className={cn(
            'group relative flex h-32 gap-5 overflow-hidden rounded-xl',
            'cursor-pointer select-none px-6 py-4',
            'bg-surface-tertiary transition-colors duration-150 hover:bg-surface-hover',
            'md:h-36 lg:h-40',
            '[&_*]:cursor-pointer',
            className,
          )}
          aria-label={localize('com_agents_agent_card_label', {
            name: agent.name,
            description: agent.description ?? '',
          })}
          aria-describedby={agent.description ? `agent-${agent.id}-description` : undefined}
          tabIndex={0}
          role="button"
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setIsOpen(true);
            }
          }}
        >
          {/* Category badge - top right (shift left when delete is shown) */}
          {categoryLabel && (
            <span
              className={cn(
                'absolute top-3 rounded-md bg-surface-hover px-2 py-0.5 text-xs text-text-secondary',
                onDelete ? 'right-12' : 'right-4',
              )}
            >
              {categoryLabel}
            </span>
          )}

          {/* Delete action: hover on desktop, always visible on mobile */}
          {onDelete && !isEphemeralAgent(agent.id ?? '') && (
            <div
              className="absolute right-3 top-3 z-10 flex items-center opacity-100 md:opacity-0 md:group-hover:opacity-100"
              onClick={(e) => e.stopPropagation()}
              role="presentation"
            >
              <OGDialog>
                <OGDialogTrigger asChild>
                  <button
                    type="button"
                    className="rounded-md p-1.5 text-red-500 hover:bg-surface-hover hover:text-red-600"
                    aria-label={localize('com_ui_delete_agent')}
                    title={localize('com_ui_delete_agent')}
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                </OGDialogTrigger>
                <OGDialogTemplate
                  title={localize('com_ui_delete_agent')}
                  className="max-w-[450px]"
                  main={
                    <p className="text-left text-sm text-text-secondary">
                      {localize('com_ui_delete_agent_confirm')}
                    </p>
                  }
                  selection={{
                    selectHandler: () => onDelete(agent.id ?? ''),
                    selectClasses: 'bg-red-600 hover:bg-red-700 dark:hover:bg-red-800 text-white',
                    selectText: localize('com_ui_delete'),
                  }}
                />
              </OGDialog>
            </div>
          )}

          {/* Avatar */}
          <div className="flex-shrink-0 self-center">
            <div className="overflow-hidden rounded-full shadow-[0_0_15px_rgba(0,0,0,0.3)] dark:shadow-[0_0_15px_rgba(0,0,0,0.5)]">
              {renderAgentAvatar(agent, { size: 'sm', showBorder: false })}
            </div>
          </div>

          {/* Content */}
          <div className="flex min-w-0 flex-1 flex-col justify-center overflow-hidden">
            {/* Agent name */}
            <Label className="line-clamp-2 text-base font-semibold text-text-primary md:text-lg">
              {agent.name}
            </Label>

            {/* Agent description */}
            {agent.description && (
              <p
                id={`agent-${agent.id}-description`}
                className="mt-0.5 line-clamp-2 text-sm leading-snug text-text-secondary md:line-clamp-5"
                aria-label={localize('com_agents_description_card', {
                  description: agent.description,
                })}
              >
                {agent.description}
              </p>
            )}

            {/* Author */}
            {displayName && (
              <div className="mt-1 text-xs text-text-tertiary">
                <span className="truncate">
                  {localize('com_ui_by_author', { 0: displayName || '' })}
                </span>
              </div>
            )}
          </div>
        </div>
      </OGDialogTrigger>

      <AgentDetailContent agent={agent} onStartChat={onStartChat} />
    </OGDialog>
  );
};

export default AgentCard;
