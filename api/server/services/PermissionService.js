const isValidId = (id) => typeof id === 'string' && id.length > 0;
const { isEnabled } = require('@librechat/api');
const { logger } = require('@librechat/data-schemas');
const { ResourceType, PrincipalType } = require('librechat-data-provider');
const {
  entraIdPrincipalFeatureEnabled,
  getUserOwnedEntraGroups,
  getUserEntraGroups,
  getGroupMembers,
  getGroupOwners,
} = require('~/server/services/GraphApiService');
const {
  findAccessibleResources: findAccessibleResourcesACL,
  getEffectivePermissions: getEffectivePermissionsACL,
  getEffectivePermissionsForResources: getEffectivePermissionsForResourcesACL,
  grantPermission: grantPermissionACL,
  revokePermission: revokePermissionACL,
  findEntriesByPrincipalsAndResource,
  findEntriesByResource,
  findRolesByResourceType,
  findGroupByExternalId,
  upsertGroupByExternalId,
  syncUserEntraGroups,
  findRoleByIdentifier,
  getUserPrincipals,
  hasPermission,
  createGroup,
  createUser,
  updateUser,
  findUser,
} = require('~/models');

/**
 * Validates that the resourceType is one of the supported enum values
 * @param {string} resourceType - The resource type to validate
 * @throws {Error} If resourceType is not valid
 */
const validateResourceType = (resourceType) => {
  const validTypes = Object.values(ResourceType);
  if (!validTypes.includes(resourceType)) {
    throw new Error(`Invalid resourceType: ${resourceType}. Valid types: ${validTypes.join(', ')}`);
  }
};

/**
 * @import { TPrincipal } from 'librechat-data-provider'
 */
/**
 * Grant a permission to a principal for a resource using a role
 * @param {Object} params - Parameters for granting role-based permission
 * @param {string} params.principalType - PrincipalType.USER, PrincipalType.GROUP, or PrincipalType.PUBLIC
 * @param {string|mongoose.Types.ObjectId|null} params.principalId - The ID of the principal (null for PrincipalType.PUBLIC)
 * @param {string} params.resourceType - Type of resource (e.g., 'agent')
 * @param {string|mongoose.Types.ObjectId} params.resourceId - The ID of the resource
 * @param {string} params.accessRoleId - The ID of the role (e.g., AccessRoleIds.AGENT_VIEWER, AccessRoleIds.AGENT_EDITOR)
 * @param {string|mongoose.Types.ObjectId} params.grantedBy - User ID granting the permission
 * @param {mongoose.ClientSession} [params.session] - Optional MongoDB session for transactions
 * @returns {Promise<Object>} The created or updated ACL entry
 */
const grantPermission = async ({
  principalType,
  principalId,
  resourceType,
  resourceId,
  accessRoleId,
  grantedBy,
  session,
}) => {
  try {
    if (!Object.values(PrincipalType).includes(principalType)) {
      throw new Error(`Invalid principal type: ${principalType}`);
    }

    if (principalType !== PrincipalType.PUBLIC && !principalId) {
      throw new Error('Principal ID is required for user, group, and role principals');
    }

    // Validate principalId based on type
    if (principalId && principalType === PrincipalType.ROLE) {
      // Role IDs are strings (role names)
      if (typeof principalId !== 'string' || principalId.trim().length === 0) {
        throw new Error(`Invalid role ID: ${principalId}`);
      }
    } else if (
      principalType &&
      principalType !== PrincipalType.PUBLIC &&
      !isValidId(principalId)
    ) {
      // User and Group IDs must be valid ObjectIds
      throw new Error(`Invalid principal ID: ${principalId}`);
    }

    if (!resourceId || !isValidId(resourceId)) {
      throw new Error(`Invalid resource ID: ${resourceId}`);
    }

    validateResourceType(resourceType);

    // Get the role to determine permission bits
    const role = await findRoleByIdentifier(accessRoleId);
    if (!role) {
      throw new Error(`Role ${accessRoleId} not found`);
    }

    // Ensure the role is for the correct resource type
    if (role.resourceType !== resourceType) {
      throw new Error(
        `Role ${accessRoleId} is for ${role.resourceType} resources, not ${resourceType}`,
      );
    }
    return await grantPermissionACL(
      principalType,
      principalId,
      resourceType,
      resourceId,
      role.permBits,
      grantedBy,
      session,
      role._id,
    );
  } catch (error) {
    logger.error(`[PermissionService.grantPermission] Error: ${error.message}`);
    throw error;
  }
};

