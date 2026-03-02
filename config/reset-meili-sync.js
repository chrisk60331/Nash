const path = require('path');
require('module-alias')({ base: path.resolve(__dirname, '..', 'api') });
const { silentExit } = require('./helpers');

(async () => {
  console.purple('---------------------------------------');
  console.purple('Reset MeiliSearch Synchronization Flags');
  console.purple('---------------------------------------');
  console.yellow('Migration not needed (Backboard storage).');
  console.yellow('MeiliSearch synchronization is no longer used with Backboard.');
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
