#!/usr/bin/env node
const path = require('path');
require('module-alias')({ base: path.resolve(__dirname, '..', 'api') });
const {
  findUser,
  deleteUserById,
  deleteConvos,
  deleteMessages,
  deletePresets,
  deleteFiles,
  deleteTokens,
  deleteAllUserSessions,
  deleteAllSharedLinks,
  deleteAllUserPluginAuths,
  deleteAllAgentApiKeys,
} = require('~/models');
const { askQuestion, silentExit } = require('./helpers');
const connect = require('./connect');

(async () => {
  await connect();

  console.purple('---------------');
  console.purple('Deleting a user and all related data');
  console.purple('---------------');

  let email = process.argv[2]?.trim();
  if (!email) {
    email = (await askQuestion('Email:')).trim();
  }

  const user = await findUser({ email: email.toLowerCase() });
  if (!user) {
    console.yellow(`No user found with email "${email}"`);
    silentExit(0);
  }

  const confirmAll = await askQuestion(
    `Really delete user ${user.email} (${user._id}) and ALL their data? (y/N)`,
  );
  if (confirmAll.toLowerCase() !== 'y') {
    console.yellow('Aborted.');
    silentExit(0);
  }

  const uid = user._id.toString();

  try {
    await Promise.all([
      deleteConvos(uid, []),
      deleteMessages({ user: uid }),
      deletePresets(uid),
      deleteFiles({ user: uid }),
      deleteTokens({ userId: uid }),
      deleteAllUserSessions(uid),
      deleteAllSharedLinks(uid),
      deleteAllUserPluginAuths(uid),
      deleteAllAgentApiKeys(uid),
    ]);

    await deleteUserById(uid);

    console.green(`Successfully deleted user ${email} and all associated data.`);
  } catch (error) {
    console.red('Error deleting user: ' + error.message);
    console.error(error);
    silentExit(1);
  }

  silentExit(0);
})().catch((err) => {
  if (!err.message.includes('fetch failed')) {
    console.error('There was an uncaught error:');
    console.error(err);
    process.exit(1);
  }
});
