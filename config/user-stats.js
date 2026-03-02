const path = require('path');
require('module-alias')({ base: path.resolve(__dirname, '..', 'api') });
const { silentExit } = require('./helpers');
const { searchUsers } = require('~/models');
const connect = require('./connect');

(async () => {
  await connect();

  console.purple('-----------------------------');
  console.purple('Show the stats of all users');
  console.purple('-----------------------------');

  const users = await searchUsers('');
  const userData = users.map((user) => ({
    User: user.name,
    Email: user.email,
    Created: user.createdAt,
  }));

  console.table(userData);
  console.yellow('Note: Per-user conversation/message counts are not available via Backboard.');

  silentExit(0);
})();

process.on('uncaughtException', (err) => {
  if (!err.message.includes('fetch failed')) {
    console.error('There was an uncaught error:');
    console.error(err);
  }

  if (!err.message.includes('fetch failed')) {
    process.exit(1);
  }
});
