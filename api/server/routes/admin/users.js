const express = require('express');
const { SystemRoles } = require('librechat-data-provider');
const { logger } = require('@librechat/data-schemas');
const {
  requireAdmin,
  getSubscriptionBB,
  updateSubscriptionBB,
  getIncludedTokens,
  invalidateSubscriptionCache,
} = require('@librechat/api');
const { requireJwtAuth } = require('~/server/middleware');
const { searchUsers, countUsers, updateUser } = require('~/models');

const router = express.Router();

router.use(requireJwtAuth);
router.use(requireAdmin);

router.get('/', async (req, res) => {
  try {
    const { q = '' } = req.query;
    let users;

    if (q && q.trim().length > 0) {
      users = await searchUsers(q, ['name', 'email', 'username']);
    } else {
      users = await searchUsers('.', ['email']);
    }

    const sanitized = users.map((u) => ({
      id: (u._id || u.id || '').toString(),
      name: u.name || '',
      email: u.email || '',
      username: u.username || '',
      role: u.role || 'USER',
      provider: u.provider || 'local',
      createdAt: u.createdAt || null,
    }));

    sanitized.sort((a, b) => {
      const ta = a.createdAt ? new Date(a.createdAt).getTime() : 0;
      const tb = b.createdAt ? new Date(b.createdAt).getTime() : 0;
      return tb - ta;
    });

    res.json({ users: sanitized, total: sanitized.length });
  } catch (err) {
    logger.error('[Admin/Users] Failed to list users', err);
    res.status(500).json({ error: 'Failed to list users' });
  }
});

router.get('/:userId/subscription', async (req, res) => {
  try {
    const sub = await getSubscriptionBB(req.params.userId);
    res.json({
      plan: sub.plan,
      usageTokens: sub.usageTokens,
      includedTokens: sub.includedTokens || getIncludedTokens(sub.plan),
      periodStart: sub.periodStart || null,
      periodEnd: sub.periodEnd || null,
      stripeCustomerId: sub.stripeCustomerId || null,
      stripeSubscriptionId: sub.stripeSubscriptionId || null,
    });
  } catch (err) {
    logger.error('[Admin/Users] Failed to get subscription', err);
    res.status(500).json({ error: 'Failed to get subscription' });
  }
});

router.put('/:userId/subscription', async (req, res) => {
  try {
    const { plan, usageTokens } = req.body;
    const validPlans = ['free', 'plus', 'unlimited'];

    if (plan && !validPlans.includes(plan)) {
      return res.status(400).json({ error: 'Invalid plan. Must be free, plus, or unlimited.' });
    }

    const updates = {};
    if (plan) {
      updates.plan = plan;
      updates.includedTokens = getIncludedTokens(plan);
    }
    if (typeof usageTokens === 'number') {
      updates.usageTokens = Math.max(0, usageTokens);
    }

    const updated = await updateSubscriptionBB(req.params.userId, updates);
    invalidateSubscriptionCache(req.params.userId);

    logger.info(`[Admin/Users] Admin ${req.user.email} updated subscription for ${req.params.userId}`, updates);

    res.json({
      plan: updated.plan,
      usageTokens: updated.usageTokens,
      includedTokens: updated.includedTokens || getIncludedTokens(updated.plan),
    });
  } catch (err) {
    logger.error('[Admin/Users] Failed to update subscription', err);
    res.status(500).json({ error: 'Failed to update subscription' });
  }
});

router.patch('/set-role', async (req, res) => {
  try {
    const { userId, role } = req.body;
    if (!userId || !role) {
      return res.status(400).json({ error: 'userId and role are required' });
    }

    const validRoles = [SystemRoles.ADMIN, SystemRoles.USER];
    if (!validRoles.includes(role)) {
      return res.status(400).json({ error: `Invalid role. Must be one of: ${validRoles.join(', ')}` });
    }

    if (userId === req.user.id) {
      return res.status(400).json({ error: 'Cannot change your own role' });
    }

    const updated = await updateUser(userId, { role });
    if (!updated) {
      return res.status(404).json({ error: 'User not found' });
    }

    logger.info(`[Admin/Users] Admin ${req.user.email} set role for ${userId} to ${role}`);
    res.json({ userId, role: updated.role || role });
  } catch (err) {
    logger.error('[Admin/Users] Failed to set role', err);
    res.status(500).json({ error: 'Failed to set role' });
  }
});

module.exports = router;