/**
 * Check if a user has specific permission bits on a resource
 * @param {Object} params - Parameters for checking permissions
 * @param {string|mongoose.Types.ObjectId} params.userId - The ID of the user
 * @param {string} [params.role] - Optional user role (if not provided, will query from DB)
 * @param {string} params.resourceType - Type of resource (e.g., 'agent')
 * @param {string|mongoose.Types.ObjectId} params.resourceId - The ID of the resource
 * @param {number} params.requiredPermissions - The permission bits required (e.g., 1 for VIEW, 3 for VIEW+EDIT)
 * @returns {Promise<boolean>} Whether the user has the required permission bits
 */
const checkPermission = async ({ userId, role, resourceType, resourceId, requiredPermission }) => {
  try {
    if (typeof requiredPermission !== 'number' || requiredPermission < 1) {
      throw new Error('requiredPermission must be a positive number');
    }

    validateResourceType(resourceType);

    const principals = await getUserPrincipals({ userId, role });

    if (principals.length === 0) {
      return false;
    }

    return await hasPermission(principals, resourceType, resourceId, requiredPermission);
  } catch (error) {
    logger.error(`[PermissionService.checkPermission] Error: ${error.message}`);
    if (error.message.includes('requiredPermission must be')) {
      throw error;
    }
    return false;
  }
};

/**
 * Get effective permission bitmask for a user on a resource
 * @param {Object} params - Parameters for getting effective permissions
 * @param {string|mongoose.Types.ObjectId} params.userId - The ID of the user
 * @param {string} [params.role] - Optional user role (if not provided, will query from DB)
 * @param {string} params.resourceType - Type of resource (e.g., 'agent')
 * @param {string|mongoose.Types.ObjectId} params.resourceId - The ID of the resource
 * @returns {Promise<number>} Effective permission bitmask
 */
const getEffectivePermissions = async ({ userId, role, resourceType, resourceId }) => {
  try {
    validateResourceType(resourceType);

    const principals = await getUserPrincipals({ userId, role });

    if (principals.length === 0) {
      return 0;
    }

    return await getEffectivePermissionsACL(principals, resourceType, resourceId);
  } catch (error) {
    logger.error(`[PermissionService.getEffectivePermissions] Error: ${error.message}`);
    return 0;
  }
};

/**
 * Get effective permissions for multiple resources in a batch operation
 * Returns map of resourceId → effectivePermissionBits
 *
 * @param {Object} params - Parameters
 * @param {string|mongoose.Types.ObjectId} params.userId - User ID
 * @param {string} [params.role] - User role (for group membership)
 * @param {string} params.resourceType - Resource type (must be valid ResourceType)
 * @param {Array<mongoose.Types.ObjectId>} params.resourceIds - Array of resource IDs
 * @returns {Promise<Map<string, number>>} Map of resourceId string → permission bits
 * @throws {Error} If resourceType is invalid
 */
const getResourcePermissionsMap = async ({ userId, role, resourceType, resourceIds }) => {
  // Validate resource type - throw on invalid type
  validateResourceType(resourceType);

  // Handle empty input
  if (!Array.isArray(resourceIds) || resourceIds.length === 0) {
    return new Map();
  }

  try {
    // Get user principals (user + groups + public)
    const principals = await getUserPrincipals({ userId, role });

    // Use batch method from aclEntry
    const permissionsMap = await getEffectivePermissionsForResourcesACL(
      principals,
      resourceType,
      resourceIds,
    );

    logger.debug(
      `[PermissionService.getResourcePermissionsMap] Computed permissions for ${resourceIds.length} resources, ${permissionsMap.size} have permissions`,
    );

    return permissionsMap;
  } catch (error) {
    logger.error(`[PermissionService.getResourcePermissionsMap] Error: ${error.message}`, error);
    throw error;
  }
};

