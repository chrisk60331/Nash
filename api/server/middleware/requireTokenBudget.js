const { getSubscriptionBB, getIncludedTokens } = require('@librechat/api');
const { logger } = require('@librechat/data-schemas');

/**
 * Blocks chat requests when the user has exhausted their included token budget.
 * Only enforced for paid plans (plus/unlimited); free-tier users are gated
 * separately by model restrictions.
 */
const requireTokenBudget = async (req, res, next) => {
  try {
    const userId = req.user?.id;
    if (!userId) {
      return next();
    }

    const sub = await getSubscriptionBB(userId);
    if (sub.plan === 'free') {
      return next();
    }

    const budget = getIncludedTokens(sub.plan);
    if (budget > 0 && (sub.usageTokens ?? 0) >= budget) {
      const isPlus = sub.plan === 'plus';
      const text = isPlus
        ? 'You\'ve used all your included tokens this billing period. Upgrade to Unlimited for 6x more usage, or wait for your next billing cycle.'
        : 'You\'ve used all your included tokens this billing period. Usage resets at the start of your next billing cycle.';

      logger.info(`[requireTokenBudget] User ${userId} exceeded budget (${sub.usageTokens}/${budget})`);
      return res.status(403).json({
        error: 'token_budget_exceeded',
        message: text,
        currentPlan: sub.plan,
        usageTokens: sub.usageTokens,
        includedTokens: budget,
        periodEnd: sub.periodEnd,
      });
    }

    return next();
  } catch (err) {
    logger.error('[requireTokenBudget] Failed to check token budget', err);
    return res.status(500).json({
      error: 'budget_check_failed',
      message: 'Unable to verify usage. Please try again.',
    });
  }
};

module.exports = requireTokenBudget;
