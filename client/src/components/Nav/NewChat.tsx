import React, { useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useSetRecoilState } from 'recoil';
import { QueryKeys } from 'librechat-data-provider';
import { useQueryClient } from '@tanstack/react-query';
import { TooltipAnchor, NewChatIcon, MobileSidebar, Sidebar, Button } from '@librechat/client';
import { CLOSE_SIDEBAR_ID, OPEN_SIDEBAR_ID } from '~/components/Chat/Menus/OpenSidebar';
import { useLocalize, useNewConvo } from '~/hooks';
import { clearMessagesCache } from '~/utils';
import store from '~/store';

export default function NewChat({
  index = 0,
  toggleNav,
  subHeaders,
  isSmallScreen,
  headerButtons,
}: {
  index?: number;
  toggleNav: () => void;
  isSmallScreen?: boolean;
  subHeaders?: React.ReactNode;
  headerButtons?: React.ReactNode;
}) {
  const queryClient = useQueryClient();
  const setActiveFolderId = useSetRecoilState(store.activeFolderId);
  /** Note: this component needs an explicit index passed if using more than one */
  const { newConversation: newConvo } = useNewConvo(index);
  const localize = useLocalize();
  const { conversation } = store.useCreateConversationAtom(index);

  const handleToggleNav = useCallback(() => {
    toggleNav();
    // Delay focus until after the sidebar animation completes (200ms)
    setTimeout(() => {
      document.getElementById(OPEN_SIDEBAR_ID)?.focus();
    }, 250);
  }, [toggleNav]);

  const clickHandler: React.MouseEventHandler<HTMLAnchorElement> = useCallback(
    (e) => {
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) {
        return;
      }

      e.preventDefault();
      setActiveFolderId(null);
      clearMessagesCache(queryClient, conversation?.conversationId);
      queryClient.invalidateQueries([QueryKeys.messages]);
      newConvo({ template: { folderId: null } });
      if (isSmallScreen) {
        toggleNav();
      }
    },
    [queryClient, conversation, newConvo, toggleNav, isSmallScreen, setActiveFolderId],
  );

  return (
    <>
      <div className="relative flex items-center justify-between px-0.5 py-[2px] md:py-2">
        <TooltipAnchor
          description={localize('com_nav_close_sidebar')}
          render={
            <Button
              id={CLOSE_SIDEBAR_ID}
              size="icon"
              variant="outline"
              data-testid="close-sidebar-button"
              aria-label={localize('com_nav_close_sidebar')}
              aria-expanded={true}
              className="rounded-full border-none bg-transparent duration-0 hover:bg-surface-active-alt focus-visible:ring-inset focus-visible:ring-black focus-visible:ring-offset-0 dark:focus-visible:ring-white md:rounded-xl"
              onClick={handleToggleNav}
            >
              <Sidebar aria-hidden="true" className="max-md:hidden" />
              <MobileSidebar
                aria-hidden="true"
                className="icon-lg m-1 inline-flex items-center justify-center md:hidden"
              />
            </Button>
          }
        />
        <img
          src="/assets/nash.png"
          alt="Nash"
          className="pointer-events-none absolute h-[31px] object-contain dark:hidden"
          style={{ left: '50%', top: '50%', transform: 'translate(-50%, -50%)' }}
        />
        <img
          src="/assets/nash_dark.png"
          alt="Nash"
          className="pointer-events-none absolute hidden h-[31px] object-contain dark:block"
          style={{ left: '50%', top: '50%', transform: 'translate(-50%, -50%)' }}
        />
        <div className="flex gap-0.5">
          {headerButtons}

          <TooltipAnchor
            description={localize('com_ui_new_chat')}
            render={
              <Button
                asChild
                size="icon"
                variant="outline"
                data-testid="nav-new-chat-button"
                aria-label={localize('com_ui_new_chat')}
                className="rounded-full border-none bg-transparent duration-0 hover:bg-surface-active-alt focus-visible:ring-inset focus-visible:ring-black focus-visible:ring-offset-0 dark:focus-visible:ring-white md:rounded-xl"
              >
                <Link to="/c/new" state={{ focusChat: true }} onClick={clickHandler}>
                  <NewChatIcon className="icon-lg text-text-primary" />
                </Link>
              </Button>
            }
          />
        </div>
      </div>
      {subHeaders != null ? subHeaders : null}
    </>
  );
}