/**
 * Find all resources of a specific type that a user has access to with specific permission bits
 * @param {Object} params - Parameters for finding accessible resources
 * @param {string|mongoose.Types.ObjectId} params.userId - The ID of the user
 * @param {string} [params.role] - Optional user role (if not provided, will query from DB)
 * @param {string} params.resourceType - Type of resource (e.g., 'agent')
 * @param {number} params.requiredPermissions - The minimum permission bits required (e.g., 1 for VIEW, 3 for VIEW+EDIT)
 * @returns {Promise<Array>} Array of resource IDs
 */
const findAccessibleResources = async ({ userId, role, resourceType, requiredPermissions }) => {
  try {
    if (typeof requiredPermissions !== 'number' || requiredPermissions < 1) {
      throw new Error('requiredPermissions must be a positive number');
    }

    validateResourceType(resourceType);

    // Get all principals for the user (user + groups + public)
    const principalsList = await getUserPrincipals({ userId, role });

    if (principalsList.length === 0) {
      return [];
    }
    return await findAccessibleResourcesACL(principalsList, resourceType, requiredPermissions);
  } catch (error) {
    logger.error(`[PermissionService.findAccessibleResources] Error: ${error.message}`);
    // Re-throw validation errors
    if (error.message.includes('requiredPermissions must be')) {
      throw error;
    }
    return [];
  }
};

/**
 * Find all publicly accessible resources of a specific type
 * @param {Object} params - Parameters for finding publicly accessible resources
 * @param {string} params.resourceType - Type of resource (e.g., 'agent')
 * @param {number} params.requiredPermissions - The minimum permission bits required (e.g., 1 for VIEW, 3 for VIEW+EDIT)
 * @returns {Promise<Array>} Array of resource IDs
 */
const findPubliclyAccessibleResources = async ({ resourceType, requiredPermissions }) => {
  try {
    if (typeof requiredPermissions !== 'number' || requiredPermissions < 1) {
      throw new Error('requiredPermissions must be a positive number');
    }

    validateResourceType(resourceType);

    const publicPrincipals = [{ principalType: PrincipalType.PUBLIC }];
    return await findAccessibleResourcesACL(publicPrincipals, resourceType, requiredPermissions);
  } catch (error) {
    logger.error(`[PermissionService.findPubliclyAccessibleResources] Error: ${error.message}`);
    if (error.message.includes('requiredPermissions must be')) {
      throw error;
    }
    return [];
  }
};

/**
 * Get available roles for a resource type
 * @param {Object} params - Parameters for getting available roles
 * @param {string} params.resourceType - Type of resource (e.g., 'agent')
 * @returns {Promise<Array>} Array of role definitions
 */
const getAvailableRoles = async ({ resourceType }) => {
  validateResourceType(resourceType);

  return await findRolesByResourceType(resourceType);
};

/**
 * Ensures a principal exists in the database based on TPrincipal data
 * Creates user if it doesn't exist locally (for Entra ID users)
 * @param {Object} principal - TPrincipal object from frontend
 * @param {string} principal.type - PrincipalType.USER, PrincipalType.GROUP, or PrincipalType.PUBLIC
 * @param {string} [principal.id] - Local database ID (null for Entra ID principals not yet synced)
 * @param {string} principal.name - Display name
 * @param {string} [principal.email] - Email address
 * @param {string} [principal.source] - 'local' or 'entra'
 * @param {string} [principal.idOnTheSource] - Entra ID object ID for external principals
 * @returns {Promise<string|null>} Returns the principalId for database operations, null for public
 */
