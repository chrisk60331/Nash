const { logger } = require('@librechat/data-schemas');

async function checkMigrations() {
  logger.debug('[checkMigrations] Skipped — BB adapter does not require MongoDB migrations');
}

module.exports = {
  checkMigrations,
};
