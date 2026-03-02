const { logger } = require('@librechat/data-schemas');
const {
  getConvoBB,
  saveConvoBB,
  bulkSaveConvosBB,
  getConvosByCursorBB,
  getConvosQueriedBB,
  getConvoTitleBB,
  deleteConvosBB,
  searchConversationBB,
  getConvoFilesBB,
  deleteNullOrEmptyConversationsBB,
} = require('@librechat/api');

const searchConversation = async (conversationId) => {
  try {
    return await searchConversationBB(conversationId);
  } catch (error) {
    logger.error('[searchConversation] Error searching conversation', error);
    throw new Error('Error searching conversation');
  }
};

const getConvo = async (user, conversationId) => {
  try {
    return await getConvoBB(user, conversationId);
  } catch (error) {
    logger.error('[getConvo] Error getting single conversation', error);
    throw new Error('Error getting single conversation');
  }
};

const deleteNullOrEmptyConversations = async () => {
  return deleteNullOrEmptyConversationsBB();
};

const getConvoFiles = async (conversationId) => {
  try {
    return await getConvoFilesBB(conversationId);
  } catch (error) {
    logger.error('[getConvoFiles] Error getting conversation files', error);
    throw new Error('Error getting conversation files');
  }
};

module.exports = {
  getConvoFiles,
  searchConversation,
  deleteNullOrEmptyConversations,
  saveConvo: async (req, { conversationId, newConversationId, ...convo }, metadata) => {
    return saveConvoBB(req, { conversationId, newConversationId, ...convo }, metadata);
  },
  bulkSaveConvos: async (conversations) => {
    return bulkSaveConvosBB(conversations);
  },
  getConvosByCursor: async (user, opts = {}) => {
    return getConvosByCursorBB(user, opts);
  },
  getConvosQueried: async (user, convoIds, cursor = null, limit = 25) => {
    return getConvosQueriedBB(user, convoIds, cursor, limit);
  },
  getConvo,
  getConvoTitle: async (user, conversationId) => {
    try {
      return await getConvoTitleBB(user, conversationId);
    } catch (error) {
      logger.error('[getConvoTitle] Error getting conversation title', error);
      throw new Error('Error getting conversation title');
    }
  },
  deleteConvos: async (user, filter) => {
    return deleteConvosBB(user, filter);
  },
};