const ensurePrincipalExists = async function (principal) {
  if (principal.type === PrincipalType.PUBLIC) {
    return null;
  }

  if (principal.id) {
    return principal.id;
  }

  if (principal.type === PrincipalType.USER && principal.source === 'entra') {
    if (!principal.email || !principal.idOnTheSource) {
      throw new Error('Entra ID user principals must have email and idOnTheSource');
    }

    let existingUser = await findUser({ idOnTheSource: principal.idOnTheSource });

    if (!existingUser) {
      existingUser = await findUser({ email: principal.email });
    }

    if (existingUser) {
      if (!existingUser.idOnTheSource && principal.idOnTheSource) {
        await updateUser(existingUser._id, {
          idOnTheSource: principal.idOnTheSource,
          provider: 'openid',
        });
      }
      return existingUser._id.toString();
    }

    const userData = {
      name: principal.name,
      email: principal.email.toLowerCase(),
      emailVerified: false,
      provider: 'openid',
      idOnTheSource: principal.idOnTheSource,
    };

    const userId = await createUser(userData, true, true);
    return userId.toString();
  }

  if (principal.type === PrincipalType.GROUP) {
    throw new Error('Group principals should be handled by group-specific methods');
  }

  throw new Error(`Unsupported principal type: ${principal.type}`);
};

/**
 * Ensures a group principal exists in the database based on TPrincipal data
 * Creates group if it doesn't exist locally (for Entra ID groups)
 * For Entra ID groups, always synchronizes member IDs when authentication context is provided
 * @param {Object} principal - TPrincipal object from frontend
 * @param {string} principal.type - Must be PrincipalType.GROUP
 * @param {string} [principal.id] - Local database ID (null for Entra ID principals not yet synced)
 * @param {string} principal.name - Display name
 * @param {string} [principal.email] - Email address
 * @param {string} [principal.description] - Group description
 * @param {string} [principal.source] - 'local' or 'entra'
 * @param {string} [principal.idOnTheSource] - Entra ID object ID for external principals
 * @param {Object} [authContext] - Optional authentication context for fetching member data
 * @param {string} [authContext.accessToken] - Access token for Graph API calls
 * @param {string} [authContext.sub] - Subject identifier
 * @returns {Promise<string>} Returns the groupId for database operations
 */
const ensureGroupPrincipalExists = async function (principal, authContext = null) {
  if (principal.type !== PrincipalType.GROUP) {
    throw new Error(`Invalid principal type: ${principal.type}. Expected '${PrincipalType.GROUP}'`);
  }

  if (principal.source === 'entra') {
    if (!principal.name || !principal.idOnTheSource) {
      throw new Error('Entra ID group principals must have name and idOnTheSource');
    }

    let memberIds = [];
    if (authContext && authContext.accessToken && authContext.sub) {
      try {
        memberIds = await getGroupMembers(
          authContext.accessToken,
          authContext.sub,
          principal.idOnTheSource,
        );

        // Include group owners as members if feature is enabled
        if (isEnabled(process.env.ENTRA_ID_INCLUDE_OWNERS_AS_MEMBERS)) {
          const ownerIds = await getGroupOwners(
            authContext.accessToken,
            authContext.sub,
            principal.idOnTheSource,
          );
          if (ownerIds && ownerIds.length > 0) {
            memberIds.push(...ownerIds);
            // Remove duplicates
            memberIds = [...new Set(memberIds)];
          }
        }
      } catch (error) {
        logger.error('Failed to fetch group members from Graph API:', error);
      }
    }

    const existingGroup = await findGroupByExternalId(principal.idOnTheSource, 'entra');

    if (existingGroup) {
      const groupId = (existingGroup._id ?? existingGroup.id).toString();

      if (authContext && authContext.accessToken && authContext.sub) {
        const updateData = {
          name: principal.name,
          source: 'entra',
          idOnTheSource: principal.idOnTheSource,
          memberIds,
        };
        if (principal.email) {
          updateData.email = principal.email.toLowerCase();
        }
        if (principal.description) {
          updateData.description = principal.description;
        }
        await upsertGroupByExternalId(principal.idOnTheSource, 'entra', updateData);
      }

      return groupId;
    }

    const groupData = {
      name: principal.name,
      source: 'entra',
      idOnTheSource: principal.idOnTheSource,
      memberIds,
    };

    if (principal.email) {
      groupData.email = principal.email.toLowerCase();
    }

    if (principal.description) {
      groupData.description = principal.description;
    }

    const newGroup = await createGroup(groupData);
    return (newGroup._id ?? newGroup.id).toString();
  }
  if (principal.id && authContext == null) {
    return principal.id;
  }

  throw new Error(`Unsupported group principal source: ${principal.source}`);
};

