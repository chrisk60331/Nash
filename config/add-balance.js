const path = require('path');
const { getBalanceConfig } = require('@librechat/api');
require('module-alias')({ base: path.resolve(__dirname, '..', 'api') });
const { findUser } = require('~/models');
const { createTransaction } = require('~/models/Transaction');
const { getAppConfig } = require('~/server/services/Config');
const { askQuestion, silentExit } = require('./helpers');
const connect = require('./connect');

(async () => {
  await connect();

  console.purple('--------------------------');
  console.purple('Add balance to a user account!');
  console.purple('--------------------------');

  let email = '';
  let amount = '';
  if (process.argv.length >= 3) {
    email = process.argv[2];
    amount = process.argv[3];
  } else {
    console.orange('Usage: npm run add-balance <email> <amount>');
    console.orange('Note: if you do not pass in the arguments, you will be prompted for them.');
    console.purple('--------------------------');
  }

  const appConfig = await getAppConfig();
  const balanceConfig = getBalanceConfig(appConfig);

  if (!balanceConfig?.enabled) {
    console.red('Error: Balance is not enabled. Use librechat.yaml to enable it');
    silentExit(1);
  }

  if (!email) {
    email = await askQuestion('Email:');
  }
  if (!email.includes('@')) {
    console.red('Error: Invalid email address!');
    silentExit(1);
  }

  if (!amount) {
    amount = await askQuestion('amount: (default is 1000 tokens if empty or 0)');
  }
  if (!amount) {
    amount = 1000;
  }

  const user = await findUser({ email });
  if (!user) {
    console.red('Error: No user with that email was found!');
    silentExit(1);
  } else {
    console.purple(`Found user: ${user.email}`);
  }

  let result;
  try {
    result = await createTransaction({
      user: user._id,
      tokenType: 'credits',
      context: 'admin',
      rawAmount: +amount,
      balance: balanceConfig,
    });
  } catch (error) {
    console.red('Error: ' + error.message);
    console.error(error);
    silentExit(1);
  }

  if (!result?.balance) {
    console.red('Error: Something went wrong while updating the balance!');
    console.error(result);
    silentExit(1);
  }

  console.green('Transaction created successfully!');
  console.purple(`Amount: ${amount}
New Balance: ${result.balance}`);
  silentExit(0);
})();

process.on('uncaughtException', (err) => {
  if (!err.message.includes('fetch failed')) {
    console.error('There was an uncaught error:');
    console.error(err);
  }

  if (err.message.includes('fetch failed')) {
    return;
  } else {
    process.exit(1);
  }
});
