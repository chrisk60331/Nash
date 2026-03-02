const {
  createToolCallBB,
  updateToolCallBB,
  deleteToolCallsBB,
  getToolCallByIdBB,
  getToolCallsByConvoBB,
  getToolCallsByMessageBB,
} = require('@librechat/api');

module.exports = {
  createToolCall: createToolCallBB,
  updateToolCall: updateToolCallBB,
  deleteToolCalls: deleteToolCallsBB,
  getToolCallById: getToolCallByIdBB,
  getToolCallsByConvo: getToolCallsByConvoBB,
  getToolCallsByMessage: getToolCallsByMessageBB,
};
