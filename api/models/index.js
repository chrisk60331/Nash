const {
  // Auth
  findUserBB,
  getUserByIdBB,
  createUserBB,
  updateUserBB,
  deleteUserByIdBB,
  countUsersBB,
  searchUsersBB,
  generateTokenBB,
  updateUserPluginsBB,
  toggleUserMemoriesBB,
  verifyPassword,
  // Sessions
  createSessionBB,
  findSessionBB,
  deleteSessionBB,
  deleteAllUserSessionsBB,
  updateExpirationBB,
  countActiveSessionsBB,
  generateRefreshTokenBB,
  // Tokens
  createTokenBB,
  findTokenBB,
  updateTokenBB,
  deleteTokensBB,
  // Shared Links
  getSharedMessagesBB,
  getSharedLinksBB,
  createSharedLinkBB,
  getSharedLinkBB,
  updateSharedLinkBB,
  deleteSharedLinkBB,
  deleteAllSharedLinksBB,
  deleteConvoSharedLinkBB,
  // Files
  findFileByIdBB,
  getFilesBB,
  getToolFilesByIdsBB,
  getCodeGeneratedFilesBB,
  getUserCodeFilesBB,
  createFileBB,
  updateFileBB,
  updateFileUsageBB,
  updateFilesUsageBB,
  deleteFileBB,
  deleteFilesBB,
  deleteFileByFilterBB,
  batchUpdateFilesBB,
  // Keys
  getUserKeyBB,
  updateUserKeyBB,
  deleteUserKeyBB,
  getUserKeyValuesBB,
  getUserKeyExpiryBB,
  // PluginAuth
  findOnePluginAuthBB,
  findPluginAuthsByKeysBB,
  updatePluginAuthBB,
  deletePluginAuthBB,
  deleteAllUserPluginAuthsBB,
  // Memories
  getAllUserMemoriesBB,
  createMemoryBB,
  setMemoryBB,
  deleteMemoryBB,
  getFormattedMemoriesBB,
  // Agent Categories
  getActiveCategoriesBB,
  getCategoriesWithCountsBB,
  getValidCategoryValuesBB,
  seedCategoriesBB,
  findCategoryByValueBB,
  createCategoryBB,
  updateCategoryBB,
  deleteCategoryBB,
  findCategoryByIdBB,
  getAllCategoriesBB,
  ensureDefaultCategoriesBB,
  // Agent API Keys
  createAgentApiKeyBB,
  validateAgentApiKeyBB,
  listAgentApiKeysBB,
  deleteAgentApiKeyBB,
  deleteAllAgentApiKeysBB,
  getAgentApiKeyByIdBB,
  // MCP
  createMCPServerBB,
  findMCPServerByServerNameBB,
  findMCPServerByObjectIdBB,
  findMCPServersByAuthorBB,
  getListMCPServersByIdsBB,
  getListMCPServersByNamesBB,
  updateMCPServerBB,
  deleteMCPServerBB,
  // RBAC
  listRolesBB,
  initializeRolesBB,
  createAccessRoleBB,
  updateAccessRoleBB,
  deleteAccessRoleBB,
  getAllAccessRolesBB,
  findAccessRoleByIdBB,
  seedDefaultRolesBB,
  findAccessRoleByIdentifierBB,
  getRoleForPermissionsBB,
  findAccessRoleByPermissionsBB,
  findAccessRolesByResourceTypeBB,
  findEntriesByPrincipalBB,
  findEntriesByResourceBB,
  findEntriesByPrincipalsAndResourceBB,
  hasPermissionBB,
  getEffectivePermissionsBB,
  getEffectivePermissionsForResourcesBB,
  grantPermissionBB,
  revokePermissionBB,
  modifyPermissionBitsBB,
  findAccessibleResourcesBB,
  findGroupByIdBB,
  findGroupByExternalIdBB,
  findGroupsByNamePatternBB,
  findGroupsByMemberIdBB,
  createGroupBB,
  upsertGroupByExternalIdBB,
  addUserToGroupBB,
  removeUserFromGroupBB,
  getUserGroupsBB,
  getUserPrincipalsBB,
  syncUserEntraGroupsBB,
  searchPrincipalsBB,
} = require('@librechat/api');