/**
 * Synchronize user's Entra ID group memberships on sign-in
 * Gets user's group IDs from GraphAPI and updates memberships only for existing groups in database
 * Optionally includes groups the user owns if ENTRA_ID_INCLUDE_OWNERS_AS_MEMBERS is enabled
 * @param {Object} user - User object with authentication context
 * @param {string} user.openidId - User's OpenID subject identifier
 * @param {string} user.idOnTheSource - User's Entra ID (oid from token claims)
 * @param {string} user.provider - Authentication provider ('openid')
 * @param {string} accessToken - Access token for Graph API calls
 * @param {mongoose.ClientSession} [session] - Optional MongoDB session for transactions
 * @returns {Promise<void>}
 */
const syncUserEntraGroupMemberships = async (user, accessToken, _session = null) => {
  try {
    if (!entraIdPrincipalFeatureEnabled(user) || !accessToken || !user.idOnTheSource) {
      return;
    }

    const memberGroupIds = await getUserEntraGroups(accessToken, user.openidId);
    let allGroupIds = [...(memberGroupIds || [])];

    if (isEnabled(process.env.ENTRA_ID_INCLUDE_OWNERS_AS_MEMBERS)) {
      const ownedGroupIds = await getUserOwnedEntraGroups(accessToken, user.openidId);
      if (ownedGroupIds && ownedGroupIds.length > 0) {
        allGroupIds.push(...ownedGroupIds);
        allGroupIds = [...new Set(allGroupIds)];
      }
    }

    if (!allGroupIds || allGroupIds.length === 0) {
      return;
    }

    await syncUserEntraGroups(user.idOnTheSource, allGroupIds);
  } catch (error) {
    logger.error(`[PermissionService.syncUserEntraGroupMemberships] Error syncing groups:`, error);
  }
};

/**
 * Check if public has a specific permission on a resource
 * @param {Object} params - Parameters for checking public permission
 * @param {string} params.resourceType - Type of resource (e.g., 'agent')
 * @param {string|mongoose.Types.ObjectId} params.resourceId - The ID of the resource
 * @param {number} params.requiredPermissions - The permission bits required (e.g., 1 for VIEW, 3 for VIEW+EDIT)
 * @returns {Promise<boolean>} Whether public has the required permission bits
 */
const hasPublicPermission = async ({ resourceType, resourceId, requiredPermissions }) => {
  try {
    if (typeof requiredPermissions !== 'number' || requiredPermissions < 1) {
      throw new Error('requiredPermissions must be a positive number');
    }

    validateResourceType(resourceType);

    // Use public principal to check permissions
    const publicPrincipal = [{ principalType: PrincipalType.PUBLIC }];

    const entries = await findEntriesByPrincipalsAndResource(
      publicPrincipal,
      resourceType,
      resourceId,
    );

    // Check if any entry has the required permission bits
    return entries.some((entry) => (entry.permBits & requiredPermissions) === requiredPermissions);
  } catch (error) {
    logger.error(`[PermissionService.hasPublicPermission] Error: ${error.message}`);
    // Re-throw validation errors
    if (error.message.includes('requiredPermissions must be')) {
      throw error;
    }
    return false;
  }
};

/**
 * Bulk update permissions for a resource (grant, update, revoke)
 * Efficiently handles multiple permission changes in a single transaction
 *
 * @param {Object} params - Parameters for bulk permission update
 * @param {string} params.resourceType - Type of resource (e.g., 'agent')
 * @param {string|mongoose.Types.ObjectId} params.resourceId - The ID of the resource
 * @param {Array<TPrincipal>} params.updatedPrincipals - Array of principals to grant/update permissions for
 * @param {Array<TPrincipal>} params.revokedPrincipals - Array of principals to revoke permissions from
 * @param {string|mongoose.Types.ObjectId} params.grantedBy - User ID making the changes
 * @param {mongoose.ClientSession} [params.session] - Optional MongoDB session for transactions
 * @returns {Promise<Object>} Results object with granted, updated, revoked arrays and error details
 */
