import { useState, memo, useCallback } from 'react';
import { useRecoilState } from 'recoil';
import { FolderIcon, FolderOpenIcon, Plus, Trash2 } from 'lucide-react';
import {
  Button,
  OGDialog,
  OGDialogClose,
  OGDialogTitle,
  OGDialogHeader,
  OGDialogContent,
  TooltipAnchor,
} from '@librechat/client';
import { useFoldersQuery, useDeleteFolderMutation } from '~/data-provider';
import { useLocalize, useNewConvo } from '~/hooks';
import CreateFolderModal from './CreateFolderModal';
import { cn } from '~/utils';
import store from '~/store';

import type { TFolder } from 'librechat-data-provider';

function FolderItem({
  folder,
  isActive,
  onSelect,
  onDelete,
}: {
  folder: TFolder;
  isActive: boolean;
  onSelect: (folderId: string | null) => void;
  onDelete: (folder: TFolder) => void;
}) {
  const Icon = isActive ? FolderOpenIcon : FolderIcon;
  const selectFolder = () => onSelect(folder.folderId);

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={selectFolder}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          selectFolder();
        }
      }}
      className={cn(
        'group flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm transition-colors',
        'cursor-pointer focus-visible:ring-2 focus-visible:ring-black focus-visible:outline-none dark:focus-visible:ring-white',
        isActive
          ? 'bg-surface-hover text-text-primary'
          : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary',
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      <span className="truncate">{folder.name}</span>
      {folder.sharedMemory ? null : (
        <span className="ml-auto shrink-0 text-[10px] uppercase tracking-wider text-text-tertiary opacity-0 group-hover:opacity-100">
          isolated
        </span>
      )}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onDelete(folder);
        }}
        className="ml-auto shrink-0 rounded p-0.5 opacity-0 transition-opacity hover:bg-surface-tertiary group-hover:opacity-100"
        aria-label="Delete folder"
      >
        <Trash2 className="h-3.5 w-3.5 text-text-secondary" />
      </button>
    </div>
  );
}

interface FoldersListProps {
  toggleNav?: () => void;
}

const FoldersList = memo(({ toggleNav }: FoldersListProps) => {
  const localize = useLocalize();
  const { newConversation } = useNewConvo();
  const [activeFolderId, setActiveFolderId] = useRecoilState(store.activeFolderId);
  const [modalOpen, setModalOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<TFolder | null>(null);

  const { data: folders } = useFoldersQuery();
  const deleteMutation = useDeleteFolderMutation();

  const handleSelect = useCallback(
    (folderId: string | null) => {
      setActiveFolderId(folderId);
      if (folderId) {
        newConversation({ template: { folderId } });
        toggleNav?.();
      }
    },
    [setActiveFolderId, newConversation, toggleNav],
  );

  const handleDeleteRequest = useCallback((folder: TFolder) => {
    setDeleteTarget(folder);
  }, []);

  const confirmDelete = useCallback(() => {
    if (!deleteTarget) {
      return;
    }
    if (activeFolderId === deleteTarget.folderId) {
      setActiveFolderId(null);
    }
    deleteMutation.mutate(deleteTarget.folderId);
    setDeleteTarget(null);
  }, [deleteTarget, activeFolderId, setActiveFolderId, deleteMutation]);

  return (
    <div className="mb-1 flex flex-col gap-0.5 px-1">
      <div className="flex items-center justify-between px-1 py-1">
        <span className="text-xs font-medium uppercase tracking-wider text-text-tertiary">
          {localize('com_folder_folders')}
        </span>
        <TooltipAnchor description={localize('com_folder_create')} side="right">
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0"
            onClick={() => setModalOpen(true)}
          >
            <Plus className="h-3.5 w-3.5 text-text-secondary" />
          </Button>
        </TooltipAnchor>
      </div>

      {folders?.map((folder) => (
        <FolderItem
          key={folder.folderId}
          folder={folder}
          isActive={activeFolderId === folder.folderId}
          onSelect={handleSelect}
          onDelete={handleDeleteRequest}
        />
      ))}

      <CreateFolderModal open={modalOpen} onOpenChange={setModalOpen} />

      <OGDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <OGDialogContent className="w-11/12 max-w-md" showCloseButton={false}>
          <OGDialogHeader>
            <OGDialogTitle>{localize('com_folder_delete')}</OGDialogTitle>
          </OGDialogHeader>
          <p className="text-sm text-text-secondary">
            {localize('com_folder_delete_confirm')}
          </p>
          {deleteTarget && (
            <p className="truncate text-sm font-medium text-text-primary">
              &ldquo;{deleteTarget.name}&rdquo;
            </p>
          )}
          <div className="flex justify-end gap-4 pt-4">
            <OGDialogClose asChild>
              <Button variant="outline">{localize('com_ui_cancel')}</Button>
            </OGDialogClose>
            <Button
              variant="destructive"
              onClick={confirmDelete}
              disabled={deleteMutation.isLoading}
            >
              {localize('com_ui_delete')}
            </Button>
          </div>
        </OGDialogContent>
      </OGDialog>
    </div>
  );
});

FoldersList.displayName = 'FoldersList';
export default FoldersList;
