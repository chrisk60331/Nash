const path = require('path');
require('module-alias/register');
const moduleAlias = require('module-alias');

const basePath = path.resolve(__dirname, '..', 'api');
moduleAlias.addAlias('~', basePath);

require('./helpers');

async function connect() {
  console.orange('Using Backboard for storage (no MongoDB connection needed)');
}

module.exports = connect;