const {
  getMessage,
  getMessages,
  saveMessage,
  recordMessage,
  updateMessage,
  deleteMessagesSince,
  deleteMessages,
} = require('./Message');
const { getConvoTitle, getConvo, saveConvo, deleteConvos } = require('./Conversation');
const { getPreset, getPresets, savePreset, deletePresets } = require('./Preset');

const seedDatabase = async () => {
  await initializeRolesBB();
  await seedDefaultRolesBB();
  await ensureDefaultCategoriesBB();
};

const comparePassword = async (user, password) => {
  return verifyPassword(password, user.password);
};

module.exports = {
  seedDatabase,
  comparePassword,

  // User methods (mapped to original names)
  findUser: findUserBB,
  getUserById: getUserByIdBB,
  createUser: createUserBB,
  updateUser: updateUserBB,
  deleteUserById: deleteUserByIdBB,
  countUsers: countUsersBB,
  searchUsers: searchUsersBB,
  generateToken: generateTokenBB,
  updateUserPlugins: updateUserPluginsBB,
  toggleUserMemories: toggleUserMemoriesBB,

  // Session methods
  createSession: createSessionBB,
  findSession: findSessionBB,
  deleteSession: deleteSessionBB,
  deleteAllUserSessions: deleteAllUserSessionsBB,
  updateExpiration: updateExpirationBB,
  countActiveSessions: countActiveSessionsBB,
  generateRefreshToken: generateRefreshTokenBB,

  // Token methods
  createToken: createTokenBB,
  findToken: findTokenBB,
  updateToken: updateTokenBB,
  deleteTokens: deleteTokensBB,

  // Share methods
  getSharedMessages: getSharedMessagesBB,
  getSharedLinks: getSharedLinksBB,
  createSharedLink: createSharedLinkBB,
  getSharedLink: getSharedLinkBB,
  updateSharedLink: updateSharedLinkBB,
  deleteSharedLink: deleteSharedLinkBB,
  deleteAllSharedLinks: deleteAllSharedLinksBB,
  deleteConvoSharedLink: deleteConvoSharedLinkBB,

  // File methods
  findFileById: findFileByIdBB,
  getFiles: getFilesBB,
  getToolFilesByIds: getToolFilesByIdsBB,
  getCodeGeneratedFiles: getCodeGeneratedFilesBB,
  getUserCodeFiles: getUserCodeFilesBB,
  createFile: createFileBB,
  updateFile: updateFileBB,
  updateFileUsage: updateFileUsageBB,
  updateFilesUsage: updateFilesUsageBB,
  deleteFile: deleteFileBB,
  deleteFiles: deleteFilesBB,
  deleteFileByFilter: deleteFileByFilterBB,
  batchUpdateFiles: batchUpdateFilesBB,

  // Key methods
  getUserKey: getUserKeyBB,
  updateUserKey: updateUserKeyBB,
  deleteUserKey: deleteUserKeyBB,
  getUserKeyValues: getUserKeyValuesBB,
  getUserKeyExpiry: getUserKeyExpiryBB,

  // PluginAuth methods
  findOnePluginAuth: findOnePluginAuthBB,
  findPluginAuthsByKeys: findPluginAuthsByKeysBB,
  updatePluginAuth: updatePluginAuthBB,
  deletePluginAuth: deletePluginAuthBB,
  deleteAllUserPluginAuths: deleteAllUserPluginAuthsBB,

  // Memory methods
  getAllUserMemories: getAllUserMemoriesBB,
  createMemory: createMemoryBB,
  setMemory: setMemoryBB,
  deleteMemory: deleteMemoryBB,
  getFormattedMemories: async ({ userId }) =>
    getFormattedMemoriesBB(typeof userId === 'string' ? userId : userId.toString()),

  // Agent Category methods
  getActiveCategories: getActiveCategoriesBB,
  getCategoriesWithCounts: getCategoriesWithCountsBB,
  getValidCategoryValues: getValidCategoryValuesBB,
  seedCategories: seedCategoriesBB,
  findCategoryByValue: findCategoryByValueBB,
  createCategory: createCategoryBB,
  updateCategory: updateCategoryBB,
  deleteCategory: deleteCategoryBB,
  findCategoryById: findCategoryByIdBB,
  getAllCategories: getAllCategoriesBB,
  ensureDefaultCategories: ensureDefaultCategoriesBB,

  // Agent API Key methods
  createAgentApiKey: createAgentApiKeyBB,
  validateAgentApiKey: validateAgentApiKeyBB,
  listAgentApiKeys: listAgentApiKeysBB,
  deleteAgentApiKey: deleteAgentApiKeyBB,
  deleteAllAgentApiKeys: deleteAllAgentApiKeysBB,
  getAgentApiKeyById: getAgentApiKeyByIdBB,

  // MCP methods
  createMCPServer: createMCPServerBB,
  findMCPServerByServerName: findMCPServerByServerNameBB,
  findMCPServerByObjectId: findMCPServerByObjectIdBB,
  findMCPServersByAuthor: findMCPServersByAuthorBB,
  getListMCPServersByIds: getListMCPServersByIdsBB,
  getListMCPServersByNames: getListMCPServersByNamesBB,
  updateMCPServer: updateMCPServerBB,
  deleteMCPServer: deleteMCPServerBB,

  // Role methods
  listRoles: listRolesBB,
  initializeRoles: initializeRolesBB,

  // AccessRole methods
  createRole: createAccessRoleBB,
  updateRole: updateAccessRoleBB,
  deleteRole: deleteAccessRoleBB,
  getAllRoles: getAllAccessRolesBB,
  findRoleById: findAccessRoleByIdBB,
  seedDefaultRoles: seedDefaultRolesBB,
  findRoleByIdentifier: findAccessRoleByIdentifierBB,
  getRoleForPermissions: getRoleForPermissionsBB,
  findRoleByPermissions: findAccessRoleByPermissionsBB,
  findRolesByResourceType: findAccessRolesByResourceTypeBB,

  // AclEntry methods
  findEntriesByPrincipal: findEntriesByPrincipalBB,
  findEntriesByResource: findEntriesByResourceBB,
  findEntriesByPrincipalsAndResource: findEntriesByPrincipalsAndResourceBB,
  hasPermission: hasPermissionBB,
  getEffectivePermissions: getEffectivePermissionsBB,
  getEffectivePermissionsForResources: getEffectivePermissionsForResourcesBB,
  grantPermission: grantPermissionBB,
  revokePermission: revokePermissionBB,
  modifyPermissionBits: modifyPermissionBitsBB,
  findAccessibleResources: findAccessibleResourcesBB,

  // Group methods
  findGroupById: findGroupByIdBB,
  findGroupByExternalId: findGroupByExternalIdBB,
  findGroupsByNamePattern: findGroupsByNamePatternBB,
  findGroupsByMemberId: findGroupsByMemberIdBB,
  createGroup: createGroupBB,
  upsertGroupByExternalId: upsertGroupByExternalIdBB,
  addUserToGroup: addUserToGroupBB,
  removeUserFromGroup: removeUserFromGroupBB,
  getUserGroups: getUserGroupsBB,
  getUserPrincipals: getUserPrincipalsBB,
  syncUserEntraGroups: syncUserEntraGroupsBB,
  searchPrincipals: searchPrincipalsBB,

  // Conversation methods (from ./Conversation.js which already uses BB)
  getConvoTitle,
  getConvo,
  saveConvo,
  deleteConvos,

  // Message methods (from ./Message.js which already uses BB)
  getMessage,
  getMessages,
  saveMessage,
  recordMessage,
  updateMessage,
  deleteMessagesSince,
  deleteMessages,

  // Preset methods (from ./Preset.js which already uses BB)
  getPreset,
  getPresets,
  savePreset,
  deletePresets,

  // Files placeholder (used by some imports as `Files` model ref)
  Files: null,

  // Balance stub (BB does not manage balances locally)
  Balance: null,
  getBalance: async () => null,
};
