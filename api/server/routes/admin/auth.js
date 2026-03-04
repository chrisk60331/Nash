const express = require('express');
const passport = require('passport');
const { randomState } = require('openid-client');
const { logger } = require('@librechat/data-schemas');
const { CacheKeys } = require('librechat-data-provider');
const {
  requireAdmin,
  getAdminPanelUrl,
  exchangeAdminCode,
  createSetBalanceConfig,
} = require('@librechat/api');
const { loginController } = require('~/server/controllers/auth/LoginController');
const { createOAuthHandler } = require('~/server/controllers/auth/oauth');
const { getAppConfig } = require('~/server/services/Config');
const getLogStores = require('~/cache/getLogStores');
const { getOpenIdConfig } = require('~/strategies');
const middleware = require('~/server/middleware');
const { Balance } = require('~/models');

const setBalanceConfig = createSetBalanceConfig({
  getAppConfig,
  Balance,
});

const router = express.Router();

router.post(
  '/login/local',
  middleware.logHeaders,
  middleware.loginLimiter,
  middleware.checkBan,
  middleware.requireLocalAuth,
  requireAdmin,
  setBalanceConfig,
  loginController,
);

router.get('/verify', middleware.requireJwtAuth, requireAdmin, (req, res) => {
  const { password: _p, totpSecret: _t, __v, ...user } = req.user;
  user.id = user._id.toString();
  res.status(200).json({ user });
});

router.get('/oauth/openid/check', (req, res) => {
  const openidConfig = getOpenIdConfig();
  if (!openidConfig) {
    return res.status(404).json({
      error: 'OpenID configuration not found',
      error_code: 'OPENID_NOT_CONFIGURED',
    });
  }
  res.status(200).json({ message: 'OpenID check successful' });
});

router.get('/oauth/openid', (req, res, next) => {
  return passport.authenticate('openidAdmin', {
    session: false,
    state: randomState(),
  })(req, res, next);
});

router.get(
  '/oauth/openid/callback',
  passport.authenticate('openidAdmin', {
    failureRedirect: `${getAdminPanelUrl()}/auth/openid/callback?error=auth_failed&error_description=Authentication+failed`,
    failureMessage: true,
    session: false,
  }),
  requireAdmin,
  setBalanceConfig,
  middleware.checkDomainAllowed,
  createOAuthHandler(`${getAdminPanelUrl()}/auth/openid/callback`),
);

/** Regex pattern for valid exchange codes: 64 hex characters */
const EXCHANGE_CODE_PATTERN = /^[a-f0-9]{64}$/i;

/**
 * Exchange OAuth authorization code for tokens.
 * This endpoint is called server-to-server by the admin panel.
 * The code is one-time-use and expires in 30 seconds.
 *
 * POST /api/admin/oauth/exchange
 * Body: { code: string }
 * Response: { token: string, refreshToken: string, user: object }
 */
router.post('/oauth/exchange', middleware.loginLimiter, async (req, res) => {
  try {
    const { code } = req.body;

    if (!code) {
      logger.warn('[admin/oauth/exchange] Missing authorization code');
      return res.status(400).json({
        error: 'Missing authorization code',
        error_code: 'MISSING_CODE',
      });
    }

    if (typeof code !== 'string' || !EXCHANGE_CODE_PATTERN.test(code)) {
      logger.warn('[admin/oauth/exchange] Invalid authorization code format');
      return res.status(400).json({
        error: 'Invalid authorization code format',
        error_code: 'INVALID_CODE_FORMAT',
      });
    }

    const cache = getLogStores(CacheKeys.ADMIN_OAUTH_EXCHANGE);
    const result = await exchangeAdminCode(cache, code);

    if (!result) {
      return res.status(401).json({
        error: 'Invalid or expired authorization code',
        error_code: 'INVALID_OR_EXPIRED_CODE',
      });
    }

    res.json(result);
  } catch (error) {
    logger.error('[admin/oauth/exchange] Error:', error);
    res.status(500).json({
      error: 'Internal server error',
      error_code: 'INTERNAL_ERROR',
    });
  }
});

/**
 * Reset a user's password by email. Protected by ADMIN_RESET_SECRET header.
 * POST /api/admin/reset-password
 * Headers: x-admin-secret: <ADMIN_RESET_SECRET>
 * Body: { email: string, password: string }
 */
