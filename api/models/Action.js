const {
  getActionsBB,
  updateActionBB,
  deleteActionBB,
  deleteActionsBB,
} = require('@librechat/api');

module.exports = {
  getActions: getActionsBB,
  updateAction: updateActionBB,
  deleteAction: deleteActionBB,
  deleteActions: deleteActionsBB,
};
