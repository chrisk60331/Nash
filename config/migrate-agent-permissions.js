const path = require('path');
require('module-alias')({ base: path.resolve(__dirname, '..', 'api') });

async function migrateAgentPermissionsEnhanced() {
  console.log('Migration not needed (Backboard storage).');
  console.log('Agent permissions are managed by Backboard.');
  return { migrated: 0, errors: 0, skipped: true };
}

if (require.main === module) {
  migrateAgentPermissionsEnhanced()
    .then(() => process.exit(0))
    .catch((error) => {
      console.error('Error:', error);
      process.exit(1);
    });
}

module.exports = { migrateAgentPermissionsEnhanced };