router.post('/reset-password', async (req, res) => {
  const secret = process.env.ADMIN_RESET_SECRET;
  if (!secret || req.headers['x-admin-secret'] !== secret) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const { email, password } = req.body;
  if (!email || !password) {
    return res.status(400).json({ error: 'email and password are required' });
  }

  if (password.length < 8) {
    return res.status(400).json({ error: 'password must be at least 8 characters' });
  }

  try {
    const { findUser, updateUser } = require('~/models');
    const user = await findUser({ email: email.trim().toLowerCase() });
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }

    await updateUser(user._id || user.id, { password });
    logger.info(`[admin/reset-password] Password reset for ${email}`);
    res.json({ success: true, email });
  } catch (error) {
    logger.error('[admin/reset-password] Error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * Provision a new user. Protected by ADMIN_RESET_SECRET header.
 * POST /api/admin/provision-user
 * Headers: x-admin-secret: <ADMIN_RESET_SECRET>
 * Body: { email: string, password: string, name?: string, username?: string, role?: string }
 */
router.post('/provision-user', async (req, res) => {
  const secret = process.env.ADMIN_RESET_SECRET;
  if (!secret || req.headers['x-admin-secret'] !== secret) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const { email, password, name, username, role } = req.body;
  if (!email || !password) {
    return res.status(400).json({ error: 'email and password are required' });
  }

  if (password.length < 8) {
    return res.status(400).json({ error: 'password must be at least 8 characters' });
  }

  try {
    const { findUser, createUser } = require('~/models');
    const existing = await findUser({ email: email.trim().toLowerCase() });
    if (existing) {
      return res.status(409).json({ error: 'User already exists' });
    }

    const userId = await createUser({
      email: email.trim().toLowerCase(),
      password,
      name: name || email.split('@')[0],
      username: username || email.split('@')[0],
      role: role === 'ADMIN' ? 'ADMIN' : 'USER',
      emailVerified: true,
      provider: 'local',
    });

    logger.info(`[admin/provision-user] Created user ${userId} (${email})`);
    res.status(201).json({ success: true, userId, email });
  } catch (error) {
    logger.error('[admin/provision-user] Error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * Delete a user by email. Protected by ADMIN_RESET_SECRET header.
 * DELETE /api/admin/delete-user
 * Headers: x-admin-secret: <ADMIN_RESET_SECRET>
 * Body: { email: string }
 */
router.delete('/delete-user', async (req, res) => {
  const secret = process.env.ADMIN_RESET_SECRET;
  if (!secret || req.headers['x-admin-secret'] !== secret) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const { email } = req.body;
  if (!email) {
    return res.status(400).json({ error: 'email is required' });
  }

  try {
    const { findUser, deleteUserById } = require('~/models');
    const user = await findUser({ email: email.trim().toLowerCase() });
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }

    const userId = user._id || user.id;
    await deleteUserById(userId);
    logger.info(`[admin/delete-user] Deleted user ${userId} (${email})`);
    res.json({ success: true, email });
  } catch (error) {
    logger.error('[admin/delete-user] Error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * Promote or demote a user by email. Protected by ADMIN_RESET_SECRET header.
 * POST /api/admin/set-role
 * Headers: x-admin-secret: <ADMIN_RESET_SECRET>
 * Body: { email: string, role: "ADMIN" | "USER" }
 */
router.post('/set-role', async (req, res) => {
  const secret = process.env.ADMIN_RESET_SECRET;
  if (!secret || req.headers['x-admin-secret'] !== secret) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const { email, role } = req.body;
  if (!email || !role) {
    return res.status(400).json({ error: 'email and role are required' });
  }

  const validRoles = ['ADMIN', 'USER'];
  if (!validRoles.includes(role)) {
    return res.status(400).json({ error: `role must be one of: ${validRoles.join(', ')}` });
  }

  try {
    const { findUser, updateUser } = require('~/models');
    const user = await findUser({ email: email.trim().toLowerCase() });
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }

    await updateUser(user._id || user.id, { role });
    logger.info(`[admin/set-role] Set role for ${email} to ${role}`);
    res.json({ success: true, email, role });
  } catch (error) {
    logger.error('[admin/set-role] Error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * Invalidate the in-memory auth cache so it reloads from Backboard.
 * POST /api/admin/reload-auth
 * Headers: x-admin-secret: <ADMIN_RESET_SECRET>
 */
router.post('/reload-auth', async (req, res) => {
  const secret = process.env.ADMIN_RESET_SECRET;
  if (!secret || req.headers['x-admin-secret'] !== secret) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  try {
    const { invalidateAuthCache } = require('@librechat/api');
    invalidateAuthCache();
    res.json({ success: true, message: 'Auth cache invalidated' });
  } catch (error) {
    logger.error('[admin/reload-auth] Error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

module.exports = router;
