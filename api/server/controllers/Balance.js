const { getBalance } = require('~/models');

async function balanceController(req, res) {
  const balanceData = await getBalance(req.user.id);

  if (!balanceData) {
    return res.status(404).json({ error: 'Balance not found' });
  }

  if (!balanceData.autoRefillEnabled) {
    delete balanceData.refillIntervalValue;
    delete balanceData.refillIntervalUnit;
    delete balanceData.lastRefill;
    delete balanceData.refillAmount;
  }

  res.status(200).json(balanceData);
}

module.exports = balanceController;
