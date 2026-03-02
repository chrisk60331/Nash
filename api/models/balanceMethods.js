const { getBalanceBB, updateBalanceBB } = require('@librechat/api');

module.exports = {
  checkBalance: getBalanceBB,
  getBalance: getBalanceBB,
  updateBalance: updateBalanceBB,
};
