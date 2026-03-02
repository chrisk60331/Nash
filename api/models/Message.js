const { z } = require('zod');
const { logger } = require('@librechat/data-schemas');
const {
  saveMessageBB,
  bulkSaveMessagesBB,
  recordMessageBB,
  updateMessageTextBB,
  updateMessageBB,
  deleteMessagesSinceBB,
  getMessagesBB,
  getMessageBB,
  deleteMessagesBB,
} = require('@librechat/api');

const idSchema = z.string().uuid();

async function saveMessage(req, params, metadata) {
  if (!req?.user?.id) {
    throw new Error('User not authenticated');
  }

  const validConvoId = idSchema.safeParse(params.conversationId);
  if (!validConvoId.success) {
    logger.warn(`Invalid conversation ID: ${params.conversationId}`);
    logger.info(`---\`saveMessage\` context: ${metadata?.context}`);
    return;
  }

  return saveMessageBB(req, params, metadata);
}

async function bulkSaveMessages(messages, overrideTimestamp = false) {
  return bulkSaveMessagesBB(messages);
}

async function recordMessage(params) {
  return recordMessageBB(params);
}

async function updateMessageText(req, { messageId, text }) {
  return updateMessageTextBB(req, { messageId, text });
}

async function updateMessage(req, message, metadata) {
  try {
    return await updateMessageBB(req, message, metadata);
  } catch (err) {
    logger.error('Error updating message:', err);
    if (metadata?.context) {
      logger.info(`---\`updateMessage\` context: ${metadata.context}`);
    }
    throw err;
  }
}

async function deleteMessagesSince(req, { messageId, conversationId }) {
  return deleteMessagesSinceBB(req, { messageId, conversationId });
}

async function getMessages(filter, select) {
  return getMessagesBB(filter, select);
}

async function getMessage({ user, messageId }) {
  return getMessageBB({ user, messageId });
}

async function deleteMessages(filter) {
  return deleteMessagesBB(filter);
}

module.exports = {
  saveMessage,
  bulkSaveMessages,
  recordMessage,
  updateMessageText,
  updateMessage,
  deleteMessagesSince,
  getMessages,
  getMessage,
  deleteMessages,
};
