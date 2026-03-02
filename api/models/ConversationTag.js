const {
  getConversationTagsBB,
  createConversationTagBB,
  updateConversationTagBB,
  deleteConversationTagBB,
  updateTagsForConversationBB,
  bulkIncrementTagCountsBB,
} = require('@librechat/api');

module.exports = {
  getConversationTags: getConversationTagsBB,
  createConversationTag: createConversationTagBB,
  updateConversationTag: updateConversationTagBB,
  deleteConversationTag: deleteConversationTagBB,
  bulkIncrementTagCounts: bulkIncrementTagCountsBB,
  updateTagsForConversation: updateTagsForConversationBB,
};
