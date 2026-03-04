const { getSubscriptionBB, planMeetsMinimum } = require('@librechat/api');
const { logger } = require('@librechat/data-schemas');

/**
 * Middleware factory that gates routes by minimum subscription plan.
 * @param {'free' | 'plus' | 'unlimited'} minPlan
 */
const requirePlan = (minPlan) => async (req, res, next) => {
  try {
    const sub = await getSubscriptionBB(req.user.id);
    if (planMeetsMinimum(sub.plan, minPlan)) {
      return next();
    }
    return res.status(403).json({
      error: 'upgrade_required',
      message: `This feature requires the ${minPlan} plan or higher.`,
      requiredPlan: minPlan,
      currentPlan: sub.plan,
    });
  } catch (err) {
    logger.error('[requirePlan] Error checking subscription', err);
    return res.status(500).json({
      error: 'subscription_check_failed',
      message: 'Unable to verify subscription status. Please try again.',
    });
  }
};

module.exports = requirePlan;
