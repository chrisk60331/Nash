const { listRolesBB, getRoleByNameBB, initializeRolesBB, updateAccessPermissionsBB } = require('@librechat/api');

module.exports = {
  getRoleByName: getRoleByNameBB,
  updateRoleByName: initializeRolesBB,
  updateAccessPermissions: updateAccessPermissionsBB,
  listRoles: listRolesBB,
  initializeRoles: initializeRolesBB,
};
