import { useCallback, useEffect } from 'react';
import { useRecoilValue, useSetRecoilState } from 'recoil';
import { replaceSpecialVars } from 'librechat-data-provider';
import { useChatContext, useChatFormContext, useAddedChatContext } from '~/Providers';
import { useAuthContext } from '~/hooks/AuthContext';
import { authModalTabAtom, showAuthModalAtom } from '~/store/authModal';
import { savePendingChatDraft } from '~/utils/auth/pendingChat';
import store from '~/store';

export default function useSubmitMessage() {
  const { user, isAuthenticated } = useAuthContext();
  const methods = useChatFormContext();
  const { conversation: addedConvo } = useAddedChatContext();
  const { ask, index, getMessages, setMessages, latestMessage, conversation } = useChatContext();

  const autoSendPrompts = useRecoilValue(store.autoSendPrompts);
  const setActivePrompt = useSetRecoilState(store.activePromptByIndex(index));
  const setShowAuthModal = useSetRecoilState(showAuthModalAtom);
  const setAuthModalTab = useSetRecoilState(authModalTabAtom);

  useEffect(() => {
    const handlePendingChatDraftSubmit = (
      event: Event,
    ) => {
      const customEvent = event as CustomEvent<{
        text?: string;
        addedConversation?: typeof addedConvo;
      }>;
      const restoredText = customEvent.detail?.text?.trim();
      if (!restoredText || !isAuthenticated) {
        return;
      }

      if (customEvent.detail?.addedConversation) {
        setMessages([...(getMessages() || [])]);
      }

      ask(
        {
          text: restoredText,
        },
        {
          addedConvo: customEvent.detail?.addedConversation ?? addedConvo ?? undefined,
        },
      );
      methods.reset();
    };

    window.addEventListener('submitPendingChatDraft', handlePendingChatDraftSubmit as EventListener);

    return () => {
      window.removeEventListener(
        'submitPendingChatDraft',
        handlePendingChatDraftSubmit as EventListener,
      );
    };
  }, [ask, methods, addedConvo, getMessages, setMessages, isAuthenticated]);

  const submitMessage = useCallback(
    (data?: { text: string }) => {
      if (!data) {
        return console.warn('No data provided to submitMessage');
      }

      if (!isAuthenticated) {
        savePendingChatDraft({
          text: data.text,
          autoSend: true,
          conversation: conversation ? { ...conversation } : null,
          addedConversation: addedConvo ? { ...addedConvo } : null,
          savedAt: Date.now(),
        });
        setAuthModalTab('login');
        setShowAuthModal(true);
        return;
      }

      const rootMessages = getMessages();
      const isLatestInRootMessages = rootMessages?.some(
        (message) => message.messageId === latestMessage?.messageId,
      );
      if (!isLatestInRootMessages && latestMessage) {
        setMessages([...(rootMessages || []), latestMessage]);
      }

      ask(
        {
          text: data.text,
        },
        {
          addedConvo: addedConvo ?? undefined,
        },
      );
      methods.reset();
    },
    [
      ask,
      methods,
      addedConvo,
      conversation,
      setMessages,
      getMessages,
      latestMessage,
      isAuthenticated,
      setAuthModalTab,
      setShowAuthModal,
    ],
  );

  const submitPrompt = useCallback(
    (text: string) => {
      const parsedText = replaceSpecialVars({ text, user });
      if (autoSendPrompts) {
        submitMessage({ text: parsedText });
        return;
      }

      const currentText = methods.getValues('text');
      const newText = currentText.trim().length > 1 ? `\n${parsedText}` : parsedText;
      setActivePrompt(newText);
    },
    [autoSendPrompts, submitMessage, setActivePrompt, methods, user],
  );

  return { submitMessage, submitPrompt };
}
