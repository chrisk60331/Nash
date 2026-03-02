const path = require('path');
require('module-alias')({ base: path.resolve(__dirname, '..', 'api') });
const { silentExit } = require('./helpers');

(async () => {
  console.purple('--------------------------');
  console.purple('Set balance to a user account!');
  console.purple('--------------------------');
  console.yellow('Balance management is handled by Backboard. This script is no longer needed.');
  console.yellow('Use the Backboard admin interface to manage user balances.');
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