const bulkUpdateResourcePermissions = async ({
  resourceType,
  resourceId,
  updatedPrincipals = [],
  revokedPrincipals = [],
  grantedBy,
}) => {
  try {
    if (!Array.isArray(updatedPrincipals)) {
      throw new Error('updatedPrincipals must be an array');
    }

    if (!Array.isArray(revokedPrincipals)) {
      throw new Error('revokedPrincipals must be an array');
    }

    if (!resourceId || !isValidId(resourceId)) {
      throw new Error(`Invalid resource ID: ${resourceId}`);
    }

    const roles = await findRolesByResourceType(resourceType);
    const rolesMap = new Map();
    for (const role of roles) {
      rolesMap.set(role.accessRoleId, role);
    }

    const results = {
      granted: [],
      updated: [],
      revoked: [],
      errors: [],
    };

    for (const principal of updatedPrincipals) {
      try {
        if (!principal.accessRoleId) {
          results.errors.push({
            principal,
            error: 'accessRoleId is required for updated principals',
          });
          continue;
        }

        const role = rolesMap.get(principal.accessRoleId);
        if (!role) {
          results.errors.push({
            principal,
            error: `Role ${principal.accessRoleId} not found`,
          });
          continue;
        }

        const principalId =
          principal.type === PrincipalType.PUBLIC
            ? null
            : principal.type === PrincipalType.ROLE
              ? principal.id
              : principal.id;

        await grantPermissionACL(
          principal.type,
          principalId,
          resourceType,
          resourceId,
          role.permBits,
          grantedBy,
          null,
          role._id ?? role.id,
        );

        results.granted.push({
          type: principal.type,
          id: principal.id,
          name: principal.name,
          email: principal.email,
          source: principal.source,
          avatar: principal.avatar,
          description: principal.description,
          idOnTheSource: principal.idOnTheSource,
          accessRoleId: principal.accessRoleId,
          memberCount: principal.memberCount,
          memberIds: principal.memberIds,
        });
      } catch (error) {
        results.errors.push({
          principal,
          error: error.message,
        });
      }
    }

    for (const principal of revokedPrincipals) {
      try {
        const principalId =
          principal.type === PrincipalType.PUBLIC
            ? null
            : principal.type === PrincipalType.ROLE
              ? principal.id
              : principal.id;

        await revokePermissionACL(principal.type, principalId, resourceType, resourceId);

        results.revoked.push({
          type: principal.type,
          id: principal.id,
          name: principal.name,
          email: principal.email,
          source: principal.source,
          avatar: principal.avatar,
          description: principal.description,
          idOnTheSource: principal.idOnTheSource,
          memberCount: principal.memberCount,
        });
      } catch (error) {
        results.errors.push({
          principal,
          error: error.message,
        });
      }
    }

    return results;
  } catch (error) {
    logger.error(`[PermissionService.bulkUpdateResourcePermissions] Error: ${error.message}`);
    throw error;
  }
};

/**
 * Remove all permissions for a resource (cleanup when resource is deleted)
 * @param {Object} params - Parameters for removing all permissions
 * @param {string} params.resourceType - Type of resource (e.g., 'agent', 'prompt')
 * @param {string|mongoose.Types.ObjectId} params.resourceId - The ID of the resource
 * @returns {Promise<Object>} Result of the deletion operation
 */
const removeAllPermissions = async ({ resourceType, resourceId }) => {
  try {
    validateResourceType(resourceType);

    if (!resourceId || !isValidId(resourceId)) {
      throw new Error(`Invalid resource ID: ${resourceId}`);
    }

    const entries = await findEntriesByResource(resourceType, resourceId);
    let deletedCount = 0;
    for (const entry of entries) {
      await revokePermissionACL(entry.principalType, entry.principalId, resourceType, resourceId);
      deletedCount++;
    }

    return { deletedCount };
  } catch (error) {
    logger.error(`[PermissionService.removeAllPermissions] Error: ${error.message}`);
    throw error;
  }
};

module.exports = {
  grantPermission,
  checkPermission,
  getEffectivePermissions,
  getResourcePermissionsMap,
  findAccessibleResources,
  findPubliclyAccessibleResources,
  hasPublicPermission,
  getAvailableRoles,
  bulkUpdateResourcePermissions,
  ensurePrincipalExists,
  ensureGroupPrincipalExists,
  syncUserEntraGroupMemberships,
  removeAllPermissions,
};
